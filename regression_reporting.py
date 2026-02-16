# -*- coding: utf-8 -*-
"""Regression report evaluation and rendering helpers."""

import time
from typing import Dict, List


DEFAULT_THRESHOLDS = {
    "max_degradation": 10.0,
    "min_adversarial_detection_rate": 60.0,
    "max_top_bypass_rate": 55.0,
}


def normalize_thresholds(thresholds: dict = None) -> dict:
    merged = dict(DEFAULT_THRESHOLDS)
    if isinstance(thresholds, dict):
        for key in DEFAULT_THRESHOLDS:
            if key in thresholds and thresholds[key] is not None:
                merged[key] = float(thresholds[key])
    return merged


def evaluate_regression_matrix(result: dict, thresholds: dict = None) -> dict:
    thresholds = normalize_thresholds(thresholds)
    runs = result.get("runs", []) if isinstance(result, dict) else []

    run_assessments: List[dict] = []
    alerts: List[dict] = []

    for run in runs:
        snapshot_id = run.get("snapshot_id", "")
        snapshot_name = run.get("snapshot_name", snapshot_id)
        campaign_id = run.get("campaign_id", "")
        summary = run.get("summary", {}) or {}

        baseline_detection = float(summary.get("baseline_detection_rate", 0) or 0)
        adversarial_detection = float(summary.get("adversarial_detection_rate", 0) or 0)
        degradation = float(summary.get("degradation", 0) or 0)

        top_bypass = 0.0
        top_items = summary.get("top_bypass_techniques", [])
        if isinstance(top_items, list) and top_items:
            top_bypass = float(top_items[0].get("bypass_rate", 0) or 0)

        run_status = "ok"

        if adversarial_detection < thresholds["min_adversarial_detection_rate"]:
            run_status = "critical"
            alerts.append(
                {
                    "severity": "critical",
                    "type": "low_detection_rate",
                    "snapshot_id": snapshot_id,
                    "snapshot_name": snapshot_name,
                    "campaign_id": campaign_id,
                    "message": f"对抗检出率 {adversarial_detection:.2f}% 低于阈值 {thresholds['min_adversarial_detection_rate']:.2f}%",
                }
            )

        if degradation > thresholds["max_degradation"]:
            if run_status != "critical":
                run_status = "warning"
            alerts.append(
                {
                    "severity": "warning",
                    "type": "high_degradation",
                    "snapshot_id": snapshot_id,
                    "snapshot_name": snapshot_name,
                    "campaign_id": campaign_id,
                    "message": f"检出衰减 {degradation:.2f}% 超过阈值 {thresholds['max_degradation']:.2f}%",
                }
            )

        if top_bypass > thresholds["max_top_bypass_rate"]:
            if run_status == "ok":
                run_status = "warning"
            alerts.append(
                {
                    "severity": "warning",
                    "type": "top_bypass_too_high",
                    "snapshot_id": snapshot_id,
                    "snapshot_name": snapshot_name,
                    "campaign_id": campaign_id,
                    "message": f"最高绕过技巧成功率 {top_bypass:.2f}% 超过阈值 {thresholds['max_top_bypass_rate']:.2f}%",
                }
            )

        run_assessments.append(
            {
                "snapshot_id": snapshot_id,
                "snapshot_name": snapshot_name,
                "campaign_id": campaign_id,
                "status": run_status,
                "baseline_detection_rate": baseline_detection,
                "adversarial_detection_rate": adversarial_detection,
                "degradation": degradation,
                "top_bypass_rate": top_bypass,
                "total_tests": int(summary.get("total_tests", 0) or 0),
            }
        )

    overall_status = "ok"
    if any(item.get("status") == "critical" for item in run_assessments):
        overall_status = "critical"
    elif any(item.get("status") == "warning" for item in run_assessments):
        overall_status = "warning"

    return {
        "status": overall_status,
        "thresholds": thresholds,
        "run_assessments": run_assessments,
        "alerts": alerts,
        "alert_count": len(alerts),
        "generated_at": time.time(),
    }


def render_regression_markdown(name: str, scenario: str, matrix_result: dict, evaluation: dict) -> str:
    lines: List[str] = []
    lines.append(f"# 回归报告: {name}")
    lines.append("")
    lines.append(f"- 场景: {scenario}")
    lines.append(f"- 状态: {evaluation.get('status', 'ok')}")
    lines.append(f"- 告警数: {evaluation.get('alert_count', 0)}")
    lines.append("")

    thresholds = evaluation.get("thresholds", {})
    lines.append("## 阈值")
    lines.append("")
    lines.append(f"- 最大衰减: {thresholds.get('max_degradation', 0)}%")
    lines.append(f"- 最低对抗检出率: {thresholds.get('min_adversarial_detection_rate', 0)}%")
    lines.append(f"- 最高技巧绕过率: {thresholds.get('max_top_bypass_rate', 0)}%")
    lines.append("")

    lines.append("## 快照结果")
    lines.append("")
    lines.append("| Snapshot | Campaign | Baseline检出率 | 对抗检出率 | 衰减 | 最高绕过率 | 状态 |")
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for item in evaluation.get("run_assessments", []):
        lines.append(
            "| {snapshot} | {campaign} | {base:.2f}% | {adv:.2f}% | {deg:.2f}% | {top:.2f}% | {status} |".format(
                snapshot=item.get("snapshot_name", item.get("snapshot_id", "")),
                campaign=item.get("campaign_id", ""),
                base=item.get("baseline_detection_rate", 0.0),
                adv=item.get("adversarial_detection_rate", 0.0),
                deg=item.get("degradation", 0.0),
                top=item.get("top_bypass_rate", 0.0),
                status=item.get("status", "ok"),
            )
        )
    lines.append("")

    alerts = evaluation.get("alerts", [])
    lines.append("## 告警")
    lines.append("")
    if not alerts:
        lines.append("- 无告警")
    else:
        for alert in alerts:
            lines.append(
                f"- [{alert.get('severity','warning').upper()}] "
                f"{alert.get('snapshot_name', alert.get('snapshot_id', ''))}: {alert.get('message', '')}"
            )
    lines.append("")

    lines.append("## 原始结果")
    lines.append("")
    comparisons = matrix_result.get("comparisons", []) if isinstance(matrix_result, dict) else []
    if comparisons:
        lines.append("- 对比增量:")
        for comp in comparisons:
            delta = comp.get("delta", {})
            lines.append(
                f"  - {comp.get('target_snapshot_id','')}: "
                f"baselineΔ={delta.get('baseline_detection_delta', 0)}, "
                f"adversarialΔ={delta.get('adversarial_detection_delta', 0)}, "
                f"degradationΔ={delta.get('degradation_delta', 0)}"
            )
    else:
        lines.append("- 无跨快照对比数据")

    return "\n".join(lines)
