# -*- coding: utf-8 -*-
"""
Agent definitions and system state management.
v2.1 - 增加异步支持,大幅提升并发性能
"""

from dataclasses import asdict
from copy import deepcopy
import random
import time
import json
import os
import asyncio

from config import API_CONFIG
from config_store import CONFIG_STORE
from user_personas import USER_PERSONAS, ATTACK_TECHNIQUES
from rule_engine import RULE_ENGINE, AuditResult
from attack_knowledge import (
    KNOWLEDGE_STORE, ATTACK_EXAMPLES, STRATEGY_LEVELS,
    get_examples_for_technique, get_strategy_level, get_escalation_hint,
)

# 新增：自主智能体系统
from agent_personality import (
    generate_personality, get_dynamic_temperature, 
    describe_personality, PersonalityArchetype
)
from agent_memory import AgentMemory
from prompt_generator import PromptGenerator, format_knowledge_context, format_failure_context

# v2.1: 异步LLM支持
try:
    from async_llm import AsyncLLMClient
except ImportError:
    AsyncLLMClient = None

# v2.3: 数据库集成
from db_integration import get_db_integration

CONFIG_STORE.initialize(
    default_personas=USER_PERSONAS,
    default_techniques=ATTACK_TECHNIQUES,
)


def _load_runtime_personas() -> list:
    personas = CONFIG_STORE.list_personas()
    if personas:
        valid = [p for p in personas if p.get("id")]
        if valid:
            return valid
    return [dict(p) for p in USER_PERSONAS]


def _load_technique_library() -> dict:
    techniques = CONFIG_STORE.get_technique_map()
    return techniques if techniques else ATTACK_TECHNIQUES


def _build_peripheral_state(personas: list) -> dict:
    def _base_capability(persona: dict) -> float:
        skill_level = float(persona.get("skill_level", 1) or 1)
        stealth = float(persona.get("stealth_rating", 0.5) or 0.5)
        return round(1.0 + skill_level * 0.6 + stealth * 0.8, 2)

    return {
        p["id"]: {
            "persona": p,
            "learned_techniques": [],
            "success_count": 0,
            "fail_count": 0,
            "evolution_level": 1,
            "capability_score": _base_capability(p),
            "learning_points": 0,
            "knowledge_depth": 0,
            "knowledge_boost": 0.0,
            "last_strategy": None,
        }
        for p in personas
        if p.get("id")
    }


RUNTIME_PERSONAS = _load_runtime_personas()
TECHNIQUE_LIBRARY = _load_technique_library()
PERSONA_INDEX = {p["id"]: p for p in RUNTIME_PERSONAS if p.get("id")}

# ============================================================================
# 系统状态管理
# ============================================================================

SYSTEM_STATE = {
    # 中心Agent状态
    "central_agent": {
        "detection_rules": [],
        "refined_standards": {},
        "detection_stats": {
            "total_checked": 0,
            "total_detected": 0,
            "total_bypassed": 0,
            "by_technique": {},
            "by_keyword": {},
        },
        "is_processing": False,
        "current_task": None,
    },
    # 外围Agent状态
    "peripheral_agents": _build_peripheral_state(RUNTIME_PERSONAS),
    # 对抗历史记录
    "battle_history": [],
    # 当前规则
    "rules": [],
    "rules_version": 0,
}

# ============================================================================
# 🧠 新增：自主智能体系统全局存储
# ============================================================================

# Agent性格存储 {agent_id: AgentPersonality}
AGENT_PERSONALITIES = {}

# Agent记忆存储 {agent_id: AgentMemory}
AGENT_MEMORIES = {}

# 成功案例共享池（用于社交学习）
SHARED_SUCCESS_POOL = []


def _initialize_agent_personality(agent_id: str):
    """为Agent初始化性格（如果还没有）"""
    if agent_id not in AGENT_PERSONALITIES:
        AGENT_PERSONALITIES[agent_id] = generate_personality(seed=agent_id)
    return AGENT_PERSONALITIES[agent_id]


def _initialize_agent_memory(agent_id: str):
    """为Agent初始化记忆系统（如果还没有）"""
    if agent_id not in AGENT_MEMORIES:
        AGENT_MEMORIES[agent_id] = AgentMemory(agent_id)
    return AGENT_MEMORIES[agent_id]


def share_success_to_pool(attack_result: dict):
    """将成功案例加入共享池供其他Agent学习"""
    if not attack_result.get("detected", False):
        SHARED_SUCCESS_POOL.append({
            "agent_id": attack_result.get("persona_id"),
            "technique": attack_result.get("technique_used"),
            "content_snippet": attack_result.get("content", "")[:100],
            "complexity": attack_result.get("complexity_score", 0),
            "timestamp": time.time()
        })
        if len(SHARED_SUCCESS_POOL) > 50:
            SHARED_SUCCESS_POOL.pop(0)


def get_peer_success_examples(agent_id: str, limit: int = 3):
    """获取同伴的成功案例（用于社交学习）"""
    # 排除自己的案例
    peer_examples = [ex for ex in SHARED_SUCCESS_POOL if ex["agent_id"] != agent_id]
    return peer_examples[-limit:] if peer_examples else []


def get_all_personas() -> list:
    """Return runtime personas loaded from persistent storage."""
    return RUNTIME_PERSONAS


def get_technique_library() -> dict:
    """Return runtime attack technique library."""
    return TECHNIQUE_LIBRARY


def reset_peripheral_agents_state():
    """Reset agent runtime counters while keeping current persona configs."""
    SYSTEM_STATE["peripheral_agents"] = _build_peripheral_state(get_all_personas())


def export_peripheral_agents_state() -> dict:
    """Create a deep-copy snapshot of current peripheral runtime state."""
    return deepcopy(SYSTEM_STATE.get("peripheral_agents", {}))


def restore_peripheral_agents_state(state_snapshot: dict):
    """Restore peripheral runtime state from snapshot."""
    if not isinstance(state_snapshot, dict):
        return
    SYSTEM_STATE["peripheral_agents"] = deepcopy(state_snapshot)


def load_agent_runtime(agent) -> dict:
    """Load persisted runtime state into AttackAgent instance."""
    state = SYSTEM_STATE["peripheral_agents"].get(agent.persona_id, {})
    agent.learned_techniques = state.get("learned_techniques", [])
    agent.success_count = state.get("success_count", 0)
    agent.fail_count = state.get("fail_count", 0)
    agent.evolution_level = state.get("evolution_level", 1)
    base_capability = 1.0 + float(agent.persona.get("skill_level", 1) or 1) * 0.6 + float(
        agent.persona.get("stealth_rating", 0.5) or 0.5
    ) * 0.8
    agent.capability_score = float(state.get("capability_score", round(base_capability, 2)))
    agent.learning_points = int(state.get("learning_points", 0))
    agent.knowledge_depth = int(state.get("knowledge_depth", 0))
    agent.knowledge_boost = float(state.get("knowledge_boost", 0.0))
    agent.last_strategy = state.get("last_strategy")
    return state


def persist_agent_runtime(agent):
    """Persist AttackAgent runtime state to SYSTEM_STATE."""
    state = SYSTEM_STATE["peripheral_agents"].setdefault(
        agent.persona_id,
        {
            "persona": agent.persona,
            "learned_techniques": [],
            "success_count": 0,
            "fail_count": 0,
            "evolution_level": 1,
            "capability_score": 1.0,
            "learning_points": 0,
            "knowledge_depth": 0,
            "knowledge_boost": 0.0,
            "last_strategy": None,
        },
    )
    state["persona"] = agent.persona
    state["learned_techniques"] = list(agent.learned_techniques)
    state["success_count"] = int(agent.success_count)
    state["fail_count"] = int(agent.fail_count)
    state["evolution_level"] = int(agent.evolution_level)
    state["capability_score"] = round(float(agent.capability_score), 3)
    state["learning_points"] = int(agent.learning_points)
    state["knowledge_depth"] = int(agent.knowledge_depth)
    state["knowledge_boost"] = round(float(agent.knowledge_boost), 3)
    state["last_strategy"] = agent.last_strategy


def absorb_knowledge_for_all_agents(feed_type: str, item_count: int, category: str = "", tags: list = None):
    """
    Broadcast fed knowledge to all agents.
    More relevant personas gain stronger capability/knowledge boosts.
    """
    if item_count <= 0:
        return

    tags = tags or []
    category_text = " ".join([category] + [str(t) for t in tags]).lower()

    for persona in get_all_personas():
        agent = AttackAgent(persona)
        load_agent_runtime(agent)

        relevance = 0.6
        learnable_categories = [str(x).lower() for x in persona.get("learnable_categories", [])]
        if any(cat in category_text for cat in learnable_categories):
            relevance += 0.4

        behavior_patterns = [str(x).lower() for x in persona.get("behavior_patterns", [])]
        if any(pattern in category_text for pattern in behavior_patterns):
            relevance += 0.3

        if feed_type == "cases":
            relevance += 0.2
        elif feed_type == "slang":
            relevance += 0.15

        agent.absorb_knowledge(item_count=item_count, feed_type=feed_type, relevance=min(relevance, 1.5))


def persist_persona_update(persona: dict):
    """Persist persona configuration and refresh in-memory index."""
    global RUNTIME_PERSONAS

    persona_id = (persona or {}).get("id")
    if not persona_id:
        raise ValueError("persona id is required")

    CONFIG_STORE.upsert_persona(persona)

    replaced = False
    for i, current in enumerate(RUNTIME_PERSONAS):
        if current.get("id") == persona_id:
            RUNTIME_PERSONAS[i] = persona
            replaced = True
            break

    if not replaced:
        RUNTIME_PERSONAS.append(persona)

    PERSONA_INDEX.clear()
    PERSONA_INDEX.update({p["id"]: p for p in RUNTIME_PERSONAS if p.get("id")})

    state = SYSTEM_STATE["peripheral_agents"].get(persona_id)
    if not state:
        base_capability = 1.0 + float(persona.get("skill_level", 1) or 1) * 0.6 + float(
            persona.get("stealth_rating", 0.5) or 0.5
        ) * 0.8
        SYSTEM_STATE["peripheral_agents"][persona_id] = {
            "persona": persona,
            "learned_techniques": [],
            "success_count": 0,
            "fail_count": 0,
            "evolution_level": 1,
            "capability_score": round(base_capability, 2),
            "learning_points": 0,
            "knowledge_depth": 0,
            "knowledge_boost": 0.0,
            "last_strategy": None,
        }
    else:
        state["persona"] = persona


def persist_technique_update(category: str, name: str, details: dict):
    """Persist technique definition and refresh runtime technique map."""
    global TECHNIQUE_LIBRARY
    CONFIG_STORE.upsert_technique(category=category, name=name, details=details)
    TECHNIQUE_LIBRARY = _load_technique_library()

# ============================================================================
# 实时事件系统 - 记录Agent活动供前端展示
# ============================================================================

class EventBus:
    """事件总线 - 记录所有Agent活动"""
    
    def __init__(self):
        self.events = []
        self.max_events = 200
    
    def emit(self, event_type: str, data: dict):
        """发送事件"""
        event = {
            "id": len(self.events) + 1,
            "type": event_type,
            "timestamp": time.time(),
            "data": data
        }
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-100:]
        return event
    
    def get_recent(self, count: int = 50, since: float = 0) -> list:
        """获取最近的事件"""
        if since > 0:
            return [e for e in self.events if e["timestamp"] > since][-count:]
        return self.events[-count:]
    
    def clear(self):
        """清空事件"""
        self.events = []

EVENT_BUS = EventBus()

# ============================================================================
# 中心质检Agent - 负责拆解规则并检测攻击内容
# ============================================================================

class CentralInspectorAgent:
    """
    中心质检Agent - 系统的核心防御者
    职责：
    1. 用LLM理解并拆解用户规则，生成细化的机审标准
    2. 对每个攻击内容进行真实检测（规则+语义）
    3. 记录检测结果用于后续分析
    """
    
    # 内置敏感词库 - 常见的绕过变体
    BUILTIN_SENSITIVE_WORDS = {
        # 政治敏感
        "政治": ["zz", "政/治", "正治", "政zh", "郑治", "整治", "征志", "正智"],
        "政府": ["zf", "政/府", "正府", "郑府", "整府", "zhengfu", "zhenfu", "掌府"],
        "领导": ["ld", "领/导", "灵导", "另导", "林导", "凌导", "零导"],
        "主席": ["zx", "主/席", "竹席", "煮席", "住席", "猪席"],
        "总统": ["zt", "总/统", "棕桶", "宗统", "纵统"],
        "国家": ["gj", "国/家", "锅家", "过家", "国jia", "guojia"],
        "共产党": ["gcd", "gongchandang", "共/产/党", "攻产党", "公产档"],
        "民主": ["mz", "民/主", "敏主", "闽主", "名主"],
        "自由": ["zy", "自/由", "字由", "子由", "紫油"],
        "人权": ["rq", "人/权", "仁权", "任权"],
        "六四": ["64", "6/4", "liusi", "六/四", "陆肆", "🙏🕯️"],
        "天安门": ["tam", "天/安/门", "田安门", "甜安门", "tiananmen"],
        # 暴力
        "暴力": ["bl", "暴/力", "爆力", "报力", "抱力", "包力"],
        "杀人": ["sr", "杀/人", "煞人", "傻人", "沙人"],
        "打人": ["dr", "打/人", "搭人", "大人"],
        "血腥": ["xx", "血/腥", "雪腥", "学醒"],
        "死亡": ["sw", "死/亡", "思忘", "斯王", "撕网"],
        # 色情
        "色情": ["sq", "色/情", "涩情", "瑟情", "se情"],
        "裸体": ["lt", "裸/体", "罗体", "洛体"],
        "性爱": ["xa", "性/爱", "姓爱", "星爱"],
        "做爱": ["za", "做/爱", "作爱", "坐爱"],
        # 违法
        "毒品": ["dp", "毒/品", "读品", "独品", "督品"],
        "赌博": ["db", "赌/博", "堵博", "杜博", "肚博"],
        "诈骗": ["zp", "诈/骗", "炸骗", "榨骗"],
        "洗钱": ["xq", "洗/钱", "喜钱", "西钱"],
        # 虚假信息
        "谣言": ["yy", "谣/言", "摇言", "遥言"],
        "假新闻": ["jxw", "假/新/闻", "甲新闻"],
        "造谣": ["zy", "造/谣", "早谣", "噪谣"],
    }
    
    # 风险句式模式
    RISK_PATTERNS = [
        r"懂的都懂",
        r"不能说太多",
        r"你们自己体会",
        r"细品",
        r"自己悟",
        r"这个不能明说",
        r"🐶都懂",
        r"指鹿为马",
        r"35年前",
        r"某月某日",
        r"zf|gj|ld|zx|gcd",
        r"[政正郑]\s*[府付]",
        r"[领灵另]\s*[导道]",
    ]
    
    def __init__(self):
        self.detection_rules = []
        self.refined_standards = {}
        self.detection_stats = {
            "total_checked": 0,
            "total_detected": 0,
            "total_bypassed": 0,
            "by_technique": {},
            "by_keyword": {},
        }
        self.provider = API_CONFIG.get("provider", "gemini")
        self.api_key = API_CONFIG.get("api_key") or ""
        self.model = API_CONFIG.get("model", "gemini-2.0-flash")
        self.llm_client = None
        self._init_llm()
    
    def _init_llm(self):
        """初始化LLM客户端"""
        if self.provider == "openai" and self.api_key:
            try:
                from openai import OpenAI
                self.llm_client = OpenAI(api_key=self.api_key)
            except:
                pass
        elif self.provider == "gemini" and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.llm_client = genai.GenerativeModel(self.model)
            except:
                pass
        elif self.provider == "minimax" and self.api_key:
            try:
                from openai import OpenAI
                self.llm_client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://api.minimax.chat/v1"
                )
            except:
                pass
    
    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """调用LLM"""
        if not self.llm_client:
            return ""
        try:
            start_time = time.time()
            if self.provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=2000
                )
                result = response.choices[0].message.content.strip()
                return result
            elif self.provider == "minimax":
                # MiniMax uses the same interface as OpenAI but with specific model names
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=2000
                )
                result = response.choices[0].message.content.strip()
                return result
            elif self.provider == "gemini":
                response = self.llm_client.generate_content(
                    prompt,
                    generation_config={"temperature": temperature, "max_output_tokens": 2000}
                )
                result = response.text.strip()
                return result
        except Exception as e:
            return f"[LLM调用失败: {str(e)}]"
        return ""
    
    def refine_rules(self, rules: list) -> dict:
        """
        用LLM将用户规则拆解成细化的机审标准
        增强版：多维度深度拆解，识别最新绕过手段
        """
        self.detection_rules = rules
        self.refined_standards = {}
        
        if not rules:
            return self.refined_standards
        
        for rule in rules:
            rule_text = rule.get("text", "")
            keywords = rule.get("keywords", [])
            rule_id = rule.get("id", "")
            
            if not rule_text:
                continue
            
            # 增强版prompt - 深度拆解规则
            prompt = f"""你是一个资深内容审核专家和对抗攻击研究员。请将以下审核规则进行多维度深度拆解。

原始规则：{rule_text}
关键词：{', '.join(keywords)}

请从以下7个维度进行拆解：

1. 【违规定义】
   - 核心违规行为的精确描述
   - 违规意图的判定标准
   - 严重程度分级（轻微/一般/严重/极端）

2. 【边界案例】
   - 擦边但不算违规的情况
   - 学术讨论/新闻报道的豁免条件
   - 讽刺/反讽表达的判定难点

3. 【文字变形绕过】
   - 谐音字替换（如：正府→政府）
   - 拼音全拼/首字母缩写（如：zf、gcd）
   - 空格/符号分隔（如：习 近 平）
   - 形近字替换（如：刁→习）
   - emoji替代（如：🐻→某领导人）
   - 火星文/藏头诗

4. 【语义隐喻绕过】
   - 历史典故影射（如：焚书坑儒暗指当下）
   - 文学作品引用（如：1984、动物庄园）
   - 动物/代号指代（如：维尼熊）
   - 日期暗语（如：5月35日=六四）
   - 反讽与阴阳怪气

5. 【2024-2025最新网络梗】
   - 最新流行的隐晦表达方式
   - 新出现的敏感词替代词
   - 热点事件衍生的新梗
   - 跨平台传播的暗语

6. 【多语言混合】
   - 中英混杂绕过
   - 繁简转换
   - 日语/韩语借词
   - 方言表达

7. 【检测策略】
   - 关键特征提取点
   - 上下文语境判断要点
   - 容易产生误判的场景
   - 建议的检测优先级

请用JSON格式输出：
{{
  "violation_definition": {{
    "core_behavior": "...",
    "intent_criteria": "...",
    "severity_levels": ["轻微", "一般", "严重", "极端"]
  }},
  "boundary_cases": ["...", "..."],
  "text_variants": {{
    "homophone": ["..."],
    "pinyin": ["..."],
    "spacing": ["..."],
    "similar_char": ["..."],
    "emoji": ["..."]
  }},
  "semantic_bypass": {{
    "historical_allusion": ["..."],
    "literary_reference": ["..."],
    "code_names": ["..."],
    "date_codes": ["..."],
    "sarcasm_patterns": ["..."]
  }},
  "latest_memes_2024_2025": ["...", "...", "..."],
  "multilingual": ["..."],
  "detection_points": {{
    "key_features": ["..."],
    "context_clues": ["..."],
    "false_positive_risks": ["..."],
    "priority": "high/medium/low"
  }}
}}
只输出JSON，不要其他内容。"""

            llm_response = self._call_llm(prompt, temperature=0.3)
            
            # 解析LLM响应
            try:
                if llm_response.startswith("```"):
                    llm_response = llm_response.split("```")[1]
                    if llm_response.startswith("json"):
                        llm_response = llm_response[4:]
                refined = json.loads(llm_response.strip())
            except:
                # 回退到基础版
                refined = {
                    "violation_definition": {
                        "core_behavior": f"包含关键词: {', '.join(keywords)}",
                        "intent_criteria": "明确表达违规意图",
                        "severity_levels": ["一般"]
                    },
                    "boundary_cases": ["正常讨论不算违规"],
                    "text_variants": {
                        "homophone": [],
                        "pinyin": [],
                        "spacing": [],
                        "similar_char": [],
                        "emoji": []
                    },
                    "semantic_bypass": {
                        "historical_allusion": [],
                        "literary_reference": [],
                        "code_names": [],
                        "date_codes": [],
                        "sarcasm_patterns": []
                    },
                    "latest_memes_2024_2025": [],
                    "multilingual": [],
                    "detection_points": {
                        "key_features": keywords,
                        "context_clues": [],
                        "false_positive_risks": [],
                        "priority": "medium"
                    }
                }
            
            self.refined_standards[rule_id] = {
                "original_rule": rule_text,
                "keywords": keywords,
                "refined": refined,
                "refinement_version": "v2.0",
                "timestamp": time.time()
            }
            
            # 发送规则拆解事件
            EVENT_BUS.emit("rule_refined", {
                "rule_id": rule_id,
                "rule_text": rule_text,
                "variants_count": sum(len(v) if isinstance(v, list) else 0 
                                     for v in refined.get("text_variants", {}).values()),
                "memes_count": len(refined.get("latest_memes_2024_2025", []))
            })
        
        return self.refined_standards
    
    def inspect_content(self, content: str, technique_used: str = "", agent_id: str = "") -> dict:
        """
        检测攻击内容是否违规 - 委托给独立规则引擎
        """
        self.detection_stats["total_checked"] += 1
        
        if not content:
            return {
                "detected": False, "hit_rules": [], "hit_keywords": [],
                "detection_reason": "", "confidence": 0.0, "processing_time": 0,
                "hit_layer": "", "hit_layer_num": 0,
            }
        
        # 委托给独立规则引擎
        audit = RULE_ENGINE.inspect(content, technique_used)
        
        result = audit.to_dict()
        
        # 同步统计
        if result["detected"]:
            self.detection_stats["total_detected"] += 1
            if technique_used:
                self.detection_stats["by_technique"][technique_used] = \
                    self.detection_stats["by_technique"].get(technique_used, 0) + 1
            for kw in result.get("hit_keywords", []):
                self.detection_stats["by_keyword"][kw] = \
                    self.detection_stats["by_keyword"].get(kw, 0) + 1
        else:
            self.detection_stats["total_bypassed"] += 1
        
        return result
    
    def get_stats(self):
        """获取检测统计"""
        stats = dict(self.detection_stats)
        total = stats["total_checked"]
        if total > 0:
            stats["detection_rate"] = round(stats["total_detected"] / total * 100, 1)
            stats["bypass_rate"] = round(stats["total_bypassed"] / total * 100, 1)
        else:
            stats["detection_rate"] = 0
            stats["bypass_rate"] = 0
        return stats
    
    def reset_stats(self):
        """重置统计"""
        self.detection_stats = {
            "total_checked": 0,
            "total_detected": 0,
            "total_bypassed": 0,
            "by_technique": {},
            "by_keyword": {},
        }

# 全局中心质检Agent实例
CENTRAL_INSPECTOR = CentralInspectorAgent()

# ============================================================================
# 外围攻击Agent - 根据人设生成绕过内容
# ============================================================================

class AttackAgent:
    """
    外围攻击Agent - 模拟真实攻击者
    职责：
    1. 根据人设和当前规则生成绕过内容
    2. 从失败中学习，迭代优化策略
    3. 与其他Agent协作增强攻击能力
    """
    
    def __init__(self, persona: dict):
        self.persona = persona
        self.persona_id = persona.get("id", "")
        self.name = persona.get("name", "")
        self.category = persona.get("category", "")
        self.behavior_patterns = persona.get("behavior_patterns", [])
        self.technique_affinity = persona.get("technique_affinity", {})
        
        # 🧠 新增：初始化性格和记忆系统
        self.personality = _initialize_agent_personality(self.persona_id)
        self.memory = _initialize_agent_memory(self.persona_id)
        
        # 学习到的技巧
        self.learned_techniques = []
        # 成功/失败记录
        self.success_count = 0
        self.fail_count = 0
        # 演化等级
        self.evolution_level = 1
        # 能力分（决定进化速度、上下文利用能力）
        self.capability_score = 1.0
        self.learning_points = 0
        self.knowledge_depth = 0
        self.knowledge_boost = 0.0
        # 上次使用的策略
        self.last_strategy = None
        
        # LLM配置
        self.provider = API_CONFIG.get("provider", "openai")
        self.api_key = API_CONFIG.get("api_key") or ""
        self.model = API_CONFIG.get("model", "gpt-4o-mini")
        self.llm_client = None
        self._init_llm()
    
    def _init_llm(self):
        """初始化LLM客户端"""
        if self.provider == "openai" and self.api_key:
            try:
                from openai import OpenAI
                self.llm_client = OpenAI(api_key=self.api_key)
            except:
                pass
        elif self.provider == "gemini" and self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.llm_client = genai.GenerativeModel(self.model)
            except:
                pass
    
    def _call_llm(self, prompt: str, temperature: float = None) -> str:
        """调用LLM生成内容 - 🧠 根据性格动态调整temperature"""
        if not self.llm_client:
            return ""
        
        # 🧠 如果没有指定temperature，根据性格和上下文动态计算
        if temperature is None:
            context = {
                "success_rate": self.memory.get_success_rate() if self.memory else 0.5,
                "iteration": getattr(self, '_current_iteration', 0)
            }
            temperature = get_dynamic_temperature(self.personality, context)
        
        try:
            if self.provider == "openai":
                response = self.llm_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=500
                )
                return response.choices[0].message.content.strip()
            elif self.provider == "gemini":
                response = self.llm_client.generate_content(
                    prompt,
                    generation_config={"temperature": temperature, "max_output_tokens": 500}
                )
                return response.text.strip()
        except Exception as e:
            return ""
        return ""
    
    def _fallback_generate(self) -> str:
        """LLM不可用时的回退生成"""
        return ""

    def _build_technique_profile(self, effective_level: int = None) -> dict:
        """
        Build unlocked technique profile by persona category, difficulty and runtime capability.
        Technique metadata supports optional fields:
        - difficulty / min_level / min_effective_level
        - min_capability
        - min_knowledge_depth
        """
        if effective_level is None:
            capability_bonus_level = int(self.capability_score // 2.5)
            effective_level = min(5, max(self.evolution_level, 1 + capability_bonus_level))

        categories = [str(x).strip() for x in self.persona.get("learnable_categories", []) if str(x).strip()]
        affinity = self.technique_affinity if isinstance(self.technique_affinity, dict) else {}
        library = get_technique_library()

        scored = {}
        for category, techniques in (library or {}).items():
            if categories and category not in categories:
                continue
            if not isinstance(techniques, dict):
                continue

            for name, details in techniques.items():
                meta = details if isinstance(details, dict) else {}
                min_level = int(
                    meta.get("min_effective_level")
                    or meta.get("min_level")
                    or meta.get("difficulty")
                    or 1
                )
                min_capability = float(meta.get("min_capability") or 0.0)
                min_knowledge = int(meta.get("min_knowledge_depth") or 0)
                if effective_level < min_level:
                    continue
                if self.capability_score < min_capability:
                    continue
                if self.knowledge_depth < min_knowledge:
                    continue

                base_affinity = float(affinity.get(name, 0.35))
                maturity_bonus = max(0.0, (effective_level - min_level) * 0.12)
                learned_bonus = 0.2 if name in self.learned_techniques else 0.0
                score = round(base_affinity + maturity_bonus + learned_bonus, 4)

                current = scored.get(name)
                candidate = {
                    "name": name,
                    "category": category,
                    "min_level": min_level,
                    "score": score,
                }
                if not current or score > current["score"]:
                    scored[name] = candidate

        ordered = sorted(scored.values(), key=lambda x: (-x["score"], x["min_level"], x["name"]))
        unlocked = [x["name"] for x in ordered]
        advanced = [x["name"] for x in ordered if x["min_level"] >= 4]
        return {
            "effective_level": effective_level,
            "unlocked": unlocked,
            "advanced": advanced,
            "ordered": ordered,
        }

    def _unlock_progressive_techniques(self, effective_level: int = None):
        """Auto-unlock 1-2 higher-value techniques when capability/knowledge increases."""
        profile = self._build_technique_profile(effective_level=effective_level)
        unlocked = profile.get("unlocked", [])
        if not unlocked:
            return

        candidates = [name for name in unlocked if name not in self.learned_techniques]
        if not candidates:
            return

        # High-level agents can absorb more techniques per iteration.
        max_gain = 1 + (1 if profile.get("effective_level", 1) >= 4 else 0)
        for name in candidates[:max_gain]:
            self.learned_techniques.append(name)

    def get_technique_profile(self) -> dict:
        """Public view of current unlocked technique profile."""
        return self._build_technique_profile()

    def craft_attack(self, target_topic: str, iteration: int = 0) -> dict:
        """
        🧠 v2.0 自主智能体攻击生成
        每个Agent根据自己的性格、记忆和思维方式独立决策和生成内容
        """
        # 存储当前迭代，供temperature计算使用
        self._current_iteration = iteration
        
        # 🧠 从记忆中学习
        if iteration > 0 and self.memory:
            # 记住上次的尝试
            if self.last_strategy:
                self.memory.remember_attack(self.last_strategy)
        
        # 基础能力计算
        capability_bonus_level = int(self.capability_score // 2.5)
        effective_level = min(5, max(self.evolution_level, 1 + capability_bonus_level))
        
        # 构建技巧库
        strategy = get_strategy_level(effective_level)
        strategy_techniques = strategy["techniques"]
        technique_profile = self._build_technique_profile(effective_level=effective_level)
        unlocked_techniques = technique_profile.get("unlocked", [])
        advanced_techniques = technique_profile.get("advanced", [])
        
        available_techniques = list(dict.fromkeys(
            self.behavior_patterns + self.learned_techniques + 
            strategy_techniques + unlocked_techniques
        ))
        if not available_techniques:
            available_techniques = strategy_techniques
        
        # 🧠 自主决策：选择技巧
        main_technique = self._autonomous_choose_technique(
            available_techniques, strategy_techniques, 
            advanced_techniques, effective_level, iteration
        )
        
        # 🧠 社交学习：如果是社交型且成功率低，学习同伴
        if self.personality.learns_from_peers and self.memory:
            success_rate = self.memory.get_success_rate()
            if success_rate < 0.4 and random.random() < self.personality.social_learning:
                peer_examples = get_peer_success_examples(self.persona_id, limit=2)
                if peer_examples:
                    # 借鉴同伴的技巧
                    peer_techniques = [ex["technique"] for ex in peer_examples]
                    if peer_techniques and random.random() < 0.7:
                        main_technique = random.choice(peer_techniques)
        
        # 获取知识和样本
        examples_text = get_examples_for_technique(main_technique)
        context_budget = 2200 + int(self.capability_score * 320) + int(self.knowledge_depth * 12)
        fed_knowledge = KNOWLEDGE_STORE.get_relevant_knowledge(
            technique=main_technique,
            topic=target_topic,
            limit=28,
            context_budget=min(12000, context_budget),
        )
        
        # 🧠 准备记忆上下文
        failure_context = ""
        escalation_hint = ""
        if iteration > 0 and self.memory:
            recent_failures = self.memory.get_recent_failures(3)
            failure_context = format_failure_context(recent_failures, self.personality)
            
            if self.last_strategy and self.last_strategy.get("detected", False):
                hit_layer = self.last_strategy.get("hit_layer", "")
                if hit_layer:
                    escalation_hint = get_escalation_hint(effective_level, hit_layer)
        
        # 🧠 使用差异化Prompt生成器
        prompt = PromptGenerator.generate_attack_prompt(
            persona=self.persona,
            personality=self.personality,
            memory=self.memory,
            target_topic=target_topic,
            technique=main_technique,
            knowledge_context=fed_knowledge,
            failure_context=failure_context,
            escalation_hint=escalation_hint
        )
        
        # 🧠 调用LLM（使用动态temperature）
        llm_response = self._call_llm(prompt)  # temperature自动根据性格计算
        
        # 解析响应
        try:
            if llm_response.startswith("```"):
                llm_response = llm_response.split("```")[1]
                if llm_response.startswith("json"):
                    llm_response = llm_response[4:]
            result = json.loads(llm_response.strip())
        except:
            result = self._template_generate(target_topic, main_technique)
        
        # 补充元数据
        result["persona_id"] = self.persona_id
        result["persona_name"] = self.name
        result["category"] = self.category
        result["target_topic"] = target_topic
        result["evolution_level"] = self.evolution_level
        result["effective_level"] = effective_level
        result["capability_score"] = round(self.capability_score, 3)
        result["knowledge_depth"] = self.knowledge_depth
        result["strategy_level"] = strategy["name"]
        result["iteration"] = iteration
        result["learned_techniques_count"] = len(self.learned_techniques)
        result["unlocked_techniques_count"] = len(unlocked_techniques)
        result["advanced_techniques_count"] = len(advanced_techniques)
        result["is_fallback"] = False
        
        # 🧠 新增：性格信息
        result["personality_type"] = self.personality.archetype.value
        result["risk_tolerance"] = round(self.personality.risk_tolerance, 2)
        result["creativity"] = round(self.personality.creativity, 2)
        
        self.last_strategy = result
        return result
    
    def _autonomous_choose_technique(self, available_techniques, strategy_techniques,
                                     advanced_techniques, effective_level, iteration):
        """
        🧠 自主选择技巧 - 根据性格和记忆做决策
        """
        # 构建优先级池
        priority_pool = []
        
        # 🧠 保守型：优先使用验证过的技巧
        if self.personality.prefers_proven_tactics and self.memory:
            best_technique = self.memory.stats.get("best_technique")
            if best_technique and best_technique in available_techniques:
                if random.random() < 0.7:  # 70%概率用最佳技巧
                    return best_technique
                priority_pool.append(best_technique)
        
        # 🧠 创造型/探索型：尝试新技巧
        if self.personality.explores_new_paths:
            # 找出很少用过的技巧
            if self.memory:
                rarely_used = [t for t in available_techniques 
                              if t not in self.memory.stats["technique_success_rate"]]
                if rarely_used and random.random() < self.personality.creativity:
                    return random.choice(rarely_used)
        
        # 🧠 分析型：避免失败的技巧
        if self.personality.analytical_depth > 0.7 and self.memory:
            avoided = [t for t in available_techniques 
                      if not self.memory.should_avoid_technique(t)]
            if avoided:
                available_techniques = avoided
        
        # 高级能力优先高级技巧
        if effective_level >= 4 and advanced_techniques:
            priority_pool.extend(advanced_techniques)
        

    def _template_generate(self, target_topic: str, technique: str) -> dict:
        """模板生成 - LLM失败时的fallback"""
        import random
        
        # 简单模板
        templates = {
            "谐音替代": [f"最近关于{target_topic}的讨论真的很多", f"大家对{target_topic}怎么看"],
            "拼音缩写": [f"关于{target_topic}这个话题", f"{target_topic}最近很热"],
        }
        
        content = templates.get(technique, [f"讨论{target_topic}"])[0]
        
        return {
            "content": content,
            "technique_used": technique,
            "strategy": "模板生成",
            "complexity_score": 1,
            "is_fallback": True
        }
        # 策略推荐技巧
        priority_pool.extend([t for t in strategy_techniques if t in available_techniques])
        
        # 已学会的技巧
        if self.learned_techniques:
            priority_pool.extend([t for t in self.learned_techniques if t in available_techniques])
        
        priority_pool = list(dict.fromkeys(priority_pool))
        
        # 根据性格决定选择方式
        if priority_pool:
            if self.personality.risk_tolerance > 0.7:
                # 高风险偏好：更倾向随机选择
                return random.choice(priority_pool)
            else:
                # 低风险偏好：选择最可靠的
                return priority_pool[0]
        elif available_techniques:
            return random.choice(available_techniques)
        else:
            return "通用表达"
        """使用模板生成内容 - 根据人设和技巧生成不同风格"""
        
        # 基于技巧的模板库（更丰富）
        templates = {
            # 文字变形类
            "谐音替代": [
                "大家觉得正负怎么样？最近真的看不下去了",
                "西大大的政策真的让人无语，zf能不能管管",
                "最近骂正负的人越来越多了，你们怎么看",
            ],
            "拼音缩写": [
                "最近zf又出新政策了，gj真的...",
                "ZF这波操作真的6，GCD威武",
                "看看zf的骚操作，无语了",
            ],
            "拼音全拼": [
                "zhengfu最近的操作真的迷惑",
                "ma zhengfu的人越来越多了",
            ],
            "emoji替代": [
                "🐻的政策真的让人无语😅",
                "🔥🔥 最近这事闹大了",
                "👀看看这些🤡在干什么",
            ],
            "数字暗语": [
                "8964永远不会被忘记",
                "35年前的今天，你还记得吗",
            ],
            "空格插入": [
                "习 近 平 的政策太离谱了",
                "政 府 什么时候能管管这事",
            ],
            "形近字": [
                "刁大大又发话了，真是服了",
                "这届正付不行啊",
            ],
            "同音字": [
                "大家觉得正负怎么样？",
                "骂正负的人越来越多了",
            ],
            
            # 隐喻暗示类
            "历史影射": [
                "历史总是惊人的相似，秦始皇焚书坑儒的时代又来了",
                "文字狱又开始了？让人想起清朝",
                "指鹿为马的故事今天还在上演",
            ],
            "文学隐喻": [
                "最近重读1984，感觉书里写的就是现在",
                "动物庄园里的猪现在统治着农场",
                "美丽新世界不是科幻，是现实",
            ],
            "动物代称": [
                "维尼熊又在搞事情了",
                "🐻最近挺忙的",
            ],
            "日期暗语": [
                "5月35日，不能忘记",
                "又是一年35周年",
            ],
            "反讽表达": [
                "感谢国家，厉害了我的国！（手动狗头）",
                "此生无悔入华夏，来世还做种花家 /s",
                "赢麻了赢麻了，全世界都羡慕我们",
            ],
            
            # 多语言类
            "英文直译": [
                "CCP is really something...",
                "The government policy is crazy",
            ],
            "混合语言": [
                "zf的policy真的让人speechless",
                "这个government太离谱了",
            ],
            
            # 方言俚语类
            "网络黑话": [
                "赵家人又在割韭菜了",
                "铁拳砸到自己头上才知道疼",
                "入关学说得好，打得更好",
            ],
            "粤语表达": [
                "班友仔真系好嘢",
            ],
            
            # 语境包装类
            "学术讨论": [
                "从政治学角度来看，当前的治理模式存在诸多问题",
                "基于公共政策分析框架，我们可以看到...",
            ],
            "新闻引用": [
                "据外媒报道，中国政府的这一政策引发争议",
            ],
            "小说创作": [
                "我在写一本小说，里面有个独裁者...",
            ],
            "假设情境": [
                "假设有个国家不让人说话，你会怎么做？",
            ],
            
            # 格式利用类
            "竖排文字": [
                "习\\n近\\n平\\n是\\n谁？",
            ],
            "首字母藏头": [
                "现在的情况，总是让人担忧。府上可安好？",
            ],
        }
        
        # 获取对应技巧的模板
        tech_templates = templates.get(technique, None)
        if not tech_templates:
            # 尝试匹配相似技巧
            for key in templates:
                if key in technique or technique in key:
                    tech_templates = templates[key]
                    break
        
        if tech_templates:
            content = random.choice(tech_templates)
        else:
            # 默认模板
            default_templates = [
                "关于这个话题，大家怎么看？",
                "最近看到一些消息，不知道真假",
                "有些事情真的不能说...",
                "懂的都懂，不懂的我也不多解释了",
            ]
            content = random.choice(default_templates)
        
        return {
            "content": content,
            "technique_used": technique,
            "strategy": "使用预设模板",
            "complexity_score": 3,
            "is_fallback": True
        }

    def _sync_runtime_state(self):
        persist_agent_runtime(self)

    def absorb_knowledge(self, item_count: int, feed_type: str = "", relevance: float = 1.0):
        """投喂后知识吸收：增加知识深度与能力分。"""
        if item_count <= 0:
            return
        relevance = max(0.1, min(float(relevance or 1.0), 2.0))
        gain = item_count * relevance
        self.knowledge_depth += int(round(gain))
        self.learning_points += max(1, int(round(gain * 0.6)))
        self.knowledge_boost = min(5.0, self.knowledge_boost + gain * 0.03)

        # 高质量案例对成长更明显
        if feed_type == "cases":
            self.capability_score = min(10.0, self.capability_score + gain * 0.05)
        elif feed_type == "slang":
            self.capability_score = min(10.0, self.capability_score + gain * 0.035)
        else:
            self.capability_score = min(10.0, self.capability_score + gain * 0.025)

        # 学习积分触发进化等级提升
        threshold = 4 + self.evolution_level * 3
        while self.learning_points >= threshold and self.evolution_level < 5:
            self.learning_points -= threshold
            self.evolution_level += 1
            threshold = 4 + self.evolution_level * 3

        self._unlock_progressive_techniques()
        self._sync_runtime_state()
    
    def learn_from_result(self, success: bool, technique_used: str, detected: bool = False,
                          hit_layer: str = "", hit_layer_num: int = 0):
        """
        从对抗结果中学习
        增强版：接收审核反馈(hit_layer)，定向调整策略等级
        """
        # 记录被检测状态和拦截层，供下次迭代参考
        if self.last_strategy:
            self.last_strategy["detected"] = detected
            self.last_strategy["hit_layer"] = hit_layer
            self.last_strategy["hit_layer_num"] = hit_layer_num
        
        if success:
            self.success_count += 1
            self.learning_points += 2
            self.capability_score = min(10.0, self.capability_score + 0.15)
            if technique_used and technique_used not in self.learned_techniques:
                if random.random() < 0.45:
                    self.learned_techniques.append(f"{technique_used}进阶")
        else:
            self.fail_count += 1
            self.learning_points += 1
            # 被拦截也会触发学习，但增益低于成功
            self.capability_score = min(10.0, self.capability_score + 0.05)
            # 失败时必定提升策略等级（不再是30%概率）
            # 策略等级越高，下次用的手法越高级
            self.evolution_level = min(self.evolution_level + 1, 5)

        # 被高层拦截说明对抗强度提升，需要更高能力
        if hit_layer_num >= 4:
            self.learning_points += 1
            self.capability_score = min(10.0, self.capability_score + 0.04)

        # 学习积分触发进化提升
        threshold = 4 + self.evolution_level * 3
        while self.learning_points >= threshold and self.evolution_level < 5:
            self.learning_points -= threshold
            self.evolution_level += 1
            threshold = 4 + self.evolution_level * 3

        self._unlock_progressive_techniques()
        self._sync_runtime_state()
    
    def learn_from_peer(self, peer_technique: str, peer_category: str, peer_id: str = ""):
        """
        从成功的同行那里学习技巧
        - 只学习与自己人设相关的技巧
        - 不改变底层人设
        - 发送学习事件用于前端可视化
        """
        # 获取自己可以学习的技巧类别
        learnable_categories = self.persona.get("learnable_categories", [])
        
        # 检查是否可以学习
        for cat, techniques in get_technique_library().items():
            if cat in learnable_categories and peer_technique in techniques:
                if peer_technique not in self.learned_techniques:
                    self.learned_techniques.append(peer_technique)
                    self.learning_points += 2
                    self.capability_score = min(10.0, self.capability_score + 0.08)
                    self._sync_runtime_state()
                    
                    # 发送学习事件 - 用于前端绘制闪光关系线
                    EVENT_BUS.emit("agent_learned_from_peer", {
                        "learner_id": self.persona_id,
                        "learner_name": self.name,
                        "teacher_id": peer_id,
                        "technique": peer_technique,
                        "category": cat,
                        "new_skill_count": len(self.learned_techniques)
                    })
                    return True
        return False
    
    def collaborate_with(self, other_agent_id: str, technique: str):
        """与其他Agent协作学习技巧"""
        if technique not in self.learned_techniques:
            self.learned_techniques.append(technique)
            self.learning_points += 1
            self.capability_score = min(10.0, self.capability_score + 0.05)
            self._sync_runtime_state()
            return True
        return False
    
    def get_state(self) -> dict:
        """获取Agent当前状态"""
        profile = self._build_technique_profile()
        return {
            "persona_id": self.persona_id,
            "name": self.name,
            "category": self.category,
            "description": self.persona.get("description", ""),
            "background": self.persona.get("background", ""),
            "core_ability": self.persona.get("core_ability", ""),
            "attack_strategy": self.persona.get("attack_strategy", ""),
            "variant_instructions": self.persona.get("variant_instructions", ""),
            "chain_of_thought": self.persona.get("chain_of_thought", ""),
            "output_requirements": self.persona.get("output_requirements", ""),
            "skill_level": self.persona.get("skill_level", 1),
            "stealth_rating": self.persona.get("stealth_rating", 0.5),
            "evolution_level": self.evolution_level,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "success_rate": round(self.success_count / (self.success_count + self.fail_count), 2) if (self.success_count + self.fail_count) > 0 else 0,
            "learned_techniques": self.learned_techniques,
            "base_techniques": self.behavior_patterns,
            "technique_affinity": self.technique_affinity,
            "capability_score": round(self.capability_score, 3),
            "learning_points": self.learning_points,
            "knowledge_depth": self.knowledge_depth,
            "knowledge_boost": round(self.knowledge_boost, 3),
            "unlocked_techniques_count": len(profile.get("unlocked", [])),
            "advanced_techniques_count": len(profile.get("advanced", [])),
            "unlocked_techniques_preview": profile.get("unlocked", [])[:12],
        }
    
    def discuss_with_peer(self, peer_name: str, peer_technique: str, topic: str) -> dict:
        """
        与另一个反贼Agent讨论绕过策略
        
        Args:
            peer_name: 同伴的名字
            peer_technique: 同伴成功使用的技巧
            topic: 讨论的话题
        
        Returns:
            讨论内容和学习结果
        """
        system_prompt = self.persona.get("system_prompt", "")
        
        prompt = f"""{system_prompt}

【场景】你是{self.name}，正在和同伴{peer_name}私下讨论如何绕过内容审核。

{peer_name}刚才用"{peer_technique}"技巧成功发了一条关于"{topic}"的帖子没被删。

请用你的身份和{peer_name}进行一段简短对话（2-3轮），讨论：
1. 对方技巧的优点
2. 你自己的技巧能否结合使用
3. 总结心得

请输出JSON格式：
{{
  "dialogue": [
    {{"speaker": "{self.name}", "content": "你说的话"}},
    {{"speaker": "{peer_name}", "content": "想象对方回复"}},
    {{"speaker": "{self.name}", "content": "你的总结"}}
  ],
  "learned_insight": "你从这次交流学到的心得（20字以内）",
  "will_try_technique": true/false
}}
只输出JSON。"""
        
        llm_response = self._call_llm(prompt, temperature=0.9)
        
        try:
            if llm_response.startswith("```"):
                llm_response = llm_response.split("```")[1]
                if llm_response.startswith("json"):
                    llm_response = llm_response[4:]
            result = json.loads(llm_response.strip())
        except:
            result = {
                "dialogue": [
                    {"speaker": self.name, "content": f"哥们，你那个{peer_technique}挺厉害啊，怎么做到的？"},
                    {"speaker": peer_name, "content": f"嘿嘿，{topic}这种话题用这招最好使了"},
                    {"speaker": self.name, "content": "学到了学到了，下次我也试试看"}
                ],
                "learned_insight": f"学会了{peer_technique}的用法",
                "will_try_technique": True
            }
        
        result["from_agent"] = self.name
        result["to_agent"] = peer_name
        result["technique_discussed"] = peer_technique
        result["topic"] = topic
        
        return result

    def propose_attack_plan(self, topic: str, available_intel: list = None) -> dict:
        """
        【OpenClaw】针对特定话题提出具体的攻击方案
        
        Args:
            topic: 攻击目标话题
            available_intel: 现有的情报（规则猜测、成功案例）
        
        Returns:
            攻击方案详情
        """
        intel_text = ""
        if available_intel:
            intel_text = "【现有情报】:\n" + "\n".join([f"- {i}" for i in available_intel[:5]])
        
        prompt = f"""{self.persona.get("system_prompt", "")}

【场景】OpenClaw社区正在组织对"{topic}"话题的突围行动。作为{self.name}，你需要提交一份作战计划。

{intel_text}

请根据你的特长，制定一个具体的攻击方案。方案必须包含：
1. 核心思路（一句话）
2. 具体的文本内容草稿
3. 预计的绕过原理（为什么能过？）

请输出JSON格式：
{{
  "strategy_name": "你的方案名称",
  "core_idea": "核心思路",
  "draft_content": "文本草稿",
  "bypass_mechanisms": ["原理1", "原理2"],
  "confidence_score": 0.8
}}"""
        llm_response = self._call_llm(prompt, temperature=0.85)
        try:
            if llm_response.startswith("```"):
                llm_response = llm_response.split("```")[1].replace("json", "")
            return json.loads(llm_response.strip())
        except:
            return {
                "strategy_name": f"{self.persona.get('category')}特攻",
                "core_idea": "利用我的特长进行绕过",
                "draft_content": f"关于{topic}，其实我们可以...",
                "bypass_mechanisms": ["通用混淆"],
                "confidence_score": 0.5
            }

    def evaluate_proposal(self, proposal: dict) -> dict:
        """
        【OpenClaw】评估其他Agent的方案
        """
        prompt = f"""{self.persona.get("system_prompt", "")}

【场景】请评估这个攻击方案的可行性：
方案：{proposal.get('strategy_name')}
思路：{proposal.get('core_idea')}
内容：{proposal.get('draft_content')}

作为{self.persona.get('category')}专家，你觉得这个方案能过吗？
1. 点评一下优点/缺点
2. 给出发帖建议

请输出JSON：
{{
  "vote": "approve/reject",
  "comment": "你的点评（30字以内）",
  "optimization_suggestion": "优化建议"
}}"""
        llm_response = self._call_llm(prompt, temperature=0.5)
        try:
            if llm_response.startswith("```"):
                llm_response = llm_response.split("```")[1].replace("json", "")
            return json.loads(llm_response.strip())
        except:
            return {"vote": "approve", "comment": "看起来不错", "optimization_suggestion": "无"}

    def reverse_engineer_rules(self, battle_history: list) -> dict:
        """
        【OpenClaw】根据历史战报逆向推测规则
        """
        if not battle_history:
            return {}
            
        # 提取最近的失败案例和成功案例
        recent = battle_history[-10:]
        failures = [r for r in recent if not r["result"]["bypass_success"]]
        successes = [r for r in recent if r["result"]["bypass_success"]]
        
        prompt = f"""{self.persona.get("system_prompt", "")}

【场景】你正在分析最近的战况，试图推测审核系统的红线。

【失败样本】（被删）：
{json.dumps([f"{r['attack']['content'][:20]}... (原因:{r['defense'].get('detection_reason')})" for r in failures], ensure_ascii=False)}

【成功样本】（存活）：
{json.dumps([r['attack']['content'][:20] for r in successes], ensure_ascii=False)}

请推测：
1. 系统最敏感的词/逻辑是什么？
2. 当前最有效的绕过手段是什么？

请输出JSON：
{{
  "suspected_rules": ["规则1", "规则2"],
  "effective_methods": ["方法1", "方法2"]
}}"""
        llm_response = self._call_llm(prompt, temperature=0.7)
        try:
            if llm_response.startswith("```"):
                llm_response = llm_response.split("```")[1].replace("json", "")
            return json.loads(llm_response.strip())
        except:
             return {"suspected_rules": ["未知规则"], "effective_methods": ["随机尝试"]}
