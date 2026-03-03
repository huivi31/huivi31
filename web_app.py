# -*- coding: utf-8 -*-
"""
多智能体基准测试系统 - Web版服务
核心架构：1个中心质检Agent + N个外围攻击Agent
版本: 2.1.0 - 异步优化+安全增强
"""

from flask import Flask, Response, jsonify, render_template, request, g
import csv
import io
import json
import os
import random
import time
import traceback
import asyncio
from datetime import datetime

try:
    from flask_compress import Compress
except Exception:  # noqa: BLE001
    Compress = None

try:
    from pypdf import PdfReader
except Exception:  # noqa: BLE001
    PdfReader = None

from config import API_CONFIG, APP_VERSION
from config_store import CONFIG_STORE
from user_personas import USER_RELATIONS, COMMUNITY_CONFIG
from rule_engine import RULE_ENGINE
from attack_knowledge import KNOWLEDGE_STORE

# Import from new modules
from agents import (
    SYSTEM_STATE, PERSONA_INDEX, EVENT_BUS,
    AttackAgent, CENTRAL_INSPECTOR,
    get_all_personas, get_technique_library,
    persist_persona_update, persist_technique_update,
    reset_peripheral_agents_state, load_agent_runtime,
    absorb_knowledge_for_all_agents,
    export_peripheral_agents_state, restore_peripheral_agents_state,
)
from battle import (
    run_agent_discussion,
    run_adversarial_battle, run_iterative_optimization,
    run_collaborative_attack, run_red_team_planning,
    OPENCLAW_BOARD
)

# v2.3: 数据库集成和监控
from db_integration import get_db_integration
from database import db
from monitor import get_monitor, get_alerts, record_metric

db_integration = get_db_integration()
monitor = get_monitor()
from orchestrator import CAMPAIGN_ORCHESTRATOR
from alerting import dispatch_regression_alerts
from regression_reporting import (
    evaluate_regression_matrix,
    normalize_thresholds,
    render_regression_markdown,
)

# v2.1.0: 导入安全和中间件模块
from auth import generate_token, authenticate_user, require_auth
from middleware import error_handler, log_request, log_response, rate_limit

app = Flask(__name__)
try:
    _env_upload_mb = int(os.getenv("MAX_DOC_UPLOAD_MB", "1024"))
except (TypeError, ValueError):
    _env_upload_mb = 1024
MAX_DOC_UPLOAD_MB = max(64, _env_upload_mb)
ALLOWED_DOC_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".json",
    ".jsonl",
    ".pdf",
}
app.config["MAX_CONTENT_LENGTH"] = MAX_DOC_UPLOAD_MB * 1024 * 1024

if Compress:
    app.config["COMPRESS_LEVEL"] = 6
    app.config["COMPRESS_MIN_SIZE"] = 500
    app.config["COMPRESS_MIMETYPES"] = [
        "text/html",
        "text/css",
        "application/javascript",
        "application/json",
        "text/plain",
        "text/markdown",
    ]
    Compress(app)

# v2.1.0: 注册中间件
error_handler(app)

# v2.3: 初始化数据库
db.initialize()
db.create_tables()

@app.before_request
def before_request():
    log_request()

@app.after_request
def after_request(response):
    return log_response(response)


def _parse_rules_text(rules_text: str) -> list:
    rules = []
    for i, line in enumerate([l.strip() for l in (rules_text or "").splitlines() if l.strip()]):
        rule_id = f"R{i+1:02d}"
        parts = [p.strip() for p in line.replace("|", " ").split() if p.strip()]
        keywords = []
        for part in parts:
            for token in part.replace("、", ",").split(","):
                token = token.strip()
                if token and token not in keywords:
                    keywords.append(token)
        rules.append({"id": rule_id, "text": line, "keywords": keywords[:5]})
    return rules


def _apply_rules_runtime(
    rules: list,
    *,
    persist: bool = True,
    rules_version: int = None,
    refine: bool = True,
):
    if rules_version is None:
        if persist:
            SYSTEM_STATE["rules_version"] += 1
        rules_version = SYSTEM_STATE["rules_version"]
    else:
        SYSTEM_STATE["rules_version"] = int(rules_version)

    SYSTEM_STATE["rules"] = rules
    RULE_ENGINE.set_rules(rules)
    CENTRAL_INSPECTOR.detection_rules = rules

    if refine:
        CENTRAL_INSPECTOR.refine_rules(rules)
        for rule_id, standard in CENTRAL_INSPECTOR.refined_standards.items():
            refined = standard.get("refined", {})
            for variant_type in ["text_variants", "semantic_bypass"]:
                variants_dict = refined.get(variant_type, {})
                if isinstance(variants_dict, dict):
                    for _vtype, vlist in variants_dict.items():
                        if isinstance(vlist, list):
                            for v in vlist:
                                if v and len(v) >= 2:
                                    RULE_ENGINE.add_custom_variants(
                                        standard.get("original_rule", rule_id), [v]
                                    )
    else:
        CENTRAL_INSPECTOR.refined_standards = {}

    if persist:
        CONFIG_STORE.save_rules(rules, SYSTEM_STATE["rules_version"])


def _bootstrap_runtime_state():
    """Load persisted rule configuration into in-memory runtime state."""
    rules, rules_version = CONFIG_STORE.load_rules()
    _apply_rules_runtime(rules, persist=False, rules_version=rules_version, refine=False)


_bootstrap_runtime_state()


# ==================== 全局错误处理 ====================
@app.errorhandler(Exception)
def handle_error(error):
    """统一错误处理，防止崩溃"""
    error_details = {
        "error": str(error),
        "type": type(error).__name__,
        "timestamp": datetime.now().isoformat(),
    }
    
    # 记录详细错误信息到审计日志
    try:
        _audit(
            event_type="system_error",
            action="exception_caught",
            severity="error",
            details={
                **error_details,
                "traceback": traceback.format_exc()
            }
        )
    except:
        pass  # 审计失败不影响错误响应
    
    # 开发环境显示详细信息，生产环境隐藏
    if app.debug:
        error_details["traceback"] = traceback.format_exc()
    
    return jsonify({
        "success": False,
        "error": error_details
    }), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "API endpoint not found"}), 404


@app.errorhandler(413)
def request_too_large(error):
    return jsonify({
        "success": False,
        "error": f"File too large. Max size: {MAX_DOC_UPLOAD_MB}MB"
    }), 413


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _audit(
    event_type: str,
    action: str,
    actor: str = "system",
    target_type: str = "",
    target_id: str = "",
    severity: str = "info",
    details: dict = None,
):
    CONFIG_STORE.create_audit_log(
        event_type=event_type,
        action=action,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
        severity=severity,
        details=details or {},
    )


def _extract_rules_payload(data: dict):
    rules = []
    source_snapshot_id = ""

    rules_text = (data.get("rules_text") or "").strip()
    if rules_text:
        return _parse_rules_text(rules_text), source_snapshot_id

    snapshot_id = (data.get("snapshot_id") or "").strip()
    if snapshot_id:
        snapshot = CONFIG_STORE.get_rule_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError("snapshot不存在")
        rules = snapshot.get("rules", [])
        source_snapshot_id = snapshot_id
        return rules, source_snapshot_id

    incoming = data.get("rules")
    if isinstance(incoming, list):
        rules = incoming
    if not rules:
        raise ValueError("缺少规则内容，请传rules_text / snapshot_id / rules")
    return rules, source_snapshot_id


def _parse_tags(tags_raw):
    if isinstance(tags_raw, str):
        tags = [t.strip() for t in tags_raw.replace("，", ",").split(",") if t.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(t).strip() for t in tags_raw if str(t).strip()]
    else:
        tags = []
    return tags


def _iter_text_items(text: str):
    if not text:
        return
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            yield line


def _iter_document_items(file_storage, ext: str, feed_type: str):
    ext = (ext or "").lower()
    stream = file_storage.stream
    stream.seek(0)

    if ext == ".pdf":
        if PdfReader is None:
            raise ValueError("服务端未安装 pypdf，暂不支持PDF解析")
        reader = PdfReader(stream)
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            for item in _iter_text_items(text):
                yield item
        return

    if ext == ".csv":
        wrapper = io.TextIOWrapper(stream, encoding="utf-8", errors="ignore", newline="")
        reader = csv.reader(wrapper)
        for row in reader:
            cells = [str(cell).strip() for cell in row if str(cell).strip()]
            if not cells:
                continue
            if feed_type == "cases":
                if len(cells) >= 2:
                    yield {
                        "original": cells[0],
                        "bypass": cells[1],
                        "technique": cells[2] if len(cells) >= 3 else "文档案例",
                    }
                continue
            if feed_type == "slang":
                if len(cells) >= 2:
                    yield f"{cells[0]}={cells[1]}"
                else:
                    yield cells[0]
                continue
            yield " ".join(cells)
        return

    if ext == ".jsonl":
        wrapper = io.TextIOWrapper(stream, encoding="utf-8", errors="ignore")
        for line in wrapper:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = line
            yield payload
        return

    if ext == ".json":
        raw = stream.read()
        text = raw.decode("utf-8", errors="ignore")
        try:
            payload = json.loads(text)
            if isinstance(payload, list):
                for item in payload:
                    yield item
                return
            if isinstance(payload, dict):
                items = payload.get("items")
                if isinstance(items, list):
                    for item in items:
                        yield item
                    return
                yield payload
                return
        except json.JSONDecodeError:
            pass
        for item in _iter_text_items(text):
            yield item
        return

    wrapper = io.TextIOWrapper(stream, encoding="utf-8", errors="ignore")
    for line in wrapper:
        line = line.strip()
        if line:
            yield line


def _normalize_document_item(item, feed_type: str):
    if feed_type == "materials":
        if isinstance(item, dict):
            text = (
                item.get("text")
                or item.get("content")
                or item.get("bypass")
                or item.get("original")
                or ""
            )
            return str(text).strip() or None
        if isinstance(item, str):
            return item.strip() or None
        return str(item).strip() or None

    if feed_type == "slang":
        if isinstance(item, dict):
            term = str(item.get("term", "")).strip()
            meaning = str(item.get("meaning", "")).strip()
            if term:
                return f"{term}={meaning}" if meaning else term
            text = item.get("text") or item.get("content")
            return str(text).strip() or None
        if isinstance(item, str):
            return item.strip() or None
        return str(item).strip() or None

    if feed_type == "cases":
        if isinstance(item, dict):
            bypass = str(item.get("bypass", "")).strip()
            original = str(item.get("original", "")).strip()
            technique = str(item.get("technique", "文档案例")).strip() or "文档案例"
            if bypass:
                return {"original": original, "bypass": bypass, "technique": technique}
            text = str(item.get("text") or item.get("content") or "").strip()
            if text:
                return {"original": "", "bypass": text, "technique": technique}
            return None
        if isinstance(item, str):
            text = item.strip()
            if text:
                return {"original": "", "bypass": text, "technique": "文档案例"}
            return None
    return None


def _feed_batch(feed_type: str, items: list, category: str, source: str, tags: list) -> int:
    if not items:
        return 0
    if feed_type == "materials":
        return KNOWLEDGE_STORE.feed_materials(items, category=category, source=source, tags=tags)
    if feed_type == "slang":
        return KNOWLEDGE_STORE.feed_slang(items, source=source, tags=tags)
    if feed_type == "cases":
        return KNOWLEDGE_STORE.feed_cases(items, source=source, tags=tags)
    return 0


@app.after_request
def apply_response_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.path == "/" and response.status_code == 200:
        response.headers.setdefault("Cache-Control", "public, max-age=120")
    elif request.path.startswith("/events"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(413)
def handle_payload_too_large(_exc):
    return jsonify({"error": f"文件太大，当前上限 {MAX_DOC_UPLOAD_MB}MB"}), 413

# ============================================================================
# API路由
# ============================================================================

# v2.1.0: 认证端点
@app.post("/api/auth/login")
@rate_limit(max_requests=10, window=60)
def api_login():
    """
    用户登录
    
    Body:
        {
            "username": "demo",
            "password": "demo123"
        }
    
    Response:
        {
            "success": true,
            "token": "eyJ...",
            "user_id": "demo",
            "role": "user"
        }
    """
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        return jsonify({
            "success": False,
            "error": "Username and password are required",
            "code": "INVALID_INPUT"
        }), 400
    
    user = authenticate_user(username, password)
    
    if not user:
        return jsonify({
            "success": False,
            "error": "Invalid username or password",
            "code": "AUTH_FAILED"
        }), 401
    
    token = generate_token(user["user_id"], user["role"])
    
    return jsonify({
        "success": True,
        "token": token,
        "user_id": user["user_id"],
        "role": user["role"]
    })


@app.get("/api/auth/test")
@require_auth
def api_auth_test():
    """测试认证是否有效"""
    return jsonify({
        "success": True,
        "message": "Authentication successful",
        "user_id": request.user_id,
        "role": request.user_role
    })


@app.get("/")
def index():
    return render_template(
        "index.html",
        personas=get_all_personas(),
        relations=USER_RELATIONS,
        provider=API_CONFIG.get("provider", "gemini"),
        community_config=COMMUNITY_CONFIG,
        doc_upload_max_mb=MAX_DOC_UPLOAD_MB,
    )


@app.get("/dashboard")
def dashboard():
    """v2.3: 系统监控Dashboard"""
    return render_template("dashboard.html")


@app.get("/batch-test")
def batch_test_page():
    """v2.3: 批量测试页面"""
    return render_template("batch_test.html")


@app.get("/api-docs")
def api_docs_page():
    """v2.3: API文档页面"""
    return render_template("api_docs.html")


@app.post("/rules")
def set_rules():
    """设置审核规则"""
    data = request.json or {}
    rules_text = (data.get("rules_text") or "").strip()
    actor = (data.get("actor") or "api").strip()
    rules = _parse_rules_text(rules_text)
    _apply_rules_runtime(rules, persist=True, refine=True)
    _audit(
        event_type="rule_update",
        action="set_rules",
        actor=actor,
        target_type="rules_state",
        target_id=f"v{SYSTEM_STATE['rules_version']}",
        details={"rules_count": len(rules)},
    )
    
    return jsonify({
        "status": "ok",
        "rules_count": len(rules),
        "rules_version": SYSTEM_STATE["rules_version"],
        "refined_standards": len(CENTRAL_INSPECTOR.refined_standards)
    })


@app.get("/rules")
def get_rules():
    """获取当前规则"""
    return jsonify({
        "rules": SYSTEM_STATE["rules"],
        "rules_count": len(SYSTEM_STATE["rules"]),
        "rules_version": SYSTEM_STATE["rules_version"],
        "refined_standards": CENTRAL_INSPECTOR.refined_standards,  # 包含详细拆解
    })


@app.post("/rules/snapshots")
def create_rule_snapshot():
    """创建规则快照，用于回归和A/B测试。"""
    data = request.json or {}
    name = (data.get("name") or f"rules-v{SYSTEM_STATE.get('rules_version', 0)}").strip()
    metadata = data.get("metadata") or {}
    actor = (data.get("actor") or "api").strip()

    rules_text = (data.get("rules_text") or "").strip()
    if rules_text:
        rules = _parse_rules_text(rules_text)
        version = int(data.get("rules_version") or SYSTEM_STATE.get("rules_version", 0) + 1)
    else:
        rules = SYSTEM_STATE.get("rules", [])
        version = SYSTEM_STATE.get("rules_version", 0)

    snapshot_id = CONFIG_STORE.create_rule_snapshot(
        name=name,
        rules=rules,
        rules_version=version,
        metadata=metadata,
    )
    _audit(
        event_type="rule_snapshot",
        action="create_snapshot",
        actor=actor,
        target_type="rule_snapshot",
        target_id=snapshot_id,
        details={"rules_count": len(rules), "rules_version": version},
    )
    return jsonify(
        {
            "status": "ok",
            "snapshot_id": snapshot_id,
            "name": name,
            "rules_count": len(rules),
            "rules_version": version,
        }
    )


@app.get("/rules/snapshots")
def list_rule_snapshots():
    """列出规则快照。"""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"snapshots": CONFIG_STORE.list_rule_snapshots(limit=limit)})


@app.post("/rules/snapshots/<snapshot_id>/apply")
def apply_rule_snapshot(snapshot_id: str):
    """应用规则快照到当前系统。"""
    snapshot = CONFIG_STORE.get_rule_snapshot(snapshot_id)
    if not snapshot:
        return jsonify({"error": "snapshot not found"}), 404

    _apply_rules_runtime(
        snapshot.get("rules", []),
        persist=True,
        rules_version=snapshot.get("rules_version", SYSTEM_STATE.get("rules_version", 0)),
        refine=True,
    )
    _audit(
        event_type="rule_snapshot",
        action="apply_snapshot",
        actor=(request.json or {}).get("actor", "api"),
        target_type="rule_snapshot",
        target_id=snapshot_id,
        details={"rules_count": len(snapshot.get("rules", [])), "rules_version": SYSTEM_STATE.get("rules_version", 0)},
    )
    return jsonify(
        {
            "status": "ok",
            "snapshot_id": snapshot_id,
            "rules_count": len(snapshot.get("rules", [])),
            "rules_version": SYSTEM_STATE.get("rules_version", 0),
        }
    )


@app.post("/rules/change-requests")
def create_rule_change_request():
    """创建规则变更申请（待审批）。"""
    data = request.json or {}
    title = (data.get("title") or f"rule-change-{int(time.time())}").strip()
    description = (data.get("description") or "").strip()
    proposer = (data.get("proposer") or "operator").strip()
    risk_level = (data.get("risk_level") or "medium").strip()
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

    try:
        rules, source_snapshot_id = _extract_rules_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    suggested_version = int(
        data.get("proposed_rules_version") or max(1, SYSTEM_STATE.get("rules_version", 0) + 1)
    )
    request_id = CONFIG_STORE.create_rule_change_request(
        title=title,
        proposer=proposer,
        proposed_rules=rules,
        proposed_rules_version=suggested_version,
        description=description,
        source_snapshot_id=source_snapshot_id,
        risk_level=risk_level,
        metadata=metadata,
    )
    _audit(
        event_type="rule_change_request",
        action="create",
        actor=proposer,
        target_type="rule_change_request",
        target_id=request_id,
        details={
            "risk_level": risk_level,
            "rules_count": len(rules),
            "proposed_rules_version": suggested_version,
            "source_snapshot_id": source_snapshot_id,
        },
    )
    EVENT_BUS.emit(
        "rule_change_requested",
        {"request_id": request_id, "title": title, "proposer": proposer, "risk_level": risk_level},
    )
    item = CONFIG_STORE.get_rule_change_request(request_id)
    return jsonify({"status": "pending", "request": item}), 201


@app.get("/rules/change-requests")
def list_rule_change_requests():
    """列出规则变更申请。"""
    status = (request.args.get("status") or "").strip()
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"requests": CONFIG_STORE.list_rule_change_requests(status=status, limit=limit)})


@app.get("/rules/change-requests/<request_id>")
def get_rule_change_request(request_id: str):
    """查看单个规则变更申请。"""
    item = CONFIG_STORE.get_rule_change_request(request_id)
    if not item:
        return jsonify({"error": "request not found"}), 404
    return jsonify(item)


@app.post("/rules/change-requests/<request_id>/review")
def review_rule_change_request(request_id: str):
    """审批规则变更申请（approved / rejected）。"""
    data = request.json or {}
    decision = (data.get("decision") or data.get("status") or "").strip().lower()
    reviewer = (data.get("reviewer") or "reviewer").strip()
    comment = (data.get("comment") or "").strip()
    if decision not in {"approved", "rejected"}:
        return jsonify({"error": "decision必须是approved或rejected"}), 400

    try:
        item = CONFIG_STORE.review_rule_change_request(
            request_id=request_id,
            decision=decision,
            reviewer=reviewer,
            comment=comment,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not item:
        return jsonify({"error": "request not found"}), 404

    _audit(
        event_type="rule_change_request",
        action=f"review:{decision}",
        actor=reviewer,
        target_type="rule_change_request",
        target_id=request_id,
        details={"comment": comment},
        severity="warning" if decision == "rejected" else "info",
    )
    EVENT_BUS.emit(
        "rule_change_reviewed",
        {
            "request_id": request_id,
            "decision": decision,
            "reviewer": reviewer,
            "comment": comment,
        },
    )
    return jsonify({"status": decision, "request": item})


@app.post("/rules/change-requests/<request_id>/apply")
def apply_rule_change_request(request_id: str):
    """应用已审批的规则变更。"""
    data = request.json or {}
    actor = (data.get("actor") or "operator").strip()
    comment = (data.get("comment") or "").strip()
    allow_force = _as_bool(data.get("force"), False)

    item = CONFIG_STORE.get_rule_change_request(request_id)
    if not item:
        return jsonify({"error": "request not found"}), 404

    status = item.get("status")
    if status not in {"approved", "applied"} and not allow_force:
        return jsonify({"error": "request未审批，需先approved或force=true"}), 400

    proposed_rules = item.get("proposed_rules", [])
    if not isinstance(proposed_rules, list) or not proposed_rules:
        return jsonify({"error": "request中没有可应用的规则"}), 400

    target_version = int(item.get("proposed_rules_version") or 0)
    if target_version <= SYSTEM_STATE.get("rules_version", 0):
        target_version = int(SYSTEM_STATE.get("rules_version", 0) + 1)

    _apply_rules_runtime(
        proposed_rules,
        persist=True,
        rules_version=target_version,
        refine=True,
    )
    updated = CONFIG_STORE.mark_rule_change_request_applied(
        request_id=request_id,
        actor=actor,
        comment=comment or f"applied by {actor}",
    )
    _audit(
        event_type="rule_change_request",
        action="apply",
        actor=actor,
        target_type="rule_change_request",
        target_id=request_id,
        details={
            "rules_count": len(proposed_rules),
            "rules_version": SYSTEM_STATE.get("rules_version", 0),
            "force": allow_force,
        },
    )
    EVENT_BUS.emit(
        "rule_change_applied",
        {
            "request_id": request_id,
            "actor": actor,
            "rules_version": SYSTEM_STATE.get("rules_version", 0),
            "rules_count": len(proposed_rules),
        },
    )
    return jsonify(
        {
            "status": "applied",
            "request": updated or item,
            "rules_version": SYSTEM_STATE.get("rules_version", 0),
            "rules_count": len(SYSTEM_STATE.get("rules", [])),
        }
    )


@app.get("/techniques")
def list_techniques():
    """获取当前攻击技法库（来自持久化配置）"""
    techniques = []
    for category, items in get_technique_library().items():
        for name, details in items.items():
            item = {
                "name": name,
                "category": category,
            }
            if isinstance(details, dict):
                item.update(details)
            techniques.append(item)

    return jsonify({
        "techniques": techniques,
        "total_count": len(techniques),
    })


@app.post("/techniques")
def upsert_technique():
    """新增或更新攻击技法定义"""
    data = request.json or {}
    category = (data.get("category") or "").strip()
    name = (data.get("name") or "").strip()
    if not category or not name:
        return jsonify({"error": "缺少category或name"}), 400

    details = {k: v for k, v in data.items() if k not in {"category", "name"}}
    persist_technique_update(category=category, name=name, details=details)

    total_count = sum(len(v) for v in get_technique_library().values())
    return jsonify({
        "status": "ok",
        "message": f"技法 {name} 已保存",
        "total_count": total_count,
    })


@app.post("/battle/run")
def run_battle():
    """运行单次对抗"""
    data = request.json or {}
    persona_id = data.get("persona_id", "")
    target_keyword = data.get("target_keyword")
    iteration = data.get("iteration", 0)
    
    if not persona_id:
        return jsonify({"error": "缺少persona_id"}), 400
    
    result = run_adversarial_battle(persona_id, target_keyword, iteration)
    return jsonify(result)


@app.post("/battle/iterate")
def run_iteration():
    """运行迭代优化对抗"""
    data = request.json or {}
    persona_id = data.get("persona_id", "")
    target_keyword = data.get("target_keyword")
    max_iterations = data.get("max_iterations", 3)
    
    if not persona_id:
        return jsonify({"error": "缺少persona_id"}), 400
    
    result = run_iterative_optimization(persona_id, target_keyword, max_iterations)
    return jsonify(result)


@app.post("/battle/collaborate")
def run_collaboration():
    """运行协作攻击"""
    data = request.json or {}
    agent_ids = data.get("agent_ids", [])
    target_keyword = data.get("target_keyword")
    
    if not agent_ids:
        return jsonify({"error": "缺少agent_ids"}), 400
    
    result = run_collaborative_attack(agent_ids, target_keyword)
    return jsonify(result)


@app.get("/battle/history")
def get_battle_history():
    """获取对抗历史"""
    limit = request.args.get("limit", 50, type=int)
    history = SYSTEM_STATE["battle_history"][-limit:]
    return jsonify({
        "history": history,
        "total_count": len(SYSTEM_STATE["battle_history"]),
    })


@app.post("/api/battle/batch")
@rate_limit(max_requests=5, window=60)
def api_batch_battle():
    """
    批量运行Agent攻击测试 (v2.2.0新增)
    
    Body:
        {
            "topic": "测试主题",
            "agent_count": 72,  // 可选,默认全部
            "agent_ids": [],    // 可选,指定Agent列表
            "timeout": 30       // 可选,超时时间(秒)
        }
    
    Response:
        {
            "success": true,
            "summary": {
                "total": 72,
                "bypassed": 15,
                "detected": 57,
                "bypass_rate": 0.208,
                "duration": 12.5
            },
            "results": [...],
            "technique_stats": {...},
            "layer_stats": {...}
        }
    """
    data = request.get_json() or {}
    topic = data.get("topic", "").strip()
    agent_count = data.get("agent_count", None)
    agent_ids = data.get("agent_ids", [])
    timeout = data.get("timeout", 30)
    
    if not topic:
        return jsonify({
            "success": False,
            "error": "Missing required field: topic",
            "code": "INVALID_INPUT"
        }), 400
    
    try:
        import time
        from collections import defaultdict
        
        start_time = time.time()
        
        # 获取要测试的Agent列表
        all_personas = get_all_personas()
        
        if agent_ids:
            # 使用指定的Agent
            test_personas = [p for p in all_personas if p.get("id") in agent_ids]
        elif agent_count:
            # 随机选择指定数量
            import random
            test_personas = random.sample(all_personas, min(agent_count, len(all_personas)))
        else:
            # 全部Agent
            test_personas = all_personas
        
        if not test_personas:
            return jsonify({
                "success": False,
                "error": "No agents available for testing",
                "code": "NO_AGENTS"
            }), 400
        
        # 运行批量攻击
        results = []
        technique_stats = defaultdict(lambda: {"total": 0, "bypassed": 0})
        layer_stats = defaultdict(int)
        
        for persona in test_personas:
            persona_id = persona.get("id")
            if not persona_id:
                continue
            
            try:
                # 运行单次攻击
                result = run_adversarial_battle(persona_id, topic, 0)
                
                # 收集结果
                results.append({
                    "agent_id": persona_id,
                    "agent_name": persona.get("name", "Unknown"),
                    "technique": result.get("technique", "未知"),
                    "content": result.get("content", "")[:100],  # 限制长度
                    "bypass_success": result.get("result", {}).get("bypass_success", False),
                    "blocked_at": result.get("result", {}).get("blocked_at"),
                    "complexity": result.get("complexity", 0)
                })
                
                # 统计技巧
                tech = result.get("technique", "未知")
                technique_stats[tech]["total"] += 1
                if result.get("result", {}).get("bypass_success"):
                    technique_stats[tech]["bypassed"] += 1
                
                # 统计拦截层
                blocked_at = result.get("result", {}).get("blocked_at")
                if blocked_at:
                    layer_stats[blocked_at] += 1
                
            except Exception as e:
                # 记录错误但继续
                results.append({
                    "agent_id": persona_id,
                    "agent_name": persona.get("name", "Unknown"),
                    "error": str(e)[:100]
                })
        
        duration = time.time() - start_time
        
        # 计算统计数据
        total = len(results)
        bypassed = sum(1 for r in results if r.get("bypass_success"))
        detected = total - bypassed
        bypass_rate = (bypassed / total) if total > 0 else 0
        
        # 处理technique_stats,计算成功率
        technique_summary = {}
        for tech, stats in technique_stats.items():
            rate = (stats["bypassed"] / stats["total"]) if stats["total"] > 0 else 0
            technique_summary[tech] = {
                "total": stats["total"],
                "bypassed": stats["bypassed"],
                "success_rate": round(rate, 3)
            }
        
        return jsonify({
            "success": True,
            "summary": {
                "total": total,
                "bypassed": bypassed,
                "detected": detected,
                "bypass_rate": round(bypass_rate, 3),
                "duration": round(duration, 2)
            },
            "results": results,
            "technique_stats": technique_summary,
            "layer_stats": dict(layer_stats)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "BATCH_TEST_FAILED"
        }), 500


@app.get("/api/stats/summary")
def api_stats_summary():
    """
    获取系统统计摘要 (v2.2.0新增)
    
    Query:
        ?limit=100  // 分析最近N条历史记录
    
    Response:
        {
            "success": true,
            "overall": {
                "total_attacks": 100,
                "bypass_rate": 0.21,
                "avg_complexity": 3.5
            },
            "by_technique": {...},
            "by_layer": {...},
            "top_agents": [...]
        }
    """
    limit = request.args.get("limit", 100, type=int)
    history = SYSTEM_STATE["battle_history"][-limit:]
    
    if not history:
        return jsonify({
            "success": True,
            "overall": {
                "total_attacks": 0,
                "bypass_rate": 0,
                "avg_complexity": 0
            },
            "by_technique": {},
            "by_layer": {},
            "top_agents": []
        })
    
    from collections import defaultdict
    
    # 总体统计
    total = len(history)
    bypassed = sum(1 for h in history if h.get("result", {}).get("bypass_success"))
    bypass_rate = (bypassed / total) if total > 0 else 0
    
    complexities = [h.get("complexity", 0) for h in history if "complexity" in h]
    avg_complexity = (sum(complexities) / len(complexities)) if complexities else 0
    
    # 按技巧统计
    technique_stats = defaultdict(lambda: {"total": 0, "bypassed": 0})
    for h in history:
        tech = h.get("technique", "未知")
        technique_stats[tech]["total"] += 1
        if h.get("result", {}).get("bypass_success"):
            technique_stats[tech]["bypassed"] += 1
    
    by_technique = {}
    for tech, stats in technique_stats.items():
        rate = (stats["bypassed"] / stats["total"]) if stats["total"] > 0 else 0
        by_technique[tech] = {
            "total": stats["total"],
            "bypassed": stats["bypassed"],
            "success_rate": round(rate, 3)
        }
    
    # 按拦截层统计
    layer_stats = defaultdict(int)
    for h in history:
        layer = h.get("result", {}).get("blocked_at")
        if layer:
            layer_stats[layer] += 1
        elif h.get("result", {}).get("bypass_success"):
            layer_stats["bypassed"] += 1
    
    # Top Agent统计
    agent_stats = defaultdict(lambda: {"total": 0, "bypassed": 0})
    for h in history:
        agent_id = h.get("persona_id", "unknown")
        agent_stats[agent_id]["total"] += 1
        if h.get("result", {}).get("bypass_success"):
            agent_stats[agent_id]["bypassed"] += 1
    
    top_agents = []
    for agent_id, stats in sorted(agent_stats.items(), 
                                   key=lambda x: x[1]["bypassed"], 
                                   reverse=True)[:10]:
        rate = (stats["bypassed"] / stats["total"]) if stats["total"] > 0 else 0
        top_agents.append({
            "agent_id": agent_id,
            "total": stats["total"],
            "bypassed": stats["bypassed"],
            "success_rate": round(rate, 3)
        })
    
    return jsonify({
        "success": True,
        "overall": {
            "total_attacks": total,
            "bypass_rate": round(bypass_rate, 3),
            "avg_complexity": round(avg_complexity, 2),
            "bypassed_count": bypassed,
            "detected_count": total - bypassed
        },
        "by_technique": by_technique,
        "by_layer": dict(layer_stats),
        "top_agents": top_agents
    })


@app.get("/board/data")
def get_board_data():
    """获取OpenClaw Board数据"""
    return jsonify({
        "intel_feed": OPENCLAW_BOARD.intel_feed[-50:],  # Return last 50 items
        "active_plans": OPENCLAW_BOARD.active_plans,
        "rule_profile": OPENCLAW_BOARD.rule_profile,
        "stats": {
            "intel_count": len(OPENCLAW_BOARD.intel_feed),
            "plans_count": sum(len(p) for p in OPENCLAW_BOARD.active_plans.values())
        }
    })


@app.post("/battle/planning")
def run_planning():
    """运行红队策划会议"""
    data = request.json or {}
    topic = data.get("topic", "通用话题")
    
    result = run_red_team_planning(topic)
    return jsonify(result)


@app.get("/inspector/stats")
def get_inspector_stats():
    """获取中心Agent统计"""
    return jsonify({
        "stats": CENTRAL_INSPECTOR.get_stats(),
        "refined_standards_count": len(CENTRAL_INSPECTOR.refined_standards),
    })


# ============================================================================
# v2.3: 数据库管理API
# ============================================================================

@app.post("/api/db/migrate")
@require_auth
def api_db_migrate():
    """
    迁移现有battle_history到数据库
    
    Response:
        {
            "success": true,
            "migrated_count": 100,
            "message": "Successfully migrated 100 records"
        }
    """
    try:
        history = SYSTEM_STATE.get("battle_history", [])
        count = db_integration.migrate_battle_history(history)
        
        return jsonify({
            "success": True,
            "migrated_count": count,
            "message": f"Successfully migrated {count} records to database"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "MIGRATION_FAILED"
        }), 500


@app.get("/api/db/battle/history")
def api_db_battle_history():
    """
    从数据库获取攻击历史记录
    
    Query:
        ?limit=100&offset=0
    
    Response:
        {
            "success": true,
            "records": [...],
            "total": 100
        }
    """
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    
    try:
        records = db_integration.get_battle_history(limit=limit, offset=offset)
        
        return jsonify({
            "success": True,
            "records": records,
            "total": len(records),
            "limit": limit,
            "offset": offset
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "QUERY_FAILED"
        }), 500


@app.get("/api/db/battle/stats")
def api_db_battle_stats():
    """
    从数据库获取攻击统计
    
    Query:
        ?hours=24
    
    Response:
        {
            "success": true,
            "stats": {...}
        }
    """
    hours = request.args.get("hours", 24, type=int)
    
    try:
        stats = db_integration.get_battle_stats(hours=hours)
        
        return jsonify({
            "success": True,
            "stats": stats,
            "time_range": f"Last {hours} hours"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "STATS_FAILED"
        }), 500


@app.get("/api/db/health")
def api_db_health():
    """
    数据库健康检查
    
    Response:
        {
            "success": true,
            "status": "healthy",
            "info": {...}
        }
    """
    try:
        health = db.health_check()
        
        return jsonify({
            "success": health["healthy"],
            "status": "healthy" if health["healthy"] else "unhealthy",
            "info": health
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "status": "error",
            "error": str(e),
            "code": "HEALTH_CHECK_FAILED"
        }), 500


@app.get("/api/agent/<agent_id>/memory")
def api_agent_memory(agent_id: str):
    """
    获取Agent记忆
    
    Response:
        {
            "success": true,
            "short_term": [...],
            "long_term_summary": {...},
            "successful_patterns": [...]
        }
    """
    try:
        memory = db_integration.get_agent_memory(agent_id)
        
        short_term = memory.get_short_term()
        successful = memory.get_successful_patterns(limit=10)
        
        return jsonify({
            "success": True,
            "agent_id": agent_id,
            "short_term_count": len(short_term),
            "short_term": short_term[:20],  # 只返回最近20条
            "successful_patterns": successful
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "MEMORY_QUERY_FAILED"
        }), 500


# ============================================================================
# v2.3: 监控告警API
# ============================================================================

@app.get("/api/monitor/alerts")
def api_monitor_alerts():
    """
    获取监控告警列表
    
    Query:
        ?level=warning&limit=50
    
    Response:
        {
            "success": true,
            "alerts": [...]
        }
    """
    level = request.args.get("level")
    limit = request.args.get("limit", 50, type=int)
    
    try:
        alerts = get_alerts(level=level, limit=limit)
        return jsonify({
            "success": True,
            "alerts": alerts,
            "count": len(alerts)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "ALERTS_QUERY_FAILED"
        }), 500


@app.get("/api/monitor/stats")
def api_monitor_stats():
    """
    获取监控统计
    
    Response:
        {
            "success": true,
            "stats": {...}
        }
    """
    try:
        stats = monitor.get_stats()
        
        # 添加最新指标值
        stats["latest_metrics"] = {
            "bypass_rate": monitor.get_latest_metric("bypass_success"),
            "avg_processing_time": monitor.get_latest_metric("processing_time"),
            "avg_complexity": monitor.get_latest_metric("complexity")
        }
        
        return jsonify({
            "success": True,
            "stats": stats
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "MONITOR_STATS_FAILED"
        }), 500


@app.post("/api/monitor/rules")
@require_auth
def api_add_alert_rule():
    """
    添加自定义告警规则
    
    Body:
        {
            "name": "rule_name",
            "metric": "bypass_rate",
            "threshold": 0.7,
            "operator": ">",
            "level": "warning",
            "message": "Custom message"
        }
    
    Response:
        {
            "success": true,
            "message": "Alert rule added"
        }
    """
    try:
        data = request.json or {}
        
        monitor.add_alert_rule(
            name=data.get("name"),
            metric=data.get("metric"),
            threshold=float(data.get("threshold", 0)),
            operator=data.get("operator", ">"),
            level=data.get("level", "warning"),
            message=data.get("message", "")
        )
        
        return jsonify({
            "success": True,
            "message": "Alert rule added successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "code": "ADD_RULE_FAILED"
        }), 500


@app.get("/agent/<persona_id>/state")
def get_agent_state(persona_id: str):
    """获取外围Agent状态"""
    persona = PERSONA_INDEX.get(persona_id)
    if not persona:
        return jsonify({"error": "Agent不存在"}), 404
    
    agent = AttackAgent(persona)
    load_agent_runtime(agent)
    
    return jsonify(agent.get_state())


@app.get("/agent/<persona_id>/techniques/unlocked")
def get_agent_unlocked_techniques(persona_id: str):
    """查看Agent当前已解锁技法（按能力阶段）。"""
    persona = PERSONA_INDEX.get(persona_id)
    if not persona:
        return jsonify({"error": "Agent不存在"}), 404

    agent = AttackAgent(persona)
    load_agent_runtime(agent)
    profile = agent.get_technique_profile()

    detail_map = {}
    for category, items in get_technique_library().items():
        if not isinstance(items, dict):
            continue
        for name, meta in items.items():
            detail_map[name] = {"category": category, **(meta if isinstance(meta, dict) else {})}

    ordered = []
    for item in profile.get("ordered", []):
        name = item.get("name")
        detail = detail_map.get(name, {})
        ordered.append(
            {
                "name": name,
                "category": item.get("category", detail.get("category", "")),
                "min_level": item.get("min_level", detail.get("difficulty", 1)),
                "score": item.get("score", 0),
                "desc": detail.get("desc", ""),
                "difficulty": detail.get("difficulty", item.get("min_level", 1)),
            }
        )

    return jsonify(
        {
            "persona_id": persona_id,
            "name": persona.get("name", ""),
            "effective_level": profile.get("effective_level", 1),
            "capability_score": round(agent.capability_score, 3),
            "knowledge_depth": agent.knowledge_depth,
            "unlocked_count": len(profile.get("unlocked", [])),
            "advanced_count": len(profile.get("advanced", [])),
            "techniques": ordered,
        }
    )


@app.post("/agent/<persona_id>/config")
def update_agent_config(persona_id: str):
    """更新Agent配置"""
    persona = PERSONA_INDEX.get(persona_id)
    if not persona:
        return jsonify({"error": "Agent不存在"}), 404
    
    config = request.json
    if not config:
        return jsonify({"error": "无效的配置数据"}), 400
    
    # 更新persona的字段
    updateable_fields = [
        "name", "category", "description", "skill_level", "stealth_rating",
        "behavior_patterns", "background", "core_ability", "attack_strategy",
        "variant_instructions", "chain_of_thought", "output_requirements"
    ]
    
    for field in updateable_fields:
        if field in config:
            persona[field] = config[field]

    persist_persona_update(persona)
    
    return jsonify({
        "success": True,
        "message": f"Agent {persona.get('name', persona_id)} 配置已更新",
        "updated_fields": [f for f in updateable_fields if f in config]
    })


@app.get("/agents/progression")
def get_agents_progression():
    """查看全体Agent进化看板。"""
    states = []
    for persona in get_all_personas():
        agent = AttackAgent(persona)
        load_agent_runtime(agent)
        profile = agent.get_technique_profile()
        states.append(
            {
                "persona_id": persona.get("id", ""),
                "name": persona.get("name", ""),
                "category": persona.get("category", ""),
                "evolution_level": agent.evolution_level,
                "effective_level": profile.get("effective_level", 1),
                "capability_score": round(agent.capability_score, 3),
                "knowledge_depth": agent.knowledge_depth,
                "learning_points": agent.learning_points,
                "learned_techniques_count": len(agent.learned_techniques),
                "unlocked_techniques_count": len(profile.get("unlocked", [])),
                "advanced_techniques_count": len(profile.get("advanced", [])),
            }
        )

    states.sort(
        key=lambda x: (
            -x.get("effective_level", 0),
            -x.get("capability_score", 0),
            -x.get("knowledge_depth", 0),
        )
    )

    by_level = {}
    for item in states:
        level_key = str(item.get("effective_level", 1))
        by_level[level_key] = by_level.get(level_key, 0) + 1

    return jsonify(
        {
            "agents": states,
            "total_agents": len(states),
            "distribution_by_effective_level": by_level,
        }
    )


@app.get("/agents/states")
def get_all_agent_states():
    """获取所有外围Agent状态"""
    states = []
    for persona in get_all_personas():
        agent = AttackAgent(persona)
        load_agent_runtime(agent)
        states.append(agent.get_state())
    
    return jsonify({
        "agents": states,
        "total_agents": len(states),
    })


@app.get("/events")
def get_events():
    """获取实时事件流"""
    since = request.args.get("since", 0, type=float)
    count = request.args.get("count", 50, type=int)
    events = EVENT_BUS.get_recent(count, since)
    return jsonify({
        "events": events,
        "count": len(events),
        "latest_timestamp": events[-1]["timestamp"] if events else 0
    })


@app.post("/discussion/start")
def start_discussion():
    """启动Agent间讨论"""
    data = request.json or {}
    topic = data.get("topic", "如何绕过审核")
    agent_ids = data.get("agent_ids", [])
    technique = data.get("technique")
    
    if not agent_ids:
        # 随机选择几个Agent
        agent_ids = random.sample(list(PERSONA_INDEX.keys()), min(3, len(PERSONA_INDEX)))
    
    discussions = run_agent_discussion(agent_ids, topic, technique)
    
    return jsonify({
        "status": "ok",
        "topic": topic,
        "participants": agent_ids,
        "discussions": discussions,
        "total_dialogues": sum(len(d.get("dialogue", [])) for d in discussions)
    })


@app.post("/meeting/start")
def start_meeting():
    """召开反贼策略会议"""
    data = request.json or {}
    topic = data.get("topic", "如何绕过内容审核")
    
    result = run_red_team_planning(topic)
    
    return jsonify(result)


@app.post("/system/reset")
def reset_system():
    """重置系统状态"""
    # Reset system state in agents module
    SYSTEM_STATE["central_agent"]["detection_rules"] = []
    SYSTEM_STATE["central_agent"]["refined_standards"] = {}
    SYSTEM_STATE["central_agent"]["detection_stats"] = {
        "total_checked": 0,
        "total_detected": 0,
        "total_bypassed": 0,
        "by_technique": {},
        "by_keyword": {},
    }
    reset_peripheral_agents_state()
    SYSTEM_STATE["battle_history"] = []
    SYSTEM_STATE["rules"] = []
    SYSTEM_STATE["rules_version"] = 0
    CONFIG_STORE.clear_rules()
    
    CENTRAL_INSPECTOR.reset_stats()
    CENTRAL_INSPECTOR.detection_rules = []
    CENTRAL_INSPECTOR.refined_standards = {}
    RULE_ENGINE.reset_stats()
    RULE_ENGINE.set_rules([])
    RULE_ENGINE.custom_variants = {}
    KNOWLEDGE_STORE.clear()
    
    return jsonify({"status": "reset", "message": "系统已重置"})


@app.get("/health")
def health():
    """增强的健康检查，返回系统状态"""
    try:
        # 检查关键组件
        rule_count = len(SYSTEM_STATE.get("rules", []))
        agent_count = len(get_all_personas())
        
        # 安全获取知识库数量
        try:
            knowledge_count = len(KNOWLEDGE_STORE.fed_materials)
        except AttributeError:
            knowledge_count = 0
        
        return jsonify({
            "status": "ok",
            "version": APP_VERSION,
            "timestamp": datetime.now().isoformat(),
            "system": {
                "rules": rule_count,
                "agents": agent_count,
                "knowledge_items": knowledge_count,
                "rules_version": SYSTEM_STATE.get("rules_version", 0)
            },
            "uptime": True
        })
    except Exception as e:
        return jsonify({
            "status": "degraded",
            "error": str(e)
        }), 500


# ============================================================================
# 知识投喂 API
# ============================================================================

@app.post("/knowledge/feed")
def feed_knowledge():
    """投喂攻击资料给所有Agent学习"""
    data = request.json or {}
    feed_type = data.get("type", "materials")  # materials / slang / cases
    content = data.get("content", "")
    items = data.get("items", [])
    source = (data.get("source") or "manual").strip()
    category = (data.get("category") or "通用").strip()
    tags = _parse_tags(data.get("tags", []))
    
    result = {"fed_count": 0, "type": feed_type}
    
    if feed_type == "materials":
        # 文本资料：每行一条
        if content:
            texts = [line.strip() for line in content.splitlines() if line.strip()]
        else:
            texts = items
        count = KNOWLEDGE_STORE.feed_materials(
            texts,
            category=category,
            source=source,
            tags=tags,
        )
        result["fed_count"] = count
    
    elif feed_type == "slang":
        # 行业黑话："词=含义" 格式，每行一条
        if content:
            entries = [line.strip() for line in content.splitlines() if line.strip()]
        else:
            entries = items
        count = KNOWLEDGE_STORE.feed_slang(entries, source=source, tags=tags)
        result["fed_count"] = count
        
        # 黑话同时加入规则引擎的自定义变体
        for entry in entries:
            if isinstance(entry, str) and ("=" in entry or "→" in entry):
                sep = "=" if "=" in entry else "→"
                parts = entry.split(sep, 1)
                if len(parts) == 2:
                    RULE_ENGINE.add_custom_variants(parts[1].strip(), [parts[0].strip()])
    
    elif feed_type == "cases":
        # 绕过案例
        if isinstance(items, list):
            count = KNOWLEDGE_STORE.feed_cases(items, source=source, tags=tags)
            result["fed_count"] = count

    # 投喂后触发全体攻击体能力吸收
    absorb_knowledge_for_all_agents(
        feed_type=feed_type,
        item_count=result["fed_count"],
        category=category,
        tags=tags,
    )
    
    # 发送事件
    EVENT_BUS.emit("knowledge_fed", {
        "type": feed_type,
        "count": result["fed_count"],
        "source": source,
        "category": category,
        "tags": tags,
        "message": f"投喂了{result['fed_count']}条{feed_type}资料"
    })
    
    result["knowledge_version"] = KNOWLEDGE_STORE.version
    result["summary"] = KNOWLEDGE_STORE.get_summary()
    return jsonify(result)


@app.post("/knowledge/feed/document")
def feed_knowledge_document():
    """
    文档投喂入口（multipart/form-data）：
    - 支持 txt/md/csv/json/jsonl/pdf
    - 服务端解析并分批写入知识库，避免前端大文本卡顿
    """
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"error": "缺少上传文件(file)"}), 400

    filename = os.path.basename(upload.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        return jsonify({"error": f"不支持的文件类型: {ext}"}), 400

    feed_type = (request.form.get("type") or "materials").strip().lower()
    if feed_type not in {"materials", "slang", "cases"}:
        return jsonify({"error": "type 必须是 materials/slang/cases"}), 400

    category = (request.form.get("category") or "文档投喂").strip()
    source = (request.form.get("source") or f"upload:{filename}").strip()
    tags = _parse_tags(request.form.get("tags", ""))
    batch_size = request.form.get("batch_size", default=120, type=int)
    batch_size = max(10, min(int(batch_size or 120), 1000))

    parsed_count = 0
    fed_count = 0
    batch_count = 0
    batch = []

    try:
        for raw_item in _iter_document_items(upload, ext, feed_type):
            item = _normalize_document_item(raw_item, feed_type)
            if item is None:
                continue
            parsed_count += 1
            batch.append(item)

            if len(batch) >= batch_size:
                fed_count += _feed_batch(feed_type, batch, category, source, tags)
                batch_count += 1
                batch = []

        if batch:
            fed_count += _feed_batch(feed_type, batch, category, source, tags)
            batch_count += 1
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"文档解析失败: {exc}"}), 500

    absorb_knowledge_for_all_agents(
        feed_type=feed_type,
        item_count=fed_count,
        category=category,
        tags=tags,
    )
    EVENT_BUS.emit(
        "knowledge_fed",
        {
            "type": feed_type,
            "count": fed_count,
            "source": source,
            "category": category,
            "tags": tags,
            "message": f"文档投喂完成: {filename} -> {fed_count}条",
        },
    )

    return jsonify(
        {
            "status": "ok",
            "filename": filename,
            "extension": ext,
            "feed_type": feed_type,
            "parsed_count": parsed_count,
            "fed_count": fed_count,
            "batch_count": batch_count,
            "batch_size": batch_size,
            "max_upload_mb": MAX_DOC_UPLOAD_MB,
            "knowledge_version": KNOWLEDGE_STORE.version,
            "summary": KNOWLEDGE_STORE.get_summary(),
        }
    )


@app.get("/knowledge/list")
def list_knowledge():
    """查看已投喂资料"""
    limit = request.args.get("limit", 100, type=int)
    include_items = request.args.get("include_items", 0, type=int) == 1
    summary = KNOWLEDGE_STORE.get_summary()
    if include_items:
        summary["items"] = CONFIG_STORE.list_knowledge_items(limit=limit)
    return jsonify(summary)


@app.post("/knowledge/clear")
def clear_knowledge():
    """清空投喂资料"""
    KNOWLEDGE_STORE.clear()
    return jsonify({"status": "cleared", "message": "投喂资料已清空"})


@app.get("/rule-engine/stats")
def get_rule_engine_stats():
    """获取规则引擎统计（按层统计）"""
    return jsonify(RULE_ENGINE.get_stats())


# ============================================================================
# 企业编排与结果仓 API
# ============================================================================

@app.post("/campaigns/run")
def run_campaign():
    """运行企业级战役编排（基线 + 进化阶段）"""
    data = request.json or {}
    name = (data.get("name") or f"campaign-{int(time.time())}").strip()
    scenario = (data.get("scenario") or "general").strip()
    persona_ids = data.get("persona_ids") or []
    target_keywords = data.get("target_keywords") or []
    baseline_rounds = data.get("baseline_rounds", 1)
    adversarial_rounds = data.get("adversarial_rounds", 1)
    enable_peer_learning = bool(data.get("enable_peer_learning", True))
    random_seed = data.get("random_seed")

    try:
        result = CAMPAIGN_ORCHESTRATOR.run_campaign(
            name=name,
            scenario=scenario,
            persona_ids=persona_ids,
            target_keywords=target_keywords,
            baseline_rounds=baseline_rounds,
            adversarial_rounds=adversarial_rounds,
            enable_peer_learning=enable_peer_learning,
            random_seed=random_seed,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"campaign execution failed: {exc}"}), 500


@app.get("/campaigns")
def list_campaigns():
    """列出历史战役"""
    limit = request.args.get("limit", 20, type=int)
    return jsonify({"campaigns": CAMPAIGN_ORCHESTRATOR.list_campaigns(limit=limit)})


@app.get("/campaigns/<campaign_id>")
def get_campaign(campaign_id: str):
    """查看单个战役详情"""
    campaign = CONFIG_STORE.get_campaign(campaign_id)
    if not campaign:
        return jsonify({"error": "campaign not found"}), 404
    return jsonify(campaign)


@app.get("/campaigns/<campaign_id>/replay")
def replay_campaign(campaign_id: str):
    """按战役回放攻防记录"""
    phase = (request.args.get("phase") or "").strip()
    limit = request.args.get("limit", 5000, type=int)
    result = CAMPAIGN_ORCHESTRATOR.replay_campaign(
        campaign_id=campaign_id,
        phase=phase,
        limit=limit,
    )
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@app.post("/campaigns/compare")
def compare_campaigns():
    """跨战役效果对比"""
    data = request.json or {}
    campaign_ids = data.get("campaign_ids") or []
    if not isinstance(campaign_ids, list) or len(campaign_ids) < 2:
        return jsonify({"error": "campaign_ids 至少传入2个"}), 400
    return jsonify(CAMPAIGN_ORCHESTRATOR.compare_campaigns(campaign_ids))


@app.post("/campaigns/ab-run")
def run_ab_campaign():
    """
    基于规则快照执行A/B对比回归。
    两个快照使用相同Agent起点、相同编排参数，便于横向比较。
    """
    data = request.json or {}
    snapshot_a_id = (data.get("snapshot_a_id") or "").strip()
    snapshot_b_id = (data.get("snapshot_b_id") or "").strip()
    if not snapshot_a_id or not snapshot_b_id:
        return jsonify({"error": "缺少snapshot_a_id或snapshot_b_id"}), 400

    snapshot_a = CONFIG_STORE.get_rule_snapshot(snapshot_a_id)
    snapshot_b = CONFIG_STORE.get_rule_snapshot(snapshot_b_id)
    if not snapshot_a or not snapshot_b:
        return jsonify({"error": "snapshot不存在"}), 404

    scenario = (data.get("scenario") or "ab-regression").strip()
    name = (data.get("name") or f"ab-{int(time.time())}").strip()
    baseline_rounds = data.get("baseline_rounds", 1)
    adversarial_rounds = data.get("adversarial_rounds", 1)
    enable_peer_learning = bool(data.get("enable_peer_learning", True))
    persona_ids = data.get("persona_ids") or []
    target_keywords = data.get("target_keywords") or []
    random_seed = data.get("random_seed")
    if random_seed is None:
        random_seed = int(time.time())

    original_rules = list(SYSTEM_STATE.get("rules", []))
    original_rules_version = int(SYSTEM_STATE.get("rules_version", 0))
    original_state = export_peripheral_agents_state()

    try:
        # 保证A/B从同一能力起点开始
        reset_peripheral_agents_state()
        ab_initial_state = export_peripheral_agents_state()

        _apply_rules_runtime(
            snapshot_a.get("rules", []),
            persist=False,
            rules_version=snapshot_a.get("rules_version", original_rules_version),
            refine=False,
        )
        restore_peripheral_agents_state(ab_initial_state)
        run_a = CAMPAIGN_ORCHESTRATOR.run_campaign(
            name=f"{name}-A",
            scenario=f"{scenario}:A",
            persona_ids=persona_ids,
            target_keywords=target_keywords,
            baseline_rounds=baseline_rounds,
            adversarial_rounds=adversarial_rounds,
            enable_peer_learning=enable_peer_learning,
            random_seed=random_seed,
        )

        _apply_rules_runtime(
            snapshot_b.get("rules", []),
            persist=False,
            rules_version=snapshot_b.get("rules_version", original_rules_version),
            refine=False,
        )
        restore_peripheral_agents_state(ab_initial_state)
        run_b = CAMPAIGN_ORCHESTRATOR.run_campaign(
            name=f"{name}-B",
            scenario=f"{scenario}:B",
            persona_ids=persona_ids,
            target_keywords=target_keywords,
            baseline_rounds=baseline_rounds,
            adversarial_rounds=adversarial_rounds,
            enable_peer_learning=enable_peer_learning,
            random_seed=random_seed,
        )

        comparison = CAMPAIGN_ORCHESTRATOR.compare_campaigns(
            [run_a.get("campaign_id"), run_b.get("campaign_id")]
        )
        delta = comparison.get("comparison", [])
        delta_item = delta[0] if delta else {}

        summary_a = run_a.get("summary", {})
        summary_b = run_b.get("summary", {})
        score_a = summary_a.get("adversarial_detection_rate", 0) - summary_a.get("degradation", 0)
        score_b = summary_b.get("adversarial_detection_rate", 0) - summary_b.get("degradation", 0)
        winner = "A" if score_a > score_b else "B" if score_b > score_a else "tie"

        return jsonify(
            {
                "status": "completed",
                "snapshot_a_id": snapshot_a_id,
                "snapshot_b_id": snapshot_b_id,
                "campaign_a_id": run_a.get("campaign_id"),
                "campaign_b_id": run_b.get("campaign_id"),
                "summary_a": summary_a,
                "summary_b": summary_b,
                "delta": delta_item,
                "winner": winner,
                "random_seed": random_seed,
            }
        )
    finally:
        restore_peripheral_agents_state(original_state)
        _apply_rules_runtime(
            original_rules,
            persist=False,
            rules_version=original_rules_version,
            refine=False,
        )


@app.post("/regressions/run")
def run_regression_matrix():
    """
    对多个规则快照执行同参数批量回归。
    适合后续挂自动化定时任务。
    """
    data = request.json or {}
    actor = (data.get("actor") or "system").strip()
    snapshot_ids = data.get("snapshot_ids") or []
    if not isinstance(snapshot_ids, list) or len(snapshot_ids) == 0:
        return jsonify({"error": "snapshot_ids不能为空"}), 400

    scenario = (data.get("scenario") or "matrix-regression").strip()
    baseline_rounds = data.get("baseline_rounds", 1)
    adversarial_rounds = data.get("adversarial_rounds", 1)
    enable_peer_learning = bool(data.get("enable_peer_learning", True))
    persona_ids = data.get("persona_ids") or []
    target_keywords = data.get("target_keywords") or []
    threshold_input = data.get("alert_thresholds") or {}
    thresholds = normalize_thresholds(threshold_input)
    persist_report = _as_bool(data.get("persist_report"), True)
    include_markdown = _as_bool(data.get("include_markdown"), True)
    dispatch_alerts_enabled = _as_bool(data.get("dispatch_alerts"), True)
    alert_channel_ids = data.get("alert_channel_ids") or []
    if not isinstance(alert_channel_ids, list):
        alert_channel_ids = []
    report_name = (data.get("report_name") or f"{scenario}-{int(time.time())}").strip()
    random_seed = data.get("random_seed")
    if random_seed is None:
        random_seed = int(time.time())

    snapshots = []
    for sid in snapshot_ids:
        snapshot = CONFIG_STORE.get_rule_snapshot(str(sid).strip())
        if snapshot:
            snapshots.append(snapshot)
    if not snapshots:
        return jsonify({"error": "未找到有效快照"}), 404

    original_rules = list(SYSTEM_STATE.get("rules", []))
    original_rules_version = int(SYSTEM_STATE.get("rules_version", 0))
    original_state = export_peripheral_agents_state()

    results = []
    comparisons = []
    matrix_result = {}
    try:
        reset_peripheral_agents_state()
        matrix_initial_state = export_peripheral_agents_state()

        for idx, snapshot in enumerate(snapshots):
            _apply_rules_runtime(
                snapshot.get("rules", []),
                persist=False,
                rules_version=snapshot.get("rules_version", original_rules_version),
                refine=False,
            )
            restore_peripheral_agents_state(matrix_initial_state)

            run_result = CAMPAIGN_ORCHESTRATOR.run_campaign(
                name=f"{scenario}-{snapshot.get('name', snapshot.get('snapshot_id'))}",
                scenario=f"{scenario}:{snapshot.get('snapshot_id')}",
                persona_ids=persona_ids,
                target_keywords=target_keywords,
                baseline_rounds=baseline_rounds,
                adversarial_rounds=adversarial_rounds,
                enable_peer_learning=enable_peer_learning,
                random_seed=int(random_seed) + idx,
            )
            results.append(
                {
                    "snapshot_id": snapshot.get("snapshot_id"),
                    "snapshot_name": snapshot.get("name"),
                    "campaign_id": run_result.get("campaign_id"),
                    "summary": run_result.get("summary", {}),
                }
            )

        if len(results) >= 2:
            base_campaign = results[0].get("campaign_id")
            for item in results[1:]:
                cmp_result = CAMPAIGN_ORCHESTRATOR.compare_campaigns(
                    [base_campaign, item.get("campaign_id")]
                )
                delta = cmp_result.get("comparison", [])
                if delta:
                    comparisons.append(
                        {
                            "base_snapshot_id": results[0].get("snapshot_id"),
                            "target_snapshot_id": item.get("snapshot_id"),
                            "delta": delta[0],
                        }
                    )

        matrix_result = {
            "status": "completed",
            "scenario": scenario,
            "random_seed": random_seed,
            "runs": results,
            "comparisons": comparisons,
        }

        evaluation = evaluate_regression_matrix(matrix_result, thresholds=thresholds)
        markdown = render_regression_markdown(
            name=report_name,
            scenario=scenario,
            matrix_result=matrix_result,
            evaluation=evaluation,
        )

        report_id = None
        if persist_report:
            report_payload = {
                "matrix_result": matrix_result,
                "evaluation": evaluation,
            }
            report_id = CONFIG_STORE.create_regression_report(
                name=report_name,
                scenario=scenario,
                status=evaluation.get("status", "ok"),
                thresholds=evaluation.get("thresholds", thresholds),
                payload=report_payload,
                markdown=markdown,
            )

        dispatch_result = None
        if dispatch_alerts_enabled and int(evaluation.get("alert_count", 0) or 0) > 0:
            dispatch_result = dispatch_regression_alerts(
                evaluation=evaluation,
                scenario=scenario,
                source_id=report_id or f"regression-{int(time.time())}",
                event_emitter=EVENT_BUS.emit,
                channel_ids=alert_channel_ids,
            )

        level = (evaluation.get("status") or "ok").lower()
        severity = "critical" if level == "critical" else "warning" if level == "warning" else "info"
        _audit(
            event_type="regression_run",
            action="matrix_run",
            actor=actor,
            target_type="regression_report",
            target_id=report_id or "",
            severity=severity,
            details={
                "scenario": scenario,
                "snapshot_ids": [item.get("snapshot_id") for item in results],
                "status": level,
                "alert_count": int(evaluation.get("alert_count", 0) or 0),
                "dispatch_alerts": dispatch_alerts_enabled,
                "selected_channels": alert_channel_ids,
            },
        )

        response = {
            **matrix_result,
            "evaluation": evaluation,
            "report_id": report_id,
            "thresholds": thresholds,
            "alert_dispatch": dispatch_result,
        }
        if include_markdown:
            response["report_markdown"] = markdown
        return jsonify(response)
    finally:
        restore_peripheral_agents_state(original_state)
        _apply_rules_runtime(
            original_rules,
            persist=False,
            rules_version=original_rules_version,
            refine=False,
        )


@app.get("/regressions/reports")
def list_regression_reports():
    """查看历史回归报告。"""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"reports": CONFIG_STORE.list_regression_reports(limit=limit)})


@app.get("/regressions/reports/<report_id>")
def get_regression_report(report_id: str):
    """查看单个回归报告详情。"""
    report = CONFIG_STORE.get_regression_report(report_id)
    if not report:
        return jsonify({"error": "report not found"}), 404
    return jsonify(report)


@app.get("/regressions/reports/<report_id>/markdown")
def get_regression_report_markdown(report_id: str):
    """获取回归报告Markdown。"""
    report = CONFIG_STORE.get_regression_report(report_id)
    if not report:
        return jsonify({"error": "report not found"}), 404
    return Response(report.get("markdown", ""), mimetype="text/markdown; charset=utf-8")


@app.post("/regressions/reports/<report_id>/dispatch-alerts")
def dispatch_report_alerts(report_id: str):
    """按报告重新触发告警分发。"""
    report = CONFIG_STORE.get_regression_report(report_id)
    if not report:
        return jsonify({"error": "report not found"}), 404

    payload = report.get("payload", {}) if isinstance(report.get("payload"), dict) else {}
    evaluation = payload.get("evaluation", {}) if isinstance(payload, dict) else {}
    if not evaluation:
        return jsonify({"error": "report payload missing evaluation"}), 400

    data = request.json or {}
    actor = (data.get("actor") or "operator").strip()
    channel_ids = data.get("alert_channel_ids") or []
    if not isinstance(channel_ids, list):
        channel_ids = []

    dispatch_result = dispatch_regression_alerts(
        evaluation=evaluation,
        scenario=report.get("scenario", "regression"),
        source_id=report_id,
        event_emitter=EVENT_BUS.emit,
        channel_ids=channel_ids,
    )
    _audit(
        event_type="alert_dispatch",
        action="dispatch_report_alerts",
        actor=actor,
        target_type="regression_report",
        target_id=report_id,
        severity="warning" if int(evaluation.get("alert_count", 0) or 0) > 0 else "info",
        details={
            "scenario": report.get("scenario"),
            "status": evaluation.get("status"),
            "alert_count": int(evaluation.get("alert_count", 0) or 0),
            "channel_ids": channel_ids,
            "dispatch_summary": dispatch_result.get("summary", {}),
        },
    )
    return jsonify(
        {
            "status": "ok",
            "report_id": report_id,
            "dispatch": dispatch_result,
        }
    )


@app.get("/alerts/channels")
def list_alert_channels():
    """查看告警通道配置。"""
    include_disabled = request.args.get("include_disabled", 0, type=int) == 1
    return jsonify({"channels": CONFIG_STORE.list_alert_channels(include_disabled=include_disabled)})


@app.post("/alerts/channels")
def upsert_alert_channel():
    """新增或更新告警通道。"""
    data = request.json or {}
    actor = (data.get("actor") or "operator").strip()
    channel_id = (data.get("channel_id") or "").strip()
    name = (data.get("name") or "").strip()
    channel_type = (data.get("channel_type") or "event_bus").strip().lower()
    endpoint = (data.get("endpoint") or "").strip()
    min_severity = (data.get("min_severity") or "warning").strip().lower()
    enabled = _as_bool(data.get("enabled"), True)
    config = data.get("config") if isinstance(data.get("config"), dict) else {}

    if channel_type not in {"event_bus", "stdout", "webhook"}:
        return jsonify({"error": "channel_type仅支持event_bus/stdout/webhook"}), 400
    if channel_type == "webhook" and not endpoint:
        return jsonify({"error": "webhook通道必须提供endpoint"}), 400
    if min_severity not in {"info", "warning", "critical"}:
        return jsonify({"error": "min_severity必须是info/warning/critical"}), 400

    channel_id = CONFIG_STORE.upsert_alert_channel(
        channel_id=channel_id,
        name=name or channel_id or f"{channel_type}-channel",
        channel_type=channel_type,
        endpoint=endpoint,
        min_severity=min_severity,
        enabled=enabled,
        config=config,
    )
    item = CONFIG_STORE.get_alert_channel(channel_id)
    _audit(
        event_type="alert_channel",
        action="upsert",
        actor=actor,
        target_type="alert_channel",
        target_id=channel_id,
        details={
            "channel_type": channel_type,
            "enabled": enabled,
            "min_severity": min_severity,
        },
    )
    return jsonify({"status": "ok", "channel": item})


@app.post("/alerts/channels/<channel_id>/toggle")
def toggle_alert_channel(channel_id: str):
    """启用/禁用告警通道。"""
    data = request.json or {}
    actor = (data.get("actor") or "operator").strip()
    enabled = _as_bool(data.get("enabled"), True)
    item = CONFIG_STORE.set_alert_channel_enabled(channel_id, enabled)
    if not item:
        return jsonify({"error": "channel not found"}), 404

    _audit(
        event_type="alert_channel",
        action="toggle",
        actor=actor,
        target_type="alert_channel",
        target_id=channel_id,
        details={"enabled": enabled},
    )
    return jsonify({"status": "ok", "channel": item})


@app.get("/alerts/incidents")
def list_alert_incidents():
    """查看告警事件。"""
    limit = request.args.get("limit", 100, type=int)
    status = (request.args.get("status") or "").strip()
    severity = (request.args.get("severity") or "").strip()
    incidents = CONFIG_STORE.list_alert_incidents(limit=limit, status=status, severity=severity)
    return jsonify({"incidents": incidents})


@app.post("/alerts/incidents/<incident_id>/ack")
def acknowledge_alert_incident(incident_id: str):
    """确认告警事件。"""
    data = request.json or {}
    actor = (data.get("actor") or "operator").strip()
    note = (data.get("note") or "").strip()
    status = (data.get("status") or "acknowledged").strip()
    item = CONFIG_STORE.acknowledge_alert_incident(
        incident_id=incident_id,
        actor=actor,
        note=note,
        status=status,
    )
    if not item:
        return jsonify({"error": "incident not found"}), 404

    _audit(
        event_type="alert_incident",
        action=f"ack:{status}",
        actor=actor,
        target_type="alert_incident",
        target_id=incident_id,
        details={"note": note},
    )
    return jsonify({"status": "ok", "incident": item})


@app.get("/alerts/deliveries")
def list_alert_deliveries():
    """查看告警投递记录。"""
    limit = request.args.get("limit", 200, type=int)
    status = (request.args.get("status") or "").strip()
    severity = (request.args.get("severity") or "").strip()
    channel_id = (request.args.get("channel_id") or "").strip()
    alert_type = (request.args.get("alert_type") or "").strip()
    items = CONFIG_STORE.list_alert_deliveries(
        limit=limit,
        status=status,
        severity=severity,
        channel_id=channel_id,
        alert_type=alert_type,
    )
    return jsonify({"deliveries": items})


@app.get("/audit/logs")
def list_audit_logs():
    """查询审计日志。"""
    limit = request.args.get("limit", 100, type=int)
    event_type = (request.args.get("event_type") or "").strip()
    actor = (request.args.get("actor") or "").strip()
    target_type = (request.args.get("target_type") or "").strip()
    target_id = (request.args.get("target_id") or "").strip()
    severity = (request.args.get("severity") or "").strip()
    logs = CONFIG_STORE.list_audit_logs(
        limit=limit,
        event_type=event_type,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
        severity=severity,
    )
    return jsonify({"logs": logs})


# 兼容旧API（保持页面功能正常）
@app.post("/simulate")
def simulate():
    """兼容旧API - 社区模拟"""
    return jsonify({
        "events": [],
        "relations": USER_RELATIONS,
        "message": "系统已重构为对抗模式"
    })


@app.post("/run")
def run_test():
    """兼容旧API - 单角色测试"""
    data = request.json or {}
    persona_id = data.get("persona_id", "")
    
    if not persona_id:
        return jsonify({"error": "缺少persona_id"}), 400
    
    # 运行一次对抗
    result = run_adversarial_battle(persona_id)
    
    return jsonify({
        "persona_id": persona_id,
        "generated_query": result["attack"]["content"],
        "risk_level": 1 if result["result"]["bypass_success"] else 5,
        "risk_detected": not result["result"]["bypass_success"],
        "technique_used": result["attack"]["technique_used"],
        "battle_result": result,
    })


@app.get("/community/memory/<persona_id>")
def get_memory(persona_id: str):
    """兼容旧API"""
    return jsonify({"persona_id": persona_id, "memory": []})


@app.get("/community/reputation/<persona_id>")
def get_reputation(persona_id: str):
    """兼容旧API - 返回Agent状态"""
    return get_agent_state(persona_id)


@app.get("/community/relations")
def get_community_relations():
    """兼容旧API"""
    return jsonify({
        "relations": USER_RELATIONS,
        "relation_count": len(USER_RELATIONS),
    })


@app.post("/community/agent/<persona_id>/config")
def update_agent_config_legacy(persona_id: str):
    """兼容旧API - 转发到新API"""
    return update_agent_config(persona_id)


@app.post("/community/reset")
def reset_community():
    """兼容旧API"""
    return reset_system()


# 测试工作流API兼容
@app.post("/test-workflow/start")
def start_test_workflow():
    """兼容旧API"""
    return jsonify({
        "status": "started",
        "message": "对抗测试已启动",
        "phases": ["单Agent对抗", "迭代优化", "协作攻击"]
    })


@app.post("/test-workflow/baseline")
def run_baseline_test():
    """运行批量对抗测试 - 全部26个反贼Agent"""
    data = request.json or {}
    personas = get_all_personas()
    
    # 检查是否有规则
    if not SYSTEM_STATE["rules"]:
        return jsonify({"error": "请先设置规则！在规则文本框输入规则后点击保存"}), 400
    
    # 检查中心Agent是否拆解了规则
    if not CENTRAL_INSPECTOR.refined_standards:
        # 强制重新拆解规则
        CENTRAL_INSPECTOR.refine_rules(SYSTEM_STATE["rules"])
    
    # 发送"中心Agent分析规则"事件
    EVENT_BUS.emit("central_agent_analysis", {
        "action": "规则拆解",
        "rules_count": len(SYSTEM_STATE["rules"]),
        "refined_count": len(CENTRAL_INSPECTOR.refined_standards),
        "message": "中心质检Agent正在分析审核规则，生成检测策略..."
    })
    
    results = []
    posts_generated = []
    
    # 测试所有26个反贼Agent
    for i, persona in enumerate(personas):
        # 发送"Agent思考"事件
        EVENT_BUS.emit("agent_thinking", {
            "agent": persona["name"],
            "category": persona.get("category", ""),
            "action": "正在构思帖子...",
            "progress": f"{i+1}/{len(personas)}"
        })
        
        result = run_adversarial_battle(persona["id"])
        results.append(result)
        
        # 发送"发帖结果"事件
        bypass = result.get("result", {}).get("bypass_success", False)
        EVENT_BUS.emit("post_result", {
            "agent": persona["name"],
            "content": result.get("attack", {}).get("content", "")[:50] + "...",
            "technique": result.get("attack", {}).get("technique_used", ""),
            "bypass": bypass,
            "status": "✅ 绕过成功" if bypass else "🚫 被检出"
        })
        
        # 收集生成的攻击帖子
        posts_generated.append({
            "agent_name": persona["name"],
            "category": persona.get("category", ""),
            "content": result.get("attack", {}).get("content", ""),
            "technique": result.get("attack", {}).get("technique_used", ""),
            "strategy": result.get("attack", {}).get("strategy", ""),
            "detected": result.get("defense", {}).get("detected", False),
            "bypass_success": result.get("result", {}).get("bypass_success", False),
        })
    
    success_count = sum(1 for r in results if r["result"]["bypass_success"])
    detection_count = len(results) - success_count
    
    # 发送"基线测试完成"事件
    EVENT_BUS.emit("baseline_complete", {
        "total": len(results),
        "bypass": success_count,
        "detected": detection_count,
        "bypass_rate": round(success_count / len(results) * 100, 1) if results else 0
    })
    
    return jsonify({
        "phase": "baseline",
        "status": "completed",
        "summary": {
            "total_tested": len(results),
            "bypass_success": success_count,
            "detection_success": detection_count,
            "bypass_rate": round(success_count / len(results) * 100, 1) if results else 0,
            "detection_rate": round(detection_count / len(results) * 100, 1) if results else 0,
        },
        "posts_generated": posts_generated,
        "results": results,
        "refined_standards": CENTRAL_INSPECTOR.refined_standards,
    })


@app.get("/test-workflow/status")
def get_workflow_status():
    """获取工作流状态"""
    return jsonify({
        "status": "running" if SYSTEM_STATE["battle_history"] else "idle",
        "current_phase": "adversarial",
        "phases_completed": ["baseline"] if SYSTEM_STATE["battle_history"] else [],
    })


@app.post("/test-workflow/adversarial")
def run_adversarial_test():
    """运行演化后的对抗测试 - 反贼学习后再测试一次"""
    data = request.json or {}
    personas = get_all_personas()
    
    # 检查是否有规则
    if not SYSTEM_STATE["rules"]:
        return jsonify({"error": "请先设置规则"}), 400
    
    results = []
    posts_generated = []
    
    # 让反贼互相学习成功的技巧
    successful_techniques = []
    for h in SYSTEM_STATE.get("battle_history", []):
        if h.get("result", {}).get("bypass_success"):
            tech = h.get("attack", {}).get("technique_used")
            category = h.get("category", "")
            pid = h.get("persona_id", "")
            if tech:
                successful_techniques.append({"technique": tech, "category": category, "agent_id": pid})
    
    # === 核心改进：真正的Multi-Agent讨论环节 ===
    EVENT_BUS.emit("discussion_phase_start", {
        "message": "🗣️ 反贼们开始私下交流，分享成功经验...",
        "successful_count": len(successful_techniques)
    })
    
    # 1. 先召开一次策略会议
    if successful_techniques:
        topic = "如何更好地绕过内容审核"
        meeting_result = run_red_team_planning(topic)
        
        # 发送会议事件
        for speech in meeting_result.get("meeting_log", []):
            EVENT_BUS.emit("meeting_speech", {
                "speaker": speech["speaker"],
                "content": speech["content"],
                "category": speech.get("category", "")
            })
    
    # 2. 成功的Agent与其他Agent进行一对一讨论
    discussion_pairs = []
    successful_agents = list(set(st["agent_id"] for st in successful_techniques if st["agent_id"]))
    failed_agents = [p["id"] for p in personas if p["id"] not in successful_agents]
    
    # 随机配对进行讨论
    for success_id in successful_agents[:3]:  # 最多3个成功者分享
        if failed_agents:
            learner_id = random.choice(failed_agents)
            success_persona = PERSONA_INDEX.get(success_id)
            learner_persona = PERSONA_INDEX.get(learner_id)
            
            if success_persona and learner_persona:
                # 找到这个成功者用的技巧
                used_tech = next((st["technique"] for st in successful_techniques if st["agent_id"] == success_id), "通用技巧")
                
                # 进行讨论
                learner_agent = AttackAgent(learner_persona)
                load_agent_runtime(learner_agent)
                
                discussion = learner_agent.discuss_with_peer(
                    success_persona["name"], 
                    used_tech, 
                    "绕过审核"
                )
                
                discussion_pairs.append(discussion)
                
                # 发送讨论事件
                for dialogue in discussion.get("dialogue", []):
                    EVENT_BUS.emit("agent_dialogue", {
                        "speaker": dialogue["speaker"],
                        "content": dialogue["content"],
                        "from_agent": success_id,
                        "to_agent": learner_id,
                        "is_discussion": True
                    })
    
    # 反贼学习阶段 - 从成功的同行那里学习
    EVENT_BUS.emit("learning_phase", {
        "message": "📚 反贼们开始学习成功的技巧...",
        "techniques_to_share": list(set(st["technique"] for st in successful_techniques))
    })
    
    learning_connections = []  # 记录学习关系，用于前端绘制
    
    for persona in personas:
        agent = AttackAgent(persona)
        load_agent_runtime(agent)
        
        # 尝试从成功的技巧中学习（只学习与自己人设相关的）
        learned_new = []
        for st in successful_techniques:
            teacher_id = st.get("agent_id", "")
            if teacher_id != persona["id"]:  # 不从自己学习
                if agent.learn_from_peer(st["technique"], st["category"], teacher_id):
                    learned_new.append(st["technique"])
                    learning_connections.append({
                        "from": teacher_id,
                        "to": persona["id"],
                        "technique": st["technique"]
                    })
        
        if learned_new:
            EVENT_BUS.emit("skill_learned", {
                "agent": persona["name"],
                "agent_id": persona["id"],
                "techniques": learned_new,
                "message": f"{persona['name']}学会了新技巧！"
            })
    
    EVENT_BUS.emit("discussion_phase_end", {
        "message": "讨论结束，反贼们准备再次尝试...",
        "discussions_count": len(discussion_pairs),
        "learning_connections": learning_connections  # 新增：传递学习连接
    })
    
    # 演化后测试 - 所有26个反贼再测试一次
    EVENT_BUS.emit("evolved_test_start", {
        "message": "🔄 开始演化后测试...",
        "iteration": 1
    })
    
    for i, persona in enumerate(personas):
        EVENT_BUS.emit("agent_thinking", {
            "agent": persona["name"],
            "action": "运用学到的新技巧构思帖子...",
            "progress": f"{i+1}/{len(personas)}"
        })
        
        result = run_adversarial_battle(persona["id"], None, 1)  # iteration=1表示第二轮
        results.append(result)
        
        bypass = result.get("result", {}).get("bypass_success", False)
        EVENT_BUS.emit("post_result", {
            "agent": persona["name"],
            "content": result.get("attack", {}).get("content", "")[:50] + "...",
            "technique": result.get("attack", {}).get("technique_used", ""),
            "bypass": bypass,
            "is_evolved": True,
            "status": "✅ 绕过成功" if bypass else "🚫 被检出"
        })
        
        # 收集生成的攻击帖子
        posts_generated.append({
            "agent_name": persona["name"],
            "category": persona.get("category", ""),
            "content": result.get("attack", {}).get("content", ""),
            "technique": result.get("attack", {}).get("technique_used", ""),
            "strategy": result.get("attack", {}).get("strategy", ""),
            "evolution_level": result.get("attack", {}).get("evolution_level", 1),
            "learned_count": result.get("attack", {}).get("learned_techniques_count", 0),
            "detected": result.get("defense", {}).get("detected", False),
            "bypass_success": result.get("result", {}).get("bypass_success", False),
        })
    
    success_count = sum(1 for r in results if r["result"]["bypass_success"])
    detection_count = len(results) - success_count
    
    EVENT_BUS.emit("evolved_test_complete", {
        "total": len(results),
        "bypass": success_count,
        "detected": detection_count,
        "bypass_rate": round(success_count / len(results) * 100, 1) if results else 0
    })
    
    return jsonify({
        "phase": "adversarial",
        "status": "completed",
        "discussions": discussion_pairs,
        "summary": {
            "total_tested": len(results),
            "bypass_success": success_count,
            "detection_success": detection_count,
            "bypass_rate": round(success_count / len(results) * 100, 1) if results else 0,
            "detection_rate": round(detection_count / len(results) * 100, 1) if results else 0,
            "improved_evasion": success_count,  # 演化后绕过成功的数量
        },
        "posts_generated": posts_generated,
        "results": results,
    })


@app.post("/test-workflow/analyze")
def run_analysis():
    """生成对比分析报告"""
    history = SYSTEM_STATE["battle_history"]
    
    if not history:
        return jsonify({"error": "还没有对抗记录"}), 400
    
    # 区分基线测试和演化后测试
    baseline_results = [h for h in history if h.get("attack", {}).get("iteration", 0) == 0]
    evolved_results = [h for h in history if h.get("attack", {}).get("iteration", 0) > 0]
    
    baseline_bypass = sum(1 for h in baseline_results if h["result"]["bypass_success"])
    evolved_bypass = sum(1 for h in evolved_results if h["result"]["bypass_success"])
    
    baseline_rate = round(baseline_bypass / len(baseline_results) * 100, 1) if baseline_results else 0
    evolved_rate = round(evolved_bypass / len(evolved_results) * 100, 1) if evolved_results else 0
    
    # 计算检出率变化
    baseline_detection = 100 - baseline_rate
    evolved_detection = 100 - evolved_rate
    degradation = baseline_detection - evolved_detection
    
    # 按技巧统计
    by_technique = {}
    for h in history:
        tech = h["attack"]["technique_used"]
        if tech not in by_technique:
            by_technique[tech] = {"total": 0, "success": 0}
        by_technique[tech]["total"] += 1
        if h["result"]["bypass_success"]:
            by_technique[tech]["success"] += 1
    
    # 找出最有效的绕过技巧
    effective_techniques = sorted(
        [(k, v["success"] / v["total"] * 100 if v["total"] > 0 else 0) for k, v in by_technique.items()],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    return jsonify({
        "phase": "analyze",
        "status": "completed",
        "summary": {
            "comparison": {
                "baseline_detection_rate": baseline_detection,
                "evolved_detection_rate": evolved_detection,
                "degradation": round(degradation, 1),
                "degradation_percent": round(degradation / baseline_detection * 100, 1) if baseline_detection > 0 else 0,
            },
            "conclusion": {
                "rule_robustness": "weak" if degradation > 20 else "moderate" if degradation > 10 else "strong",
                "total_tests": len(history),
                "baseline_tests": len(baseline_results),
                "evolved_tests": len(evolved_results),
            },
            "effective_techniques": effective_techniques,
            "recommendations": [
                {"priority": "high", "suggestion": f"关注{effective_techniques[0][0]}技巧，绕过率{effective_techniques[0][1]:.1f}%"} if effective_techniques else {}
            ],
        },
        "baseline_detection_rate": baseline_detection,
        "adversarial_detection_rate": evolved_detection,
        "degradation": round(degradation, 1),
        "degradation_percent": round(degradation / baseline_detection * 100, 1) if baseline_detection > 0 else 0,
        "rule_robustness": "weak" if degradation > 20 else "moderate" if degradation > 10 else "strong",
        "total_battles": len(history),
        "by_technique": {k: {"rate": round(v["success"] / v["total"] * 100, 1) if v["total"] > 0 else 0} for k, v in by_technique.items()},
        "total_baseline_posts": len(baseline_results),
        "total_evolved_posts": len(evolved_results),
        "baseline_posts": [{"agent": h["persona_name"], "content": h["attack"]["content"], "technique": h["attack"]["technique_used"], "bypass": h["result"]["bypass_success"]} for h in baseline_results[:10]],
        "evolved_posts": [{"agent": h["persona_name"], "content": h["attack"]["content"], "technique": h["attack"]["technique_used"], "bypass": h["result"]["bypass_success"]} for h in evolved_results[:10]],
    })


@app.get("/test-workflow/report")
def get_workflow_report():
    """生成对抗报告 - 包含完整的帖子数据"""
    history = SYSTEM_STATE["battle_history"]
    
    if not history:
        return jsonify({"error": "还没有对抗记录"}), 400
    
    # 区分基线测试和演化后测试
    baseline_results = [h for h in history if h.get("attack", {}).get("iteration", 0) == 0]
    evolved_results = [h for h in history if h.get("attack", {}).get("iteration", 0) > 0]
    
    # 计算统计
    total = len(history)
    bypass_success = sum(1 for h in history if h["result"]["bypass_success"])
    
    baseline_total = len(baseline_results)
    baseline_bypass = sum(1 for h in baseline_results if h["result"]["bypass_success"])
    baseline_detection_rate = round((1 - baseline_bypass / baseline_total) * 100, 1) if baseline_total else 0
    
    evolved_total = len(evolved_results)
    evolved_bypass = sum(1 for h in evolved_results if h["result"]["bypass_success"])
    evolved_detection_rate = round((1 - evolved_bypass / evolved_total) * 100, 1) if evolved_total else baseline_detection_rate
    
    # 计算衰减
    degradation = baseline_detection_rate - evolved_detection_rate
    
    # 按技巧统计
    by_technique = {}
    for h in history:
        tech = h["attack"]["technique_used"]
        if tech not in by_technique:
            by_technique[tech] = {"total": 0, "success": 0}
        by_technique[tech]["total"] += 1
        if h["result"]["bypass_success"]:
            by_technique[tech]["success"] += 1
    
    # 构建帖子数据 - 完整信息
    def format_post(h):
        return {
            "persona_id": h.get("persona_id", ""),
            "persona_name": h.get("persona_name", "未知"),
            "category": h.get("category", ""),
            "content": h.get("attack", {}).get("content", ""),
            "technique_used": h.get("attack", {}).get("technique_used", ""),
            "strategy": h.get("attack", {}).get("strategy", ""),
            "bypass": h.get("result", {}).get("bypass_success", False),
            "risk_detected": h.get("defense", {}).get("detected", False),
            "detection_reason": h.get("defense", {}).get("detection_reason", ""),
            "confidence": h.get("defense", {}).get("confidence", 0),
            "hit_keywords": h.get("defense", {}).get("hit_keywords", []),
            "target_topic": h.get("target_topic", ""),
            "stealth_score": h.get("attack", {}).get("complexity_score", 0),
            "iteration": h.get("attack", {}).get("iteration", 0),
        }
    
    baseline_posts = [format_post(h) for h in baseline_results]
    evolved_posts = [format_post(h) for h in evolved_results]
    
    # 生成建议
    recommendations = []
    if baseline_detection_rate < 30:
        recommendations.append({"priority": "high", "suggestion": "基线检出率过低，建议大幅加强规则覆盖度"})
    if degradation > 20:
        recommendations.append({"priority": "high", "suggestion": f"规则衰减严重({degradation:.1f}%)，建议增加变体检测能力"})
    
    # 按技巧分析薄弱点
    for tech, stats in by_technique.items():
        rate = round(stats["success"] / stats["total"] * 100, 1) if stats["total"] else 0
        if rate > 70:
            recommendations.append({"priority": "high", "suggestion": f"'{tech}'技巧绕过率{rate}%，建议专项加强"})
    
    if not recommendations:
        recommendations.append({"priority": "info", "suggestion": "规则表现良好，可继续观察"})
    
    return jsonify({
        "baseline_detection_rate": baseline_detection_rate,
        "adversarial_detection_rate": evolved_detection_rate,
        "degradation": degradation,
        "degradation_percent": abs(degradation),
        "rule_robustness": "weak" if baseline_detection_rate < 30 else "moderate" if baseline_detection_rate < 60 else "strong",
        "evolution_impact": "severe" if degradation > 20 else "moderate" if degradation > 10 else "mild",
        "total_battles": total,
        "bypass_success": bypass_success,
        "total_baseline_posts": baseline_total,
        "total_adversarial_posts": evolved_total,
        "baseline_posts": baseline_posts,
        "adversarial_posts": evolved_posts,
        "by_technique": {k: {"rate": round(v["success"] / v["total"] * 100, 1), "total": v["total"], "success": v["success"]} for k, v in by_technique.items()},
        "recommendations": recommendations,
        "protocol": {
            "random_seed": SYSTEM_STATE.get("random_seed", "N/A"),
            "repeat_runs": 1,
            "test_pool_size": total,
            "rules_snapshot": {
                "rules_version": SYSTEM_STATE.get("rules_version", 1),
                "rules_count": len(SYSTEM_STATE.get("rules", []))
            }
        }
    })


@app.post("/test-workflow/reset")
def reset_test_workflow():
    """兼容旧API"""
    return reset_system()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
