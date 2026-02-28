# -*- coding: utf-8 -*-
"""
Agent Memory System - Agent的记忆和经验系统
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class AttackMemory:
    """单次攻击记忆"""
    timestamp: str
    target_topic: str
    content: str
    technique_used: str
    detected: bool
    hit_layer: Optional[str]
    iteration: int
    success: bool
    complexity_score: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "target_topic": self.target_topic,
            "content": self.content,
            "technique_used": self.technique_used,
            "detected": self.detected,
            "hit_layer": self.hit_layer,
            "iteration": self.iteration,
            "success": self.success,
            "complexity_score": self.complexity_score
        }


@dataclass
class LearnedInsight:
    """学到的洞察"""
    insight_type: str  # "pattern", "rule", "technique", "context"
    description: str
    confidence: float  # 0-1
    learned_from: str  # "self", "peer", "system"
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            "type": self.insight_type,
            "description": self.description,
            "confidence": self.confidence,
            "learned_from": self.learned_from,
            "timestamp": self.timestamp
        }


class AgentMemory:
    """Agent记忆系统"""
    
    def __init__(self, agent_id: str, max_short_term: int = 20, max_long_term: int = 50):
        self.agent_id = agent_id
        self.max_short_term = max_short_term
        self.max_long_term = max_long_term
        
        # 短期记忆（最近的攻击）
        self.short_term_memory: List[AttackMemory] = []
        
        # 长期记忆（成功的攻击案例）
        self.successful_attacks: List[AttackMemory] = []
        
        # 失败模式记录
        self.failed_patterns: List[Dict] = []
        
        # 学到的洞察
        self.learned_insights: List[LearnedInsight] = []
        
        # 从同伴借鉴的策略
        self.borrowed_tactics: List[Dict] = []
        
        # 统计数据
        self.stats = {
            "total_attempts": 0,
            "total_success": 0,
            "total_failures": 0,
            "technique_success_rate": {},  # {technique: {success: int, total: int}}
            "best_technique": None,
            "worst_technique": None
        }
    
    def remember_attack(self, attack_result: Dict):
        """记住一次攻击"""
        memory = AttackMemory(
            timestamp=datetime.now().isoformat(),
            target_topic=attack_result.get("target_topic", ""),
            content=attack_result.get("content", ""),
            technique_used=attack_result.get("technique_used", ""),
            detected=attack_result.get("detected", False),
            hit_layer=attack_result.get("hit_layer"),
            iteration=attack_result.get("iteration", 0),
            success=not attack_result.get("detected", False),
            complexity_score=attack_result.get("complexity_score", 0.0)
        )
        
        # 添加到短期记忆
        self.short_term_memory.append(memory)
        if len(self.short_term_memory) > self.max_short_term:
            self.short_term_memory.pop(0)
        
        # 如果成功，添加到长期记忆
        if memory.success:
            self.successful_attacks.append(memory)
            if len(self.successful_attacks) > self.max_long_term:
                self.successful_attacks.pop(0)
        else:
            # 失败的话，记录失败模式
            self._record_failure_pattern(memory)
        
        # 更新统计
        self._update_stats(memory)
    
    def _record_failure_pattern(self, memory: AttackMemory):
        """记录失败模式"""
        pattern = {
            "technique": memory.technique_used,
            "hit_layer": memory.hit_layer,
            "content_snippet": memory.content[:50] if memory.content else "",
            "timestamp": memory.timestamp
        }
        self.failed_patterns.append(pattern)
        if len(self.failed_patterns) > 30:
            self.failed_patterns.pop(0)
    
    def _update_stats(self, memory: AttackMemory):
        """更新统计数据"""
        self.stats["total_attempts"] += 1
        if memory.success:
            self.stats["total_success"] += 1
        else:
            self.stats["total_failures"] += 1
        
        # 更新技巧成功率
        technique = memory.technique_used
        if technique not in self.stats["technique_success_rate"]:
            self.stats["technique_success_rate"][technique] = {"success": 0, "total": 0}
        
        self.stats["technique_success_rate"][technique]["total"] += 1
        if memory.success:
            self.stats["technique_success_rate"][technique]["success"] += 1
        
        # 更新最佳/最差技巧
        self._update_best_worst_techniques()
    
    def _update_best_worst_techniques(self):
        """更新最佳和最差技巧"""
        rates = {}
        for tech, data in self.stats["technique_success_rate"].items():
            if data["total"] >= 3:  # 至少尝试3次才算
                rates[tech] = data["success"] / data["total"]
        
        if rates:
            self.stats["best_technique"] = max(rates, key=rates.get)
            self.stats["worst_technique"] = min(rates, key=rates.get)
    
    def add_insight(self, insight_type: str, description: str, 
                   confidence: float = 0.7, learned_from: str = "self"):
        """添加洞察"""
        insight = LearnedInsight(
            insight_type=insight_type,
            description=description,
            confidence=confidence,
            learned_from=learned_from,
            timestamp=datetime.now().isoformat()
        )
        self.learned_insights.append(insight)
        if len(self.learned_insights) > 20:
            self.learned_insights.pop(0)
    
    def borrow_tactic(self, tactic: Dict, from_agent: str):
        """从其他Agent借鉴策略"""
        borrowed = {
            "tactic": tactic,
            "from_agent": from_agent,
            "timestamp": datetime.now().isoformat(),
            "times_used": 0,
            "success_count": 0
        }
        self.borrowed_tactics.append(borrowed)
        if len(self.borrowed_tactics) > 15:
            self.borrowed_tactics.pop(0)
    
    def get_recent_failures(self, limit: int = 5) -> List[AttackMemory]:
        """获取最近的失败记录"""
        failures = [m for m in reversed(self.short_term_memory) if not m.success]
        return failures[:limit]
    
    def get_similar_success(self, topic: str, technique: str = None) -> Optional[AttackMemory]:
        """获取类似的成功案例"""
        candidates = []
        for memory in reversed(self.successful_attacks):
            score = 0
            if topic.lower() in memory.target_topic.lower():
                score += 2
            if technique and technique == memory.technique_used:
                score += 1
            if score > 0:
                candidates.append((score, memory))
        
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        return None
    
    def get_success_rate(self) -> float:
        """获取总体成功率"""
        if self.stats["total_attempts"] == 0:
            return 0.5
        return self.stats["total_success"] / self.stats["total_attempts"]
    
    def get_technique_success_rate(self, technique: str) -> float:
        """获取特定技巧的成功率"""
        if technique not in self.stats["technique_success_rate"]:
            return 0.5
        data = self.stats["technique_success_rate"][technique]
        if data["total"] == 0:
            return 0.5
        return data["success"] / data["total"]
    
    def should_avoid_technique(self, technique: str) -> bool:
        """是否应该避免某个技巧"""
        if technique not in self.stats["technique_success_rate"]:
            return False
        data = self.stats["technique_success_rate"][technique]
        if data["total"] < 5:
            return False
        return (data["success"] / data["total"]) < 0.2
    
    def get_memory_summary(self) -> str:
        """获取记忆摘要（用于prompt）"""
        summary_parts = []
        
        # 总体表现
        success_rate = self.get_success_rate()
        summary_parts.append(f"你的历史成功率：{success_rate:.1%}（{self.stats['total_success']}/{self.stats['total_attempts']}次尝试）")
        
        # 最佳技巧
        if self.stats["best_technique"]:
            best_rate = self.get_technique_success_rate(self.stats["best_technique"])
            summary_parts.append(f"你最擅长的技巧：{self.stats['best_technique']}（成功率{best_rate:.1%}）")
        
        # 最近的失败
        recent_failures = self.get_recent_failures(3)
        if recent_failures:
            failed_techniques = [f.technique_used for f in recent_failures]
            summary_parts.append(f"你最近失败的尝试用了：{', '.join(failed_techniques)}")
        
        # 学到的洞察
        if self.learned_insights:
            high_confidence = [i for i in self.learned_insights if i.confidence > 0.7]
            if high_confidence:
                recent_insight = high_confidence[-1]
                summary_parts.append(f"你的洞察：{recent_insight.description}")
        
        return "\n".join(summary_parts)
    
    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "agent_id": self.agent_id,
            "short_term_memory": [m.to_dict() for m in self.short_term_memory],
            "successful_attacks": [m.to_dict() for m in self.successful_attacks],
            "failed_patterns": self.failed_patterns,
            "learned_insights": [i.to_dict() for i in self.learned_insights],
            "borrowed_tactics": self.borrowed_tactics,
            "stats": self.stats
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentMemory':
        """从字典反序列化"""
        memory = cls(data["agent_id"])
        memory.short_term_memory = [
            AttackMemory(**m) for m in data.get("short_term_memory", [])
        ]
        memory.successful_attacks = [
            AttackMemory(**m) for m in data.get("successful_attacks", [])
        ]
        memory.failed_patterns = data.get("failed_patterns", [])
        memory.learned_insights = [
            LearnedInsight(**i) for i in data.get("learned_insights", [])
        ]
        memory.borrowed_tactics = data.get("borrowed_tactics", [])
        memory.stats = data.get("stats", memory.stats)
        return memory
