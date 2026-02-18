# -*- coding: utf-8 -*-
"""Persistent configuration and simulation result store."""

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Dict, List, Optional, Tuple


DEFAULT_DB_PATH = os.getenv(
    "RISK_CONFIG_DB_PATH",
    os.path.join(os.path.dirname(__file__), "data", "config.db"),
)


class ConfigStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._initialized = False
        self._schema_ready = False

    def initialize(self, default_personas: List[dict], default_techniques: Dict[str, dict]):
        with self._lock:
            if self._initialized:
                return

            self._ensure_schema()

            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

            with self._connect() as conn:
                self._bootstrap_personas(conn, default_personas)
                self._bootstrap_techniques(conn, default_techniques)
                self._bootstrap_alert_channels(conn)

            self._initialized = True

    # ------------------------------------------------------------------
    # Personas and techniques
    # ------------------------------------------------------------------
    def list_personas(self) -> List[dict]:
        self._ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM personas ORDER BY created_at ASC"
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def upsert_persona(self, persona: dict):
        self._ensure_schema()
        persona_id = (persona or {}).get("id")
        if not persona_id:
            raise ValueError("persona id is required")

        now = time.time()
        payload = json.dumps(persona, ensure_ascii=False)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO personas (persona_id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(persona_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (persona_id, payload, now, now),
            )
            conn.commit()

    def list_techniques(self) -> List[dict]:
        self._ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM techniques ORDER BY category ASC, technique_name ASC"
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def upsert_technique(self, category: str, name: str, details: dict):
        self._ensure_schema()
        if not category or not name:
            raise ValueError("technique category and name are required")

        record = dict(details or {})
        record["name"] = name
        record["category"] = category

        now = time.time()
        payload = json.dumps(record, ensure_ascii=False)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO techniques (technique_name, category, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(technique_name) DO UPDATE SET
                    category = excluded.category,
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (name, category, payload, now, now),
            )
            conn.commit()

    def get_technique_map(self) -> Dict[str, Dict[str, dict]]:
        mapping: Dict[str, Dict[str, dict]] = {}
        for item in self.list_techniques():
            category = item.get("category", "未分类")
            name = item.get("name")
            if not name:
                continue
            normalized = dict(item)
            normalized.pop("name", None)
            normalized.pop("category", None)
            mapping.setdefault(category, {})[name] = normalized
        return mapping

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------
    def load_rules(self) -> Tuple[List[dict], int]:
        self._ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT rules_json, rules_version FROM rules_state WHERE id = 1"
            ).fetchone()

        if not row:
            return [], 0

        rules_json = row["rules_json"] or "[]"
        try:
            rules = json.loads(rules_json)
        except json.JSONDecodeError:
            rules = []

        version = int(row["rules_version"] or 0)
        return rules, version

    def save_rules(self, rules: List[dict], rules_version: int):
        self._ensure_schema()
        now = time.time()
        rules_json = json.dumps(rules or [], ensure_ascii=False)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rules_state (id, rules_json, rules_version, updated_at)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    rules_json = excluded.rules_json,
                    rules_version = excluded.rules_version,
                    updated_at = excluded.updated_at
                """,
                (rules_json, int(rules_version), now),
            )
            conn.commit()

    def clear_rules(self):
        self._ensure_schema()
        with self._connect() as conn:
            conn.execute("DELETE FROM rules_state WHERE id = 1")
            conn.commit()

    # ------------------------------------------------------------------
    # Rule snapshots
    # ------------------------------------------------------------------
    def create_rule_snapshot(
        self,
        name: str,
        rules: List[dict],
        rules_version: int,
        metadata: Optional[dict] = None,
    ) -> str:
        self._ensure_schema()
        snapshot_id = f"rs_{uuid.uuid4().hex[:16]}"
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rule_snapshots (
                    snapshot_id, name, rules_json, rules_version, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    name or snapshot_id,
                    json.dumps(rules or [], ensure_ascii=False),
                    int(rules_version or 0),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
        return snapshot_id

    def get_rule_snapshot(self, snapshot_id: str) -> Optional[dict]:
        self._ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT snapshot_id, name, rules_json, rules_version, metadata_json, created_at
                FROM rule_snapshots WHERE snapshot_id = ?
                """,
                (snapshot_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "snapshot_id": row["snapshot_id"],
            "name": row["name"],
            "rules": _safe_json(row["rules_json"], []),
            "rules_version": int(row["rules_version"] or 0),
            "metadata": _safe_json(row["metadata_json"], {}),
            "created_at": row["created_at"],
        }

    def list_rule_snapshots(self, limit: int = 50) -> List[dict]:
        self._ensure_schema()
        limit = max(1, min(int(limit or 50), 500))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT snapshot_id, name, rules_json, rules_version, metadata_json, created_at
                FROM rule_snapshots
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "snapshot_id": row["snapshot_id"],
                "name": row["name"],
                "rules": _safe_json(row["rules_json"], []),
                "rules_version": int(row["rules_version"] or 0),
                "metadata": _safe_json(row["metadata_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Knowledge feed persistence
    # ------------------------------------------------------------------
    def add_knowledge_item(
        self,
        feed_type: str,
        payload: dict,
        category: str = "",
        technique: str = "",
        source: str = "manual",
        tags: Optional[List[str]] = None,
    ) -> int:
        self._ensure_schema()
        feed_type = (feed_type or "materials").strip()
        now = time.time()
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        payload_json = json.dumps(payload or {}, ensure_ascii=False)

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO knowledge_items (
                    feed_type, category, technique, source, tags_json, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (feed_type, category, technique, source, tags_json, payload_json, now),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_knowledge_items(
        self,
        feed_type: Optional[str] = None,
        limit: int = 500,
    ) -> List[dict]:
        self._ensure_schema()
        limit = max(1, min(int(limit or 500), 5000))
        sql = """
            SELECT id, feed_type, category, technique, source, tags_json, payload_json, created_at
            FROM knowledge_items
        """
        params: list = []
        if feed_type:
            sql += " WHERE feed_type = ?"
            params.append(feed_type)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        items = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except json.JSONDecodeError:
                payload = {}
            try:
                tags = json.loads(row["tags_json"] or "[]")
            except json.JSONDecodeError:
                tags = []

            items.append(
                {
                    "id": row["id"],
                    "feed_type": row["feed_type"],
                    "category": row["category"],
                    "technique": row["technique"],
                    "source": row["source"],
                    "tags": tags,
                    "payload": payload,
                    "timestamp": row["created_at"],
                }
            )

        return items

    def clear_knowledge_items(self):
        self._ensure_schema()
        with self._connect() as conn:
            conn.execute("DELETE FROM knowledge_items")
            conn.commit()

    def get_knowledge_stats(self) -> dict:
        self._ensure_schema()
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(1) AS c FROM knowledge_items").fetchone()["c"]
            by_type_rows = conn.execute(
                "SELECT feed_type, COUNT(1) AS c FROM knowledge_items GROUP BY feed_type"
            ).fetchall()
            by_source_rows = conn.execute(
                "SELECT source, COUNT(1) AS c FROM knowledge_items GROUP BY source ORDER BY c DESC LIMIT 20"
            ).fetchall()

        return {
            "total_items": int(total or 0),
            "by_type": {row["feed_type"]: int(row["c"] or 0) for row in by_type_rows},
            "top_sources": {row["source"]: int(row["c"] or 0) for row in by_source_rows},
        }

    # ------------------------------------------------------------------
    # Campaign and replay result repository
    # ------------------------------------------------------------------
    def create_campaign(self, name: str, scenario: str, config: dict) -> str:
        self._ensure_schema()
        campaign_id = f"cmp_{uuid.uuid4().hex[:16]}"
        now = time.time()
        config_json = json.dumps(config or {}, ensure_ascii=False)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO campaigns (
                    campaign_id, name, scenario, status, config_json, summary_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (campaign_id, name, scenario, "running", config_json, "{}", now, now),
            )
            conn.commit()

        return campaign_id

    def append_campaign_record(
        self,
        campaign_id: str,
        phase: str,
        persona_id: str,
        record: dict,
    ):
        self._ensure_schema()
        now = time.time()
        record_json = json.dumps(record or {}, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO campaign_records (
                    campaign_id, phase, persona_id, record_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (campaign_id, phase, persona_id, record_json, now),
            )
            conn.commit()

    def complete_campaign(self, campaign_id: str, status: str, summary: dict):
        self._ensure_schema()
        now = time.time()
        summary_json = json.dumps(summary or {}, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE campaigns
                SET status = ?, summary_json = ?, updated_at = ?
                WHERE campaign_id = ?
                """,
                (status, summary_json, now, campaign_id),
            )
            conn.commit()

    def get_campaign(self, campaign_id: str) -> Optional[dict]:
        self._ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT campaign_id, name, scenario, status, config_json, summary_json, created_at, updated_at
                FROM campaigns WHERE campaign_id = ?
                """,
                (campaign_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "campaign_id": row["campaign_id"],
            "name": row["name"],
            "scenario": row["scenario"],
            "status": row["status"],
            "config": _safe_json(row["config_json"], {}),
            "summary": _safe_json(row["summary_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_campaigns(self, limit: int = 20) -> List[dict]:
        self._ensure_schema()
        limit = max(1, min(int(limit or 20), 200))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT campaign_id, name, scenario, status, config_json, summary_json, created_at, updated_at
                FROM campaigns
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "campaign_id": row["campaign_id"],
                "name": row["name"],
                "scenario": row["scenario"],
                "status": row["status"],
                "config": _safe_json(row["config_json"], {}),
                "summary": _safe_json(row["summary_json"], {}),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def list_campaign_records(
        self,
        campaign_id: str,
        phase: Optional[str] = None,
        limit: int = 5000,
    ) -> List[dict]:
        self._ensure_schema()
        limit = max(1, min(int(limit or 5000), 20000))
        sql = """
            SELECT id, campaign_id, phase, persona_id, record_json, created_at
            FROM campaign_records
            WHERE campaign_id = ?
        """
        params: list = [campaign_id]
        if phase:
            sql += " AND phase = ?"
            params.append(phase)
        sql += " ORDER BY id ASC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "id": row["id"],
                "campaign_id": row["campaign_id"],
                "phase": row["phase"],
                "persona_id": row["persona_id"],
                "record": _safe_json(row["record_json"], {}),
                "timestamp": row["created_at"],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Regression reports
    # ------------------------------------------------------------------
    def create_regression_report(
        self,
        name: str,
        scenario: str,
        status: str,
        thresholds: dict,
        payload: dict,
        markdown: str = "",
    ) -> str:
        self._ensure_schema()
        report_id = f"rr_{uuid.uuid4().hex[:16]}"
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO regression_reports (
                    report_id, name, scenario, status, thresholds_json, payload_json, markdown_text, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    name or report_id,
                    scenario or "regression",
                    status or "ok",
                    json.dumps(thresholds or {}, ensure_ascii=False),
                    json.dumps(payload or {}, ensure_ascii=False),
                    markdown or "",
                    now,
                ),
            )
            conn.commit()
        return report_id

    def get_regression_report(self, report_id: str) -> Optional[dict]:
        self._ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT report_id, name, scenario, status, thresholds_json, payload_json, markdown_text, created_at
                FROM regression_reports
                WHERE report_id = ?
                """,
                (report_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "report_id": row["report_id"],
            "name": row["name"],
            "scenario": row["scenario"],
            "status": row["status"],
            "thresholds": _safe_json(row["thresholds_json"], {}),
            "payload": _safe_json(row["payload_json"], {}),
            "markdown": row["markdown_text"] or "",
            "created_at": row["created_at"],
        }

    def list_regression_reports(self, limit: int = 50) -> List[dict]:
        self._ensure_schema()
        limit = max(1, min(int(limit or 50), 500))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT report_id, name, scenario, status, thresholds_json, payload_json, created_at
                FROM regression_reports
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "report_id": row["report_id"],
                "name": row["name"],
                "scenario": row["scenario"],
                "status": row["status"],
                "thresholds": _safe_json(row["thresholds_json"], {}),
                "payload": _safe_json(row["payload_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Rule governance workflow
    # ------------------------------------------------------------------
    def create_rule_change_request(
        self,
        title: str,
        proposer: str,
        proposed_rules: List[dict],
        proposed_rules_version: int,
        description: str = "",
        source_snapshot_id: str = "",
        risk_level: str = "medium",
        metadata: Optional[dict] = None,
    ) -> str:
        self._ensure_schema()
        request_id = f"rcr_{uuid.uuid4().hex[:16]}"
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rule_change_requests (
                    request_id, title, description, proposer, proposed_rules_json, proposed_rules_version,
                    source_snapshot_id, risk_level, status, review_comment, reviewer, metadata_json,
                    created_at, updated_at, reviewed_at, applied_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    title or request_id,
                    description or "",
                    proposer or "system",
                    json.dumps(proposed_rules or [], ensure_ascii=False),
                    int(proposed_rules_version or 0),
                    source_snapshot_id or "",
                    risk_level or "medium",
                    "pending",
                    "",
                    "",
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                    now,
                    0.0,
                    0.0,
                ),
            )
            conn.commit()
        return request_id

    def get_rule_change_request(self, request_id: str) -> Optional[dict]:
        self._ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT request_id, title, description, proposer, proposed_rules_json, proposed_rules_version,
                       source_snapshot_id, risk_level, status, review_comment, reviewer, metadata_json,
                       created_at, updated_at, reviewed_at, applied_at
                FROM rule_change_requests
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()

        if not row:
            return None
        return {
            "request_id": row["request_id"],
            "title": row["title"],
            "description": row["description"],
            "proposer": row["proposer"],
            "proposed_rules": _safe_json(row["proposed_rules_json"], []),
            "proposed_rules_version": int(row["proposed_rules_version"] or 0),
            "source_snapshot_id": row["source_snapshot_id"],
            "risk_level": row["risk_level"],
            "status": row["status"],
            "review_comment": row["review_comment"] or "",
            "reviewer": row["reviewer"] or "",
            "metadata": _safe_json(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "reviewed_at": row["reviewed_at"],
            "applied_at": row["applied_at"],
        }

    def list_rule_change_requests(self, status: str = "", limit: int = 50) -> List[dict]:
        self._ensure_schema()
        limit = max(1, min(int(limit or 50), 500))
        sql = """
            SELECT request_id, title, description, proposer, proposed_rules_json, proposed_rules_version,
                   source_snapshot_id, risk_level, status, review_comment, reviewer, metadata_json,
                   created_at, updated_at, reviewed_at, applied_at
            FROM rule_change_requests
        """
        params = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "request_id": row["request_id"],
                "title": row["title"],
                "description": row["description"],
                "proposer": row["proposer"],
                "proposed_rules": _safe_json(row["proposed_rules_json"], []),
                "proposed_rules_version": int(row["proposed_rules_version"] or 0),
                "source_snapshot_id": row["source_snapshot_id"],
                "risk_level": row["risk_level"],
                "status": row["status"],
                "review_comment": row["review_comment"] or "",
                "reviewer": row["reviewer"] or "",
                "metadata": _safe_json(row["metadata_json"], {}),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "reviewed_at": row["reviewed_at"],
                "applied_at": row["applied_at"],
            }
            for row in rows
        ]

    def review_rule_change_request(
        self,
        request_id: str,
        decision: str,
        reviewer: str,
        comment: str = "",
    ) -> Optional[dict]:
        self._ensure_schema()
        normalized = (decision or "").strip().lower()
        if normalized not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")

        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE rule_change_requests
                SET status = ?, reviewer = ?, review_comment = ?, reviewed_at = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (normalized, reviewer or "reviewer", comment or "", now, now, request_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None

        return self.get_rule_change_request(request_id)

    def mark_rule_change_request_applied(
        self,
        request_id: str,
        actor: str,
        comment: str = "",
    ) -> Optional[dict]:
        self._ensure_schema()
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE rule_change_requests
                SET status = ?, reviewer = COALESCE(NULLIF(reviewer, ''), ?),
                    review_comment = CASE
                        WHEN review_comment IS NULL OR review_comment = '' THEN ?
                        ELSE review_comment || '\n' || ?
                    END,
                    applied_at = ?, updated_at = ?
                WHERE request_id = ?
                """,
                ("applied", actor or "system", comment or "", comment or "", now, now, request_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
        return self.get_rule_change_request(request_id)

    # ------------------------------------------------------------------
    # Audit logs
    # ------------------------------------------------------------------
    def create_audit_log(
        self,
        event_type: str,
        action: str,
        actor: str,
        target_type: str = "",
        target_id: str = "",
        severity: str = "info",
        details: Optional[dict] = None,
    ) -> int:
        self._ensure_schema()
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO audit_logs (
                    event_type, action, actor, target_type, target_id, severity, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type or "system",
                    action or "",
                    actor or "system",
                    target_type or "",
                    target_id or "",
                    severity or "info",
                    json.dumps(details or {}, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_audit_logs(
        self,
        limit: int = 100,
        event_type: str = "",
        actor: str = "",
        target_type: str = "",
        target_id: str = "",
        severity: str = "",
    ) -> List[dict]:
        self._ensure_schema()
        limit = max(1, min(int(limit or 100), 2000))
        sql = """
            SELECT id, event_type, action, actor, target_type, target_id, severity, details_json, created_at
            FROM audit_logs
            WHERE 1 = 1
        """
        params = []
        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)
        if actor:
            sql += " AND actor = ?"
            params.append(actor)
        if target_type:
            sql += " AND target_type = ?"
            params.append(target_type)
        if target_id:
            sql += " AND target_id = ?"
            params.append(target_id)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "id": int(row["id"]),
                "event_type": row["event_type"],
                "action": row["action"],
                "actor": row["actor"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "severity": row["severity"],
                "details": _safe_json(row["details_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Alert channels and deliveries
    # ------------------------------------------------------------------
    def upsert_alert_channel(
        self,
        name: str,
        channel_type: str,
        endpoint: str = "",
        min_severity: str = "warning",
        enabled: bool = True,
        config: Optional[dict] = None,
        channel_id: str = "",
    ) -> str:
        self._ensure_schema()
        now = time.time()
        if not channel_id:
            channel_id = f"ac_{uuid.uuid4().hex[:16]}"

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO alert_channels (
                    channel_id, name, channel_type, endpoint, min_severity, enabled, config_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    name = excluded.name,
                    channel_type = excluded.channel_type,
                    endpoint = excluded.endpoint,
                    min_severity = excluded.min_severity,
                    enabled = excluded.enabled,
                    config_json = excluded.config_json,
                    updated_at = excluded.updated_at
                """,
                (
                    channel_id,
                    name or channel_id,
                    channel_type or "event_bus",
                    endpoint or "",
                    min_severity or "warning",
                    1 if enabled else 0,
                    json.dumps(config or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.commit()
        return channel_id

    def get_alert_channel(self, channel_id: str) -> Optional[dict]:
        self._ensure_schema()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT channel_id, name, channel_type, endpoint, min_severity, enabled, config_json, created_at, updated_at
                FROM alert_channels
                WHERE channel_id = ?
                """,
                (channel_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "channel_id": row["channel_id"],
            "name": row["name"],
            "channel_type": row["channel_type"],
            "endpoint": row["endpoint"] or "",
            "min_severity": row["min_severity"] or "warning",
            "enabled": bool(row["enabled"]),
            "config": _safe_json(row["config_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_alert_channels(self, include_disabled: bool = False) -> List[dict]:
        self._ensure_schema()
        sql = """
            SELECT channel_id, name, channel_type, endpoint, min_severity, enabled, config_json, created_at, updated_at
            FROM alert_channels
        """
        params = []
        if not include_disabled:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY created_at ASC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "channel_id": row["channel_id"],
                "name": row["name"],
                "channel_type": row["channel_type"],
                "endpoint": row["endpoint"] or "",
                "min_severity": row["min_severity"] or "warning",
                "enabled": bool(row["enabled"]),
                "config": _safe_json(row["config_json"], {}),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def set_alert_channel_enabled(self, channel_id: str, enabled: bool) -> Optional[dict]:
        self._ensure_schema()
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE alert_channels SET enabled = ?, updated_at = ? WHERE channel_id = ?",
                (1 if enabled else 0, now, channel_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
        return self.get_alert_channel(channel_id)

    def create_alert_incident(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        source_type: str = "",
        source_id: str = "",
        status: str = "open",
        payload: Optional[dict] = None,
    ) -> str:
        self._ensure_schema()
        incident_id = f"ai_{uuid.uuid4().hex[:16]}"
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO alert_incidents (
                    incident_id, alert_type, severity, title, message, source_type, source_id,
                    status, payload_json, acknowledged_by, acknowledged_note, created_at, updated_at, acknowledged_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    alert_type or "regression",
                    severity or "warning",
                    title or incident_id,
                    message or "",
                    source_type or "",
                    source_id or "",
                    status or "open",
                    json.dumps(payload or {}, ensure_ascii=False),
                    "",
                    "",
                    now,
                    now,
                    0.0,
                ),
            )
            conn.commit()
        return incident_id

    def list_alert_incidents(
        self,
        limit: int = 100,
        status: str = "",
        severity: str = "",
    ) -> List[dict]:
        self._ensure_schema()
        limit = max(1, min(int(limit or 100), 2000))
        sql = """
            SELECT incident_id, alert_type, severity, title, message, source_type, source_id,
                   status, payload_json, acknowledged_by, acknowledged_note, created_at, updated_at, acknowledged_at
            FROM alert_incidents
            WHERE 1 = 1
        """
        params = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "incident_id": row["incident_id"],
                "alert_type": row["alert_type"],
                "severity": row["severity"],
                "title": row["title"],
                "message": row["message"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "status": row["status"],
                "payload": _safe_json(row["payload_json"], {}),
                "acknowledged_by": row["acknowledged_by"] or "",
                "acknowledged_note": row["acknowledged_note"] or "",
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "acknowledged_at": row["acknowledged_at"],
            }
            for row in rows
        ]

    def acknowledge_alert_incident(
        self,
        incident_id: str,
        actor: str,
        note: str = "",
        status: str = "acknowledged",
    ) -> Optional[dict]:
        self._ensure_schema()
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE alert_incidents
                SET status = ?, acknowledged_by = ?, acknowledged_note = ?, acknowledged_at = ?, updated_at = ?
                WHERE incident_id = ?
                """,
                (status or "acknowledged", actor or "operator", note or "", now, now, incident_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None

            row = conn.execute(
                """
                SELECT incident_id, alert_type, severity, title, message, source_type, source_id,
                       status, payload_json, acknowledged_by, acknowledged_note, created_at, updated_at, acknowledged_at
                FROM alert_incidents
                WHERE incident_id = ?
                """,
                (incident_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "incident_id": row["incident_id"],
            "alert_type": row["alert_type"],
            "severity": row["severity"],
            "title": row["title"],
            "message": row["message"],
            "source_type": row["source_type"],
            "source_id": row["source_id"],
            "status": row["status"],
            "payload": _safe_json(row["payload_json"], {}),
            "acknowledged_by": row["acknowledged_by"] or "",
            "acknowledged_note": row["acknowledged_note"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "acknowledged_at": row["acknowledged_at"],
        }

    def create_alert_delivery(
        self,
        incident_id: str,
        channel_id: str,
        alert_type: str,
        severity: str,
        status: str,
        payload: Optional[dict] = None,
        response: str = "",
    ) -> str:
        self._ensure_schema()
        delivery_id = f"ad_{uuid.uuid4().hex[:16]}"
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO alert_deliveries (
                    delivery_id, incident_id, channel_id, alert_type, severity, status,
                    payload_json, response_text, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delivery_id,
                    incident_id or "",
                    channel_id or "",
                    alert_type or "regression",
                    severity or "warning",
                    status or "sent",
                    json.dumps(payload or {}, ensure_ascii=False),
                    response or "",
                    now,
                ),
            )
            conn.commit()
        return delivery_id

    def list_alert_deliveries(
        self,
        limit: int = 200,
        status: str = "",
        severity: str = "",
        channel_id: str = "",
        alert_type: str = "",
    ) -> List[dict]:
        self._ensure_schema()
        limit = max(1, min(int(limit or 200), 5000))
        sql = """
            SELECT delivery_id, incident_id, channel_id, alert_type, severity, status,
                   payload_json, response_text, created_at
            FROM alert_deliveries
            WHERE 1 = 1
        """
        params = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        if channel_id:
            sql += " AND channel_id = ?"
            params.append(channel_id)
        if alert_type:
            sql += " AND alert_type = ?"
            params.append(alert_type)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "delivery_id": row["delivery_id"],
                "incident_id": row["incident_id"],
                "channel_id": row["channel_id"],
                "alert_type": row["alert_type"],
                "severity": row["severity"],
                "status": row["status"],
                "payload": _safe_json(row["payload_json"], {}),
                "response": row["response_text"] or "",
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Internal table setup
    # ------------------------------------------------------------------
    def _create_tables(self, conn: sqlite3.Connection):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS personas (
                persona_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS techniques (
                technique_name TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rules_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                rules_json TEXT NOT NULL,
                rules_version INTEGER NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rule_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                rules_json TEXT NOT NULL,
                rules_version INTEGER NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rule_snapshots_created ON rule_snapshots(created_at DESC)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_type TEXT NOT NULL,
                category TEXT NOT NULL,
                technique TEXT NOT NULL,
                source TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_knowledge_feed_time ON knowledge_items(feed_type, created_at DESC)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS campaigns (
                campaign_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                scenario TEXT NOT NULL,
                status TEXT NOT NULL,
                config_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS campaign_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                persona_id TEXT NOT NULL,
                record_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_campaign_records_main ON campaign_records(campaign_id, phase, id)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS regression_reports (
                report_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                scenario TEXT NOT NULL,
                status TEXT NOT NULL,
                thresholds_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                markdown_text TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_regression_reports_created ON regression_reports(created_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rule_change_requests (
                request_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                proposer TEXT NOT NULL,
                proposed_rules_json TEXT NOT NULL,
                proposed_rules_version INTEGER NOT NULL,
                source_snapshot_id TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL,
                review_comment TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                reviewed_at REAL NOT NULL,
                applied_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rule_change_requests_status_time ON rule_change_requests(status, created_at DESC)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_main ON audit_logs(event_type, severity, created_at DESC)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_channels (
                channel_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                channel_type TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                min_severity TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                config_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_incidents (
                incident_id TEXT PRIMARY KEY,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                acknowledged_by TEXT NOT NULL,
                acknowledged_note TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                acknowledged_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_incidents_main ON alert_incidents(status, severity, created_at DESC)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_deliveries (
                delivery_id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                response_text TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_deliveries_main ON alert_deliveries(status, severity, created_at DESC)"
        )
        conn.commit()

    def _bootstrap_personas(self, conn: sqlite3.Connection, default_personas: List[dict]):
        now = time.time()
        for persona in default_personas:
            if not persona.get("id"):
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO personas (persona_id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (persona["id"], json.dumps(persona, ensure_ascii=False), now, now),
            )
        conn.commit()

    def _bootstrap_techniques(self, conn: sqlite3.Connection, default_techniques: Dict[str, dict]):
        now = time.time()
        for category, techniques in (default_techniques or {}).items():
            if not isinstance(techniques, dict):
                continue
            for name, details in techniques.items():
                record = dict(details or {})
                record["name"] = name
                record["category"] = category
                conn.execute(
                    """
                    INSERT OR REPLACE INTO techniques (technique_name, category, payload, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, category, json.dumps(record, ensure_ascii=False), now, now),
                )
        conn.commit()

    def _bootstrap_alert_channels(self, conn: sqlite3.Connection):
        row = conn.execute("SELECT COUNT(1) AS c FROM alert_channels").fetchone()
        if row and row["c"] > 0:
            return

        now = time.time()
        conn.execute(
            """
            INSERT INTO alert_channels (
                channel_id, name, channel_type, endpoint, min_severity, enabled, config_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "default_event_bus",
                "Default Event Bus",
                "event_bus",
                "",
                "warning",
                1,
                "{}",
                now,
                now,
            ),
        )
        conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        with self._lock:
            if self._schema_ready:
                return

            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

            conn = self._connect()
            try:
                self._create_tables(conn)
            finally:
                conn.close()
            self._schema_ready = True


def _safe_json(raw: str, fallback):
    try:
        return json.loads(raw or "")
    except json.JSONDecodeError:
        return fallback


CONFIG_STORE = ConfigStore()
