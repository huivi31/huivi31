#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nightly regression runner for snapshot matrix tests."""

import argparse
import json
import os
import sys
import time

from web_app import app


def _parse_snapshot_ids(raw: str):
    ids = []
    for part in (raw or "").replace("，", ",").split(","):
        item = part.strip()
        if item:
            ids.append(item)
    return ids


def _parse_csv_items(raw: str):
    items = []
    for part in (raw or "").replace("，", ",").split(","):
        item = part.strip()
        if item:
            items.append(item)
    return items


def _status_rank(status: str) -> int:
    s = (status or "ok").lower()
    if s == "critical":
        return 2
    if s == "warning":
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run nightly regression matrix")
    parser.add_argument("--snapshot-ids", required=True, help="comma-separated snapshot ids")
    parser.add_argument("--scenario", default="nightly-regression")
    parser.add_argument("--report-name", default="")
    parser.add_argument("--baseline-rounds", type=int, default=1)
    parser.add_argument("--adversarial-rounds", type=int, default=1)
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--max-degradation", type=float, default=10.0)
    parser.add_argument("--min-adversarial-detection", type=float, default=60.0)
    parser.add_argument("--max-top-bypass-rate", type=float, default=55.0)
    parser.add_argument("--fail-on", choices=["none", "warning", "critical"], default="critical")
    parser.add_argument("--dispatch-alerts", choices=["0", "1"], default="1")
    parser.add_argument("--alert-channel-ids", default="", help="comma-separated channel ids")
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")

    args = parser.parse_args()

    snapshot_ids = _parse_snapshot_ids(args.snapshot_ids)
    if not snapshot_ids:
        print("snapshot ids is empty", file=sys.stderr)
        return 2

    seed = args.random_seed or int(time.time())

    payload = {
        "snapshot_ids": snapshot_ids,
        "scenario": args.scenario,
        "report_name": args.report_name or f"{args.scenario}-{int(time.time())}",
        "baseline_rounds": args.baseline_rounds,
        "adversarial_rounds": args.adversarial_rounds,
        "random_seed": seed,
        "persist_report": True,
        "include_markdown": True,
        "dispatch_alerts": args.dispatch_alerts == "1",
        "alert_channel_ids": _parse_csv_items(args.alert_channel_ids),
        "alert_thresholds": {
            "max_degradation": args.max_degradation,
            "min_adversarial_detection_rate": args.min_adversarial_detection,
            "max_top_bypass_rate": args.max_top_bypass_rate,
        },
    }

    client = app.test_client()
    response = client.post("/regressions/run", json=payload)
    if response.status_code >= 400:
        print(f"regression failed: status={response.status_code} body={response.get_data(as_text=True)}", file=sys.stderr)
        return 1

    result = response.get_json() or {}
    evaluation = result.get("evaluation", {})
    status = (evaluation.get("status") or "ok").lower()
    alert_count = int(evaluation.get("alert_count", 0) or 0)
    report_id = result.get("report_id")
    dispatch = result.get("alert_dispatch") or {}
    dispatch_summary = dispatch.get("summary") or {}

    print(f"report_id={report_id}")
    print(f"status={status}")
    print(f"alert_count={alert_count}")
    print(f"runs={len(result.get('runs', []))}")
    print(f"dispatch_incidents={dispatch_summary.get('incident_count', 0)}")
    print(f"dispatch_sent={dispatch_summary.get('sent_count', 0)}")
    print(f"dispatch_failed={dispatch_summary.get('failed_count', 0)}")

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    markdown = result.get("report_markdown", "")
    if args.output_md and markdown:
        with open(args.output_md, "w", encoding="utf-8") as f:
            f.write(markdown)

    # exit code policy
    fail_threshold = args.fail_on
    if fail_threshold == "none":
        return 0

    status_value = _status_rank(status)
    threshold_value = 1 if fail_threshold == "warning" else 2
    return 1 if status_value >= threshold_value else 0


if __name__ == "__main__":
    sys.exit(main())
