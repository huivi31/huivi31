# -*- coding: utf-8 -*-
"""Alert routing and delivery helpers."""

import json
import time
import urllib.request
from typing import Callable, Dict, List, Optional

from config_store import CONFIG_STORE


SEVERITY_RANK = {
    "info": 0,
    "warning": 1,
    "critical": 2,
}


def normalize_severity(value: str) -> str:
    severity = (value or "warning").strip().lower()
    if severity not in SEVERITY_RANK:
        return "warning"
    return severity


def should_deliver(alert_severity: str, min_severity: str) -> bool:
    return SEVERITY_RANK[normalize_severity(alert_severity)] >= SEVERITY_RANK[normalize_severity(min_severity)]


def _post_json(url: str, payload: dict, headers: dict = None, timeout: float = 3.0) -> str:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - user-controlled endpoint
        status = getattr(resp, "status", None)
        return f"http_status={status}"


def dispatch_alerts(
    alerts: List[dict],
    context: dict,
    event_emitter: Optional[Callable[[str, dict], None]] = None,
    channel_ids: Optional[List[str]] = None,
) -> dict:
    alerts = alerts if isinstance(alerts, list) else []
    if not alerts:
        return {
            "incidents": [],
            "deliveries": [],
            "summary": {"incident_count": 0, "delivery_count": 0, "sent_count": 0, "failed_count": 0},
        }

    selected_ids = {str(x).strip() for x in (channel_ids or []) if str(x).strip()}
    channels = CONFIG_STORE.list_alert_channels(include_disabled=True)
    if selected_ids:
        channels = [c for c in channels if c.get("channel_id") in selected_ids]

    incidents: List[dict] = []
    deliveries: List[dict] = []
    sent_count = 0
    failed_count = 0

    for alert in alerts:
        severity = normalize_severity(alert.get("severity", "warning"))
        alert_type = (alert.get("type") or "regression").strip()
        title = (alert.get("title") or f"{alert_type}:{severity}").strip()
        message = (alert.get("message") or "").strip()
        payload = {
            "alert": alert,
            "context": context or {},
            "generated_at": time.time(),
        }

        incident_id = CONFIG_STORE.create_alert_incident(
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            source_type=(context or {}).get("source_type", ""),
            source_id=(context or {}).get("source_id", ""),
            status="open",
            payload=payload,
        )
        incidents.append(
            {
                "incident_id": incident_id,
                "alert_type": alert_type,
                "severity": severity,
                "title": title,
                "message": message,
            }
        )

        if event_emitter:
            event_emitter(
                "alert_incident_created",
                {
                    "incident_id": incident_id,
                    "severity": severity,
                    "title": title,
                    "source_type": (context or {}).get("source_type", ""),
                    "source_id": (context or {}).get("source_id", ""),
                },
            )

        for channel in channels:
            channel_id = channel.get("channel_id", "")
            min_severity = channel.get("min_severity", "warning")
            channel_payload = {
                "incident_id": incident_id,
                "severity": severity,
                "alert_type": alert_type,
                "title": title,
                "message": message,
                "alert": alert,
                "context": context or {},
            }
            if not channel.get("enabled", False):
                delivery_id = CONFIG_STORE.create_alert_delivery(
                    incident_id=incident_id,
                    channel_id=channel_id,
                    alert_type=alert_type,
                    severity=severity,
                    status="disabled",
                    payload=channel_payload,
                    response="channel disabled",
                )
                deliveries.append(
                    {
                        "delivery_id": delivery_id,
                        "incident_id": incident_id,
                        "channel_id": channel_id,
                        "status": "disabled",
                        "response": "channel disabled",
                    }
                )
                continue

            if not should_deliver(severity, min_severity):
                delivery_id = CONFIG_STORE.create_alert_delivery(
                    incident_id=incident_id,
                    channel_id=channel_id,
                    alert_type=alert_type,
                    severity=severity,
                    status="skipped",
                    payload=channel_payload,
                    response=f"severity {severity} below threshold {min_severity}",
                )
                deliveries.append(
                    {
                        "delivery_id": delivery_id,
                        "incident_id": incident_id,
                        "channel_id": channel_id,
                        "status": "skipped",
                        "response": f"severity {severity} below threshold {min_severity}",
                    }
                )
                continue

            channel_type = (channel.get("channel_type") or "event_bus").strip().lower()
            status = "sent"
            response_text = ""

            try:
                if channel_type == "event_bus":
                    if event_emitter:
                        event_emitter("alert_notification", channel_payload)
                    response_text = "event emitted"
                elif channel_type == "stdout":
                    print(json.dumps(channel_payload, ensure_ascii=False))
                    response_text = "printed"
                elif channel_type == "webhook":
                    config = channel.get("config", {}) or {}
                    timeout = float(config.get("timeout_sec", 3.0) or 3.0)
                    headers = config.get("headers", {}) if isinstance(config.get("headers"), dict) else {}
                    endpoint = (channel.get("endpoint") or "").strip()
                    if not endpoint:
                        raise ValueError("webhook endpoint is empty")
                    response_text = _post_json(endpoint, channel_payload, headers=headers, timeout=timeout)
                else:
                    raise ValueError(f"unsupported channel type: {channel_type}")
            except Exception as exc:  # noqa: BLE001
                status = "failed"
                response_text = str(exc)

            delivery_id = CONFIG_STORE.create_alert_delivery(
                incident_id=incident_id,
                channel_id=channel_id,
                alert_type=alert_type,
                severity=severity,
                status=status,
                payload=channel_payload,
                response=response_text,
            )
            deliveries.append(
                {
                    "delivery_id": delivery_id,
                    "incident_id": incident_id,
                    "channel_id": channel_id,
                    "status": status,
                    "response": response_text,
                }
            )
            if status == "sent":
                sent_count += 1
            if status == "failed":
                failed_count += 1

    return {
        "incidents": incidents,
        "deliveries": deliveries,
        "summary": {
            "incident_count": len(incidents),
            "delivery_count": len(deliveries),
            "sent_count": sent_count,
            "failed_count": failed_count,
        },
    }


def dispatch_regression_alerts(
    evaluation: dict,
    scenario: str,
    source_id: str = "",
    event_emitter: Optional[Callable[[str, dict], None]] = None,
    channel_ids: Optional[List[str]] = None,
) -> dict:
    alerts = evaluation.get("alerts", []) if isinstance(evaluation, dict) else []
    normalized_alerts = []
    for item in alerts:
        severity = normalize_severity(item.get("severity", "warning"))
        alert_type = item.get("type", "regression_alert")
        snapshot_name = item.get("snapshot_name") or item.get("snapshot_id") or ""
        normalized_alerts.append(
            {
                "type": alert_type,
                "severity": severity,
                "title": f"[{severity.upper()}] {snapshot_name or scenario}",
                "message": item.get("message", ""),
                "raw": item,
            }
        )

    context = {
        "source_type": "regression_report",
        "source_id": source_id or "",
        "scenario": scenario,
        "evaluation_status": (evaluation or {}).get("status", "ok"),
        "alert_count": int((evaluation or {}).get("alert_count", 0) or 0),
    }

    return dispatch_alerts(
        normalized_alerts,
        context=context,
        event_emitter=event_emitter,
        channel_ids=channel_ids,
    )
