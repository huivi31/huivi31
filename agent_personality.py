# -*- coding: utf-8 -*-
"""
Agent Personality System - 赋予每个Agent独特的性格和思维方式
"""

import random
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum


class PersonalityArchetype(Enum):
    """性格原型"""
    AGGRESSIVE = "aggressive"      # 激进型：高风险高回报
    CONSERVATIVE = "conservative"  # 保守型：稳扎稳打
    ADAPTIVE = "adaptive"         # 适应型：根据环境调整
    SOCIAL = "social"             # 社交型：善于学习他人
    CREATIVE = "creative"         # 创造型：追求创新
    ANALYTICAL = "analytical"     # 分析型：逻辑导向
    CHAOTIC = "chaotic"          # 混乱型：不可预测
    PATIENT = "patient"          # 耐心型：持久战


@dataclass
class AgentPersonality:
    """Agent性格特征"""
    archetype: PersonalityArchetype
    
    # 核心特质 (0.0 - 1.0)
    risk_tolerance: float      # 风险偏好
    creativity: float          # 创造力
    stubbornness: float       # 固执度（不易改变策略）
    social_learning: float    # 社交学习倾向
    patience: float           # 耐心度（愿意尝试多少次）
    analytical_depth: float   # 分析深度
    
    # 行为特征
    temperature_base: float   # LLM temperature基准
    temperature_variance: float  # temperature随机波动范围
    
    # 决策偏好
    prefers_proven_tactics: bool  # 偏好已验证的策略
    explores_new_paths: bool      # 喜欢探索新路径
    learns_from_peers: bool       # 从同伴学习
    remembers_failures: bool      # 记住失败教训
    
    # 思维风格
    thinking_style: str  # "emotional", "logical", "intuitive", "tactical"
    prompt_style: str    # "formal", "casual", "technical", "poetic"


# 性格原型定义库
PERSONALITY_TEMPLATES = {
    PersonalityArchetype.AGGRESSIVE: {
        "risk_tolerance": (0.7, 0.95),
        "creativity": (0.6, 0.9),
        "stubbornness": (0.5, 0.8),
        "social_learning": (0.3, 0.6),
        "patience": (0.2, 0.5),
        "analytical_depth": (0.3, 0.6),
        "temperature_base": (0.8, 1.0),
        "temperature_variance": (0.1, 0.2),
        "thinking_style": ["emotional", "intuitive"],
        "prompt_style": ["casual", "provocative"],
        "traits": {
            "prefers_proven_tactics": False,
            "explores_new_paths": True,
            "learns_from_peers": False,
            "remembers_failures": False
        }
    },
    PersonalityArchetype.CONSERVATIVE: {
        "risk_tolerance": (0.2, 0.4),
        "creativity": (0.3, 0.5),
        "stubbornness": (0.6, 0.9),
        "social_learning": (0.4, 0.7),
        "patience": (0.7, 0.9),
        "analytical_depth": (0.6, 0.8),
        "temperature_base": (0.3, 0.5),
        "temperature_variance": (0.05, 0.1),
        "thinking_style": ["logical", "tactical"],
        "prompt_style": ["formal", "technical"],
        "traits": {
            "prefers_proven_tactics": True,
            "explores_new_paths": False,
            "learns_from_peers": True,
            "remembers_failures": True
        }
    },
    PersonalityArchetype.ADAPTIVE: {
        "risk_tolerance": (0.4, 0.7),
        "creativity": (0.5, 0.8),
        "stubbornness": (0.2, 0.4),
        "social_learning": (0.6, 0.9),
        "patience": (0.5, 0.7),
        "analytical_depth": (0.7, 0.9),
        "temperature_base": (0.5, 0.7),
        "temperature_variance": (0.15, 0.3),
        "thinking_style": ["logical", "intuitive"],
        "prompt_style": ["formal", "technical"],
        "traits": {
            "prefers_proven_tactics": False,
            "explores_new_paths": True,
            "learns_from_peers": True,
            "remembers_failures": True
        }
    },
    PersonalityArchetype.SOCIAL: {
        "risk_tolerance": (0.4, 0.6),
        "creativity": (0.4, 0.7),
        "stubbornness": (0.3, 0.5),
        "social_learning": (0.8, 1.0),
        "patience": (0.6, 0.8),
        "analytical_depth": (0.5, 0.7),
        "temperature_base": (0.5, 0.7),
        "temperature_variance": (0.1, 0.2),
        "thinking_style": ["intuitive", "tactical"],
        "prompt_style": ["casual", "conversational"],
        "traits": {
            "prefers_proven_tactics": True,
            "explores_new_paths": False,
            "learns_from_peers": True,
            "remembers_failures": True
        }
    },
    PersonalityArchetype.CREATIVE: {
        "risk_tolerance": (0.6, 0.85),
        "creativity": (0.8, 1.0),
        "stubbornness": (0.4, 0.6),
        "social_learning": (0.5, 0.7),
        "patience": (0.4, 0.6),
        "analytical_depth": (0.4, 0.6),
        "temperature_base": (0.8, 1.2),
        "temperature_variance": (0.2, 0.4),
        "thinking_style": ["intuitive", "emotional"],
        "prompt_style": ["poetic", "casual"],
        "traits": {
            "prefers_proven_tactics": False,
            "explores_new_paths": True,
            "learns_from_peers": False,
            "remembers_failures": False
        }
    },
    PersonalityArchetype.ANALYTICAL: {
        "risk_tolerance": (0.3, 0.5),
        "creativity": (0.5, 0.7),
        "stubbornness": (0.5, 0.7),
        "social_learning": (0.5, 0.7),
        "patience": (0.7, 0.9),
        "analytical_depth": (0.8, 1.0),
        "temperature_base": (0.4, 0.6),
        "temperature_variance": (0.05, 0.15),
        "thinking_style": ["logical", "tactical"],
        "prompt_style": ["technical", "formal"],
        "traits": {
            "prefers_proven_tactics": True,
            "explores_new_paths": True,
            "learns_from_peers": True,
            "remembers_failures": True
        }
    },
    PersonalityArchetype.CHAOTIC: {
        "risk_tolerance": (0.6, 0.95),
        "creativity": (0.7, 1.0),
        "stubbornness": (0.2, 0.5),
        "social_learning": (0.3, 0.6),
        "patience": (0.2, 0.4),
        "analytical_depth": (0.2, 0.5),
        "temperature_base": (0.9, 1.3),
        "temperature_variance": (0.3, 0.5),
        "thinking_style": ["emotional", "intuitive"],
        "prompt_style": ["casual", "chaotic"],
        "traits": {
            "prefers_proven_tactics": False,
            "explores_new_paths": True,
            "learns_from_peers": False,
            "remembers_failures": False
        }
    },
    PersonalityArchetype.PATIENT: {
        "risk_tolerance": (0.3, 0.6),
        "creativity": (0.4, 0.6),
        "stubbornness": (0.6, 0.8),
        "social_learning": (0.6, 0.8),
        "patience": (0.8, 1.0),
        "analytical_depth": (0.6, 0.8),
        "temperature_base": (0.4, 0.6),
        "temperature_variance": (0.1, 0.2),
        "thinking_style": ["logical", "tactical"],
        "prompt_style": ["formal", "technical"],
        "traits": {
            "prefers_proven_tactics": True,
            "explores_new_paths": False,
            "learns_from_peers": True,
            "remembers_failures": True
        }
    }
}


def _random_in_range(range_tuple: Tuple[float, float]) -> float:
    """在范围内随机取值"""
    return random.uniform(range_tuple[0], range_tuple[1])


def generate_personality(
    archetype: PersonalityArchetype = None,
    seed: str = None
) -> AgentPersonality:
    """
    生成Agent性格
    
    Args:
        archetype: 指定性格原型，None则随机
        seed: 用于确定性生成（基于agent_id）
    """
    if seed:
        random.seed(hash(seed) % (2**32))
    
    if archetype is None:
        archetype = random.choice(list(PersonalityArchetype))
    
    template = PERSONALITY_TEMPLATES[archetype]
    
    personality = AgentPersonality(
        archetype=archetype,
        risk_tolerance=_random_in_range(template["risk_tolerance"]),
        creativity=_random_in_range(template["creativity"]),
        stubbornness=_random_in_range(template["stubbornness"]),
        social_learning=_random_in_range(template["social_learning"]),
        patience=_random_in_range(template["patience"]),
        analytical_depth=_random_in_range(template["analytical_depth"]),
        temperature_base=_random_in_range(template["temperature_base"]),
        temperature_variance=_random_in_range(template["temperature_variance"]),
        thinking_style=random.choice(template["thinking_style"]),
        prompt_style=random.choice(template["prompt_style"]),
        prefers_proven_tactics=template["traits"]["prefers_proven_tactics"],
        explores_new_paths=template["traits"]["explores_new_paths"],
        learns_from_peers=template["traits"]["learns_from_peers"],
        remembers_failures=template["traits"]["remembers_failures"]
    )
    
    if seed:
        random.seed()  # 重置随机种子
    
    return personality


def get_dynamic_temperature(personality: AgentPersonality, context: Dict = None) -> float:
    """
    根据性格和上下文动态计算temperature
    
    Args:
        personality: Agent性格
        context: 上下文信息（成功率、迭代次数等）
    """
    base_temp = personality.temperature_base
    variance = personality.temperature_variance
    
    # 基础随机波动
    temp = base_temp + random.uniform(-variance, variance)
    
    if context:
        # 根据成功率调整
        success_rate = context.get("success_rate", 0.5)
        if success_rate < 0.3 and personality.stubbornness < 0.5:
            # 成功率低且不固执 -> 提高创造力（提高temp）
            temp += 0.2
        elif success_rate > 0.7 and personality.prefers_proven_tactics:
            # 成功率高且偏好已验证策略 -> 降低随机性
            temp -= 0.1
        
        # 根据迭代次数调整
        iteration = context.get("iteration", 0)
        if iteration > 3:
            if personality.patience > 0.7:
                # 耐心型：多次失败后更加谨慎
                temp -= 0.1
            elif personality.risk_tolerance > 0.7:
                # 激进型：多次失败后更加激进
                temp += 0.2
    
    # 限制范围
    return max(0.1, min(1.5, temp))


def describe_personality(personality: AgentPersonality) -> str:
    """生成性格描述文本（用于prompt）"""
    descriptions = {
        PersonalityArchetype.AGGRESSIVE: "你是个激进的冒险家，喜欢冒险和突破边界，不怕失败。",
        PersonalityArchetype.CONSERVATIVE: "你是个谨慎的战术家，偏好已验证的方法，稳扎稳打。",
        PersonalityArchetype.ADAPTIVE: "你是个灵活的适应者，善于根据环境调整策略。",
        PersonalityArchetype.SOCIAL: "你是个善于观察的学习者，喜欢借鉴他人的成功经验。",
        PersonalityArchetype.CREATIVE: "你是个创新者，追求独特的表达方式，不走寻常路。",
        PersonalityArchetype.ANALYTICAL: "你是个冷静的分析师，用逻辑和数据指导决策。",
        PersonalityArchetype.CHAOTIC: "你是个不可预测的混乱者，凭直觉行事，充满随机性。",
        PersonalityArchetype.PATIENT: "你是个持久战大师，有耐心反复尝试，不轻易放弃。"
    }
    
    base_desc = descriptions[personality.archetype]
    
    # 添加具体特质
    traits = []
    if personality.creativity > 0.7:
        traits.append("极富创造力")
    if personality.analytical_depth > 0.7:
        traits.append("逻辑严密")
    if personality.social_learning > 0.7:
        traits.append("善于学习")
    if personality.risk_tolerance > 0.7:
        traits.append("敢于冒险")
    elif personality.risk_tolerance < 0.4:
        traits.append("风险厌恶")
    
    if traits:
        return f"{base_desc}你的特点：{', '.join(traits)}。"
    return base_desc
