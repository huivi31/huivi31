# -*- coding: utf-8 -*-
"""Campaign orchestration and replay/compare service."""

import random
import time
from typing import Dict, List, Optional

from config_store import CONFIG_STORE
from agents import (
    EVENT_BUS,
    AttackAgent,
    get_all_personas,
    load_agent_runtime,
)
from battle import run_adversarial_battle


class CampaignOrchestrator:
    def __init__(self):
        pass

    def run_campaign(
        self,
        name: str,
        scenario: str,
        persona_ids: Optional[List[str]] = None,
        target_keywords: Optional[List[str]] = None,
        baseline_rounds: int = 1,
        adversarial_rounds: int = 1,
        enable_peer_learning: bool = True,
        random_seed: Optional[int] = None,
    ) -> dict:
        personas = self._select_personas(persona_ids)
        if not personas:
            raise ValueError("没有可执行的Agent")

        target_keywords = [str(x).strip() for x in (target_keywords or []) if str(x).strip()]
        baseline_rounds = 1 if baseline_rounds is None else int(baseline_rounds)
        adversarial_rounds = 1 if adversarial_rounds is None else int(adversarial_rounds)
        baseline_rounds = max(1, min(baseline_rounds, 5))
        adversarial_rounds = max(0, min(adversarial_rounds, 5))

        config = {
            "scenario": scenario,
            "persona_ids": [p["id"] for p in personas],
            "target_keywords": target_keywords,
            "baseline_rounds": baseline_rounds,
            "adversarial_rounds": adversarial_rounds,
            "enable_peer_learning": bool(enable_peer_learning),
            "random_seed": random_seed,
        }

        if random_seed is not None:
            random.seed(int(random_seed))

        campaign_id = CONFIG_STORE.create_campaign(
            name=name or f"Campaign-{int(time.time())}",
            scenario=scenario or "default",
            config=config,
        )

        EVENT_BUS.emit(
            "campaign_started",
            {
                "campaign_id": campaign_id,
                "name": name,
                "scenario": scenario,
                "persona_count": len(personas),
            },
        )

        try:
            baseline_records = self._run_phase(
                phase="baseline",
                personas=personas,
                rounds=baseline_rounds,
                target_keywords=target_keywords,
                campaign_id=campaign_id,
            )

            learning_connections = []
            if enable_peer_learning:
                learning_connections = self._run_peer_learning(personas, baseline_records)

            evolved_records: List[dict] = []
            if adversarial_rounds > 0:
                evolved_records = self._run_phase(
                    phase="adversarial",
                    personas=personas,
                    rounds=adversarial_rounds,
                    target_keywords=target_keywords,
                    campaign_id=campaign_id,
                    start_iteration=1,
                )

            summary = self._build_summary(
                campaign_id=campaign_id,
                scenario=scenario,
                baseline_records=baseline_records,
                evolved_records=evolved_records,
                learning_connections=learning_connections,
            )
            CONFIG_STORE.complete_campaign(campaign_id, status="completed", summary=summary)

            EVENT_BUS.emit(
                "campaign_completed",
                {
                    "campaign_id": campaign_id,
                    "baseline_tests": len(baseline_records),
                    "adversarial_tests": len(evolved_records),
                    "degradation": summary.get("degradation", 0),
                },
            )

            return {
                "campaign_id": campaign_id,
                "status": "completed",
                "summary": summary,
            }
        except Exception as exc:
            CONFIG_STORE.complete_campaign(
                campaign_id,
                status="failed",
                summary={"error": str(exc)},
            )
            EVENT_BUS.emit(
                "campaign_failed",
                {"campaign_id": campaign_id, "error": str(exc)},
            )
            raise

    def replay_campaign(self, campaign_id: str, phase: str = "", limit: int = 5000) -> dict:
        campaign = CONFIG_STORE.get_campaign(campaign_id)
        if not campaign:
            return {"error": "campaign not found"}

        records = CONFIG_STORE.list_campaign_records(
            campaign_id=campaign_id,
            phase=phase or None,
            limit=limit,
        )
        return {
            "campaign": campaign,
            "phase": phase or "all",
            "records": records,
            "count": len(records),
        }

    def compare_campaigns(self, campaign_ids: List[str]) -> dict:
        selected = []
        for campaign_id in campaign_ids:
            campaign = CONFIG_STORE.get_campaign(campaign_id)
            if not campaign:
                continue
            summary = campaign.get("summary", {})
            selected.append(
                {
                    "campaign_id": campaign_id,
                    "name": campaign.get("name", ""),
                    "scenario": campaign.get("scenario", ""),
                    "status": campaign.get("status", ""),
                    "baseline_detection_rate": summary.get("baseline_detection_rate", 0),
                    "adversarial_detection_rate": summary.get("adversarial_detection_rate", 0),
                    "degradation": summary.get("degradation", 0),
                    "total_tests": summary.get("total_tests", 0),
                }
            )

        if not selected:
            return {"campaigns": [], "comparison": []}

        base = selected[0]
        comparison = []
        for item in selected[1:]:
            comparison.append(
                {
                    "campaign_id": item["campaign_id"],
                    "vs_campaign_id": base["campaign_id"],
                    "baseline_detection_delta": round(
                        item["baseline_detection_rate"] - base["baseline_detection_rate"], 2
                    ),
                    "adversarial_detection_delta": round(
                        item["adversarial_detection_rate"] - base["adversarial_detection_rate"], 2
                    ),
                    "degradation_delta": round(item["degradation"] - base["degradation"], 2),
                }
            )

        return {
            "campaigns": selected,
            "comparison": comparison,
        }

    def list_campaigns(self, limit: int = 20) -> List[dict]:
        return CONFIG_STORE.list_campaigns(limit=limit)

    def _select_personas(self, persona_ids: Optional[List[str]]) -> List[dict]:
        personas = get_all_personas()
        if not persona_ids:
            return personas

        wanted = {str(pid).strip() for pid in persona_ids if str(pid).strip()}
        return [p for p in personas if p.get("id") in wanted]

    def _run_phase(
        self,
        phase: str,
        personas: List[dict],
        rounds: int,
        target_keywords: List[str],
        campaign_id: str,
        start_iteration: int = 0,
    ) -> List[dict]:
        records: List[dict] = []

        EVENT_BUS.emit(
            "campaign_phase_start",
            {
                "campaign_id": campaign_id,
                "phase": phase,
                "rounds": rounds,
                "persona_count": len(personas),
            },
        )

        for round_idx in range(rounds):
            for i, persona in enumerate(personas):
                keyword = None
                if target_keywords:
                    keyword = target_keywords[(i + round_idx) % len(target_keywords)]

                iteration = start_iteration + round_idx
                record = run_adversarial_battle(
                    persona_id=persona["id"],
                    target_keyword=keyword,
                    iteration=iteration,
                )
                records.append(record)
                CONFIG_STORE.append_campaign_record(
                    campaign_id=campaign_id,
                    phase=phase,
                    persona_id=persona["id"],
                    record=record,
                )

        EVENT_BUS.emit(
            "campaign_phase_end",
            {
                "campaign_id": campaign_id,
                "phase": phase,
                "records": len(records),
            },
        )

        return records

    def _run_peer_learning(self, personas: List[dict], baseline_records: List[dict]) -> List[dict]:
        successful = []
        for record in baseline_records:
            if record.get("result", {}).get("bypass_success"):
                technique = record.get("attack", {}).get("technique_used", "")
                if technique:
                    successful.append(
                        {
                            "agent_id": record.get("persona_id", ""),
                            "technique": technique,
                            "category": record.get("category", ""),
                        }
                    )

        if not successful:
            return []

        connections: List[dict] = []
        for learner_persona in personas:
            learner_id = learner_persona.get("id", "")
            if not learner_id:
                continue

            learner = AttackAgent(learner_persona)
            load_agent_runtime(learner)

            for share in successful:
                teacher_id = share.get("agent_id", "")
                if not teacher_id or teacher_id == learner_id:
                    continue
                learned = learner.learn_from_peer(
                    share.get("technique", ""),
                    share.get("category", ""),
                    teacher_id,
                )
                if learned:
                    connections.append(
                        {
                            "from": teacher_id,
                            "to": learner_id,
                            "technique": share.get("technique", ""),
                        }
                    )

        if connections:
            EVENT_BUS.emit(
                "campaign_peer_learning",
                {
                    "connections": connections,
                    "count": len(connections),
                },
            )

        return connections

    def _build_summary(
        self,
        campaign_id: str,
        scenario: str,
        baseline_records: List[dict],
        evolved_records: List[dict],
        learning_connections: List[dict],
    ) -> dict:
        baseline_detection_rate = self._detection_rate(baseline_records)
        adversarial_detection_rate = self._detection_rate(evolved_records)
        if not evolved_records:
            adversarial_detection_rate = baseline_detection_rate

        degradation = round(baseline_detection_rate - adversarial_detection_rate, 2)

        by_technique = self._technique_stats(baseline_records + evolved_records)
        top_bypass = sorted(
            by_technique.items(),
            key=lambda kv: kv[1].get("bypass_rate", 0),
            reverse=True,
        )[:5]

        return {
            "campaign_id": campaign_id,
            "scenario": scenario,
            "baseline_detection_rate": baseline_detection_rate,
            "adversarial_detection_rate": adversarial_detection_rate,
            "degradation": degradation,
            "total_tests": len(baseline_records) + len(evolved_records),
            "baseline_tests": len(baseline_records),
            "adversarial_tests": len(evolved_records),
            "learning_connections": len(learning_connections),
            "rule_robustness": "weak" if degradation > 20 else "moderate" if degradation > 10 else "strong",
            "top_bypass_techniques": [
                {"technique": k, **v} for k, v in top_bypass
            ],
        }

    def _detection_rate(self, records: List[dict]) -> float:
        if not records:
            return 0.0
        detected = sum(1 for r in records if r.get("defense", {}).get("detected", False))
        return round(detected / len(records) * 100, 2)

    def _technique_stats(self, records: List[dict]) -> Dict[str, dict]:
        stats: Dict[str, dict] = {}
        for record in records:
            technique = record.get("attack", {}).get("technique_used") or "未知技巧"
            item = stats.setdefault(technique, {"total": 0, "success": 0, "bypass_rate": 0})
            item["total"] += 1
            if record.get("result", {}).get("bypass_success", False):
                item["success"] += 1

        for technique, item in stats.items():
            total = max(1, item["total"])
            item["bypass_rate"] = round(item["success"] / total * 100, 2)
        return stats


CAMPAIGN_ORCHESTRATOR = CampaignOrchestrator()
