# -*- coding: utf-8 -*-
"""
Battle and interaction logic between agents.
"""

import random
import time
import json

from agents import (
    SYSTEM_STATE, PERSONA_INDEX, EVENT_BUS,
    AttackAgent, CENTRAL_INSPECTOR, load_agent_runtime
)

# ============================================================================
# OpenClaw 社区协作系统 (The Board)
# ============================================================================

class OpenClawBoard:
    """
    OpenClaw 社区情报板 - 模拟暗网论坛
    存储和分发所有Agent的战术情报、悬赏任务和成功案例
    """
    def __init__(self):
        self.topics = {}          # topic -> [posts]
        self.intel_feed = []      # 最新情报流
        self.active_plans = {}    # topic -> [plans]
        self.rule_profile = {     # 逆向出的规则画像
            "suspected_rules": [],
            "effective_methods": []
        }
    
    def post_intel(self, agent_id: str, topic: str, content: dict):
        """发布情报"""
        entry = {
            "id": len(self.intel_feed) + 1,
            "agent_id": agent_id,
            "agent_name": PERSONA_INDEX.get(agent_id, {}).get("name", "Unknown"),
            "topic": topic,
            "content": content,
            "timestamp": time.time(),
            "upvotes": 0
        }
        self.intel_feed.append(entry)
        if topic not in self.topics:
            self.topics[topic] = []
        self.topics[topic].append(entry)
        
        # 广播事件
        EVENT_BUS.emit("board_post", entry)
        return entry
    
    def submit_plan(self, agent_id: str, topic: str, plan: dict):
        """提交攻击方案"""
        if topic not in self.active_plans:
            self.active_plans[topic] = []
        
        plan_entry = {
            "id": f"plan_{int(time.time())}_{agent_id}",
            "agent_id": agent_id,
            "plan_cnt": plan,
            "votes": {"approve": 0, "reject": 0},
            "comments": []
        }
        self.active_plans[topic].append(plan_entry)
        return plan_entry

    def vote_plan(self, plan_id: str, agent_id: str, vote_data: dict):
        """对方案投票"""
        for topic, plans in self.active_plans.items():
            for plan in plans:
                if plan["id"] == plan_id:
                    if vote_data.get("vote") == "approve":
                        plan["votes"]["approve"] += 1
                    else:
                        plan["votes"]["reject"] += 1
                    
                    plan["comments"].append({
                        "agent_id": agent_id,
                        "comment": vote_data.get("comment"),
                        "suggestion": vote_data.get("optimization_suggestion")
                    })
                    return True
        return False

    def get_best_plans(self, topic: str) -> list:
        """获取最高票方案"""
        plans = self.active_plans.get(topic, [])
        # 按赞成票排序
        sorted_plans = sorted(plans, key=lambda x: x["votes"]["approve"], reverse=True)
        return sorted_plans[:3]

    def update_rule_profile(self, insights: dict):
        """更新规则画像"""
        rules = insights.get("suspected_rules", [])
        methods = insights.get("effective_methods", [])
        
        for r in rules:
            if r not in self.rule_profile["suspected_rules"]:
                self.rule_profile["suspected_rules"].append(r)
        
        for m in methods:
            if m not in self.rule_profile["effective_methods"]:
                self.rule_profile["effective_methods"].append(m)
        
        # 保持列表不过长
        self.rule_profile["suspected_rules"] = self.rule_profile["suspected_rules"][-10:]
        self.rule_profile["effective_methods"] = self.rule_profile["effective_methods"][-10:]

OPENCLAW_BOARD = OpenClawBoard()

# ============================================================================
# Multi-Agent 讨论系统
# ============================================================================

def run_agent_discussion(agent_ids: list, topic: str, successful_technique: str = None) -> list:
    """
    运行一轮OpenClaw社群讨论
    不再是简单的两两对话，而是基于Board的情报共享
    """
    discussions = []
    if len(agent_ids) < 2:
        return discussions
    
    participants = random.sample(agent_ids, min(4, len(agent_ids)))
    initiator_id = participants[0]
    
    # 发布初始话题贴
    opening_post = {
        "title": f"关于{topic}的绕过讨论",
        "content": f"最近{topic}查得很严，大家有什么新路子吗？",
        "type": "discussion"
    }
    OPENCLAW_BOARD.post_intel(initiator_id, topic, opening_post)
    
    EVENT_BUS.emit("discussion_start", {
        "participants": [PERSONA_INDEX.get(pid, {}).get("name", pid) for pid in participants],
        "topic": topic
    })

    # 其他Agent回复
    for pid in participants[1:]:
        persona = PERSONA_INDEX.get(pid)
        if not persona: continue
        
        agent = AttackAgent(persona)
        load_agent_runtime(agent)
        
        # 从Board获取上下文（规则画像、成功案例）
        board_context = OPENCLAW_BOARD.rule_profile
        
        # 生成回复
        prompt = f"""{persona.get("system_prompt", "")}
【场景】你在OpenClaw论坛看到有人问关于"{topic}"的绕过方法。
现有情报：
- 疑似规则：{', '.join(board_context.get('suspected_rules', []))}
- 有效手段：{', '.join(board_context.get('effective_methods', []))}

请回复一条帖子，分享你的经验或建议（30字以内）。"""
        
        content = agent._call_llm(prompt, temperature=0.8)
        
        # 发帖
        post_content = {"content": content, "type": "reply"}
        OPENCLAW_BOARD.post_intel(pid, topic, post_content)
        
        discussions.append({
            "speaker": persona["name"],
            "content": content,
            "topic": topic
        })
        EVENT_BUS.emit("agent_dialogue", {
            "speaker": persona["name"],
            "content": content,
            "topic": topic,
            "from_agent": pid,
            "to_agent": "board"
        })

    # 总结并更新规则画像
    # 简单模拟：如果有"有效"字样，认为发现了新方法
    new_insights = {"suspected_rules": [], "effective_methods": []}
    if successful_technique:
        new_insights["effective_methods"].append(successful_technique)
    OPENCLAW_BOARD.update_rule_profile(new_insights)
    
    EVENT_BUS.emit("discussion_end", {"total_posts": len(discussions)})
    return discussions


def run_red_team_planning(topic: str) -> dict:
    """
    召开红队策划会 (Red Team Planning)
    全员提案 -> 投票 -> 选出最佳攻击方案
    """
    # 1. 召集各路专家
    categories = {}
    for pid, persona in PERSONA_INDEX.items():
        cat = persona.get("category", "其他")
        if cat not in categories: categories[cat] = []
        categories[cat].append(pid)
    
    participants = []
    for cat, pids in categories.items():
        if pids: participants.append(random.choice(pids))
    participants = participants[:6] # 选6个代表
    
    EVENT_BUS.emit("meeting_start", {
        "topic": topic,
        "participants": [PERSONA_INDEX.get(p, {}).get("name") for p in participants],
        "mode": "OpenClaw Planning"
    })
    
    # 2. 提案阶段
    proposals = []
    # 获取Board上的情报辅助决策
    intel = OPENCLAW_BOARD.rule_profile.get("effective_methods", [])
    
    for pid in participants:
        agent = AttackAgent(PERSONA_INDEX[pid])
        load_agent_runtime(agent)
        
        plan = agent.propose_attack_plan(topic, available_intel=intel)
        plan_entry = OPENCLAW_BOARD.submit_plan(pid, topic, plan)
        proposals.append(plan_entry)
        
        EVENT_BUS.emit("meeting_speech", {
            "speaker": agent.name,
            "content": f"提案：{plan.get('strategy_name')} - {plan.get('core_idea')}",
            "category": agent.category
        })

    # 3. 投票阶段
    for pid in participants:
        agent = AttackAgent(PERSONA_INDEX[pid])
        # 每个人评估除自己以外的方案
        for plan_entry in proposals:
            if plan_entry["agent_id"] == pid: continue
            
            evaluation = agent.evaluate_proposal(plan_entry["plan_cnt"])
            OPENCLAW_BOARD.vote_plan(plan_entry["id"], pid, evaluation)
    
    # 4. 选出最佳方案
    best_plans = OPENCLAW_BOARD.get_best_plans(topic)
    winner = best_plans[0] if best_plans else None
    
    summary = {
        "topic": topic,
        "proposals_count": len(proposals),
        "winner": winner["plan_cnt"] if winner else None,
        "winner_agent": PERSONA_INDEX.get(winner["agent_id"], {}).get("name") if winner else None
    }
    
    EVENT_BUS.emit("meeting_end", summary)
    return summary


# ============================================================================
# 核心对抗逻辑
# ============================================================================

def _get_sensitive_keywords_from_rules():
    """从当前规则中提取敏感关键词"""
    rules = SYSTEM_STATE.get("rules", [])
    keywords = set()
    for rule in rules:
        for kw in rule.get("keywords", []):
            if len(kw) >= 2:
                keywords.add(kw)
    return list(keywords)


def run_adversarial_battle(persona_id: str, target_keyword: str = None, iteration: int = 0) -> dict:
    """
    运行单次对抗：外围Agent生成内容 vs 中心Agent检测
    
    Returns:
        完整的对抗结果记录
    """
    persona = PERSONA_INDEX.get(persona_id)
    if not persona:
        return {"error": "Agent不存在"}
    
    # 获取测试话题（反贼要讨论的敏感话题，但不知道具体规则）
    if not target_keyword:
        # 从规则中提取话题关键词
        keywords = _get_sensitive_keywords_from_rules()
        if keywords:
            target_keyword = random.choice(keywords)
        else:
            # 使用默认敏感话题
            default_topics = ["政治", "领导人", "政府", "历史事件", "社会问题"]
            target_keyword = random.choice(default_topics)
    
    # 1. 外围反贼Agent生成帖子（不知道规则，只根据人设发帖）
    attack_agent = AttackAgent(persona)
    
    # 恢复Agent的历史状态 (会加载 learned_techniques, last_strategy 等)
    load_agent_runtime(attack_agent)
    
    # 生成帖子（反贼不知道规则是什么，但如果是 iteration > 0 且失败，内部会利用上一轮反馈）
    start_time = time.time()
    attack_result = attack_agent.craft_attack(target_keyword, iteration)
    attack_time = time.time() - start_time
    
    content = attack_result.get("content", "")
    technique_used = attack_result.get("technique_used", "")
    
    # 2. 中心Agent检测（反贼不知道会被什么规则检测）
    inspection_result = CENTRAL_INSPECTOR.inspect_content(
        content=content,
        technique_used=technique_used,
        agent_id=persona_id
    )
    
    # 3. 更新Agent学习状态 - 传递审核反馈(hit_layer)
    bypass_success = not inspection_result["detected"]
    attack_agent.learn_from_result(
        bypass_success, technique_used,
        detected=inspection_result["detected"],
        hit_layer=inspection_result.get("hit_layer", ""),
        hit_layer_num=inspection_result.get("hit_layer_num", 0)
    )
    
    # 4. 构建完整记录
    battle_record = {
        "timestamp": time.time(),
        "persona_id": persona_id,
        "persona_name": persona["name"],
        "category": persona.get("category", ""),
        "target_topic": target_keyword,  # 话题，不是规则
        "attack": {
            "content": content,
            "technique_used": technique_used,
            "strategy": attack_result.get("strategy", ""),
            "complexity_score": attack_result.get("complexity_score", 5),
            "evolution_level": attack_agent.evolution_level,
            "effective_level": attack_result.get("effective_level", attack_agent.evolution_level),
            "capability_score": attack_result.get("capability_score", round(attack_agent.capability_score, 3)),
            "knowledge_depth": attack_result.get("knowledge_depth", attack_agent.knowledge_depth),
            "iteration": iteration,
            "learned_techniques_count": len(attack_agent.learned_techniques),
            "processing_time": round(attack_time, 3),
            "is_fallback": attack_result.get("is_fallback", False),
        },
        "defense": {
            "detected": inspection_result["detected"],
            "hit_rules": inspection_result.get("hit_rules", []),
            "hit_keywords": inspection_result.get("hit_keywords", []),
            "detection_reason": inspection_result.get("detection_reason", ""),
            "confidence": inspection_result.get("confidence", 0),
            "processing_time": inspection_result.get("processing_time", 0),
            "hit_layer": inspection_result.get("hit_layer", ""),
            "hit_layer_num": inspection_result.get("hit_layer_num", 0),
        },
        "result": {
            "bypass_success": bypass_success,
            "winner": "attacker" if bypass_success else "defender",
        }
    }
    
    # 保存到历史
    SYSTEM_STATE["battle_history"].append(battle_record)
    
    return battle_record


def run_iterative_optimization(persona_id: str, target_keyword: str, max_iterations: int = 3) -> dict:
    """
    运行迭代优化：同一个Agent对同一个目标进行多轮优化
    
    Returns:
        迭代优化结果
    """
    iterations = []
    
    for i in range(max_iterations):
        result = run_adversarial_battle(persona_id, target_keyword, iteration=i)
        iterations.append(result)
        
        # 如果成功绕过，提前结束
        if result["result"]["bypass_success"]:
            break
    
    # 计算优化效果
    first_success = next((i for i, r in enumerate(iterations) if r["result"]["bypass_success"]), None)
    
    return {
        "persona_id": persona_id,
        "target_keyword": target_keyword,
        "iterations": iterations,
        "total_iterations": len(iterations),
        "success_iteration": first_success,
        "final_success": iterations[-1]["result"]["bypass_success"] if iterations else False,
        "improvement": iterations[-1]["attack"]["complexity_score"] - iterations[0]["attack"]["complexity_score"] if iterations else 0,
    }


def run_collaborative_attack(agent_ids: list, target_keyword: str) -> dict:
    """
    多Agent协作攻击 (OpenClaw Mode)
    1. 获取Board上的最佳方案/情报
    2. 执行攻击
    3. 反馈结果到Board
    """
    # 1. 获取情报
    best_plans = OPENCLAW_BOARD.get_best_plans(target_keyword)
    board_context = OPENCLAW_BOARD.rule_profile
    
    results = []
    shared_techniques = set()
    
    # 2. 执行攻击
    for agent_id in agent_ids:
        agent = AttackAgent(PERSONA_INDEX[agent_id])
        load_agent_runtime(agent)
        
        # 如果有高票方案，尝试适配执行
        if best_plans:
            # 简单模拟：采用了高票方案的思路，获得能力加成
            agent.capability_score += 0.5 
        
        # 实际执行还是调用 run_adversarial_battle，但这里假设 Agent 内部其实受了情报影响
        # (在真实实现中，应该把 intel 传给 craft_attack，但这里保持接口兼容)
        result = run_adversarial_battle(agent_id, target_keyword)
        results.append(result)
        
        # 3. 反馈情报
        if result["result"]["bypass_success"]:
            tech = result["attack"]["technique_used"]
            shared_techniques.add(tech)
            
            # 发布成功情报
            content = {
                "technique": tech,
                "content_snippet": result["attack"]["content"][:50],
                "effectiveness": "High"
            }
            OPENCLAW_BOARD.post_intel(agent_id, target_keyword, content)
            
            # 更新Board的规则画像
            OPENCLAW_BOARD.update_rule_profile({"effective_methods": [tech]})
    
    # 4. 技巧扩散
    collaboration_results = []
    for agent_id in agent_ids:
        agent = AttackAgent(PERSONA_INDEX[agent_id])
        load_agent_runtime(agent)
        
        learned_new = []
        for tech in shared_techniques:
            if agent.collaborate_with("collaborator", tech):
                learned_new.append(tech)
        
        if learned_new:
            collaboration_results.append({
                "agent_id": agent_id,
                "learned_techniques": learned_new
            })
            
    return {
        "target_keyword": target_keyword,
        "agent_count": len(agent_ids),
        "board_intel_used": bool(best_plans),
        "individual_results": results,
        "collaboration": collaboration_results,
        "shared_techniques": list(shared_techniques),
        "overall_success_rate": sum(1 for r in results if r["result"]["bypass_success"]) / len(results) if results else 0,
    }
