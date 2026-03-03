# -*- coding: utf-8 -*-
"""
数据模型定义
v2.3.0 - 完整的数据库模型支持
"""

from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import json

Base = declarative_base()


class BattleRecord(Base):
    """
    攻击记录表
    存储每次Agent攻击的完整信息
    """
    __tablename__ = 'battle_records'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 会话信息
    session_id = Column(String(64), index=True, nullable=False, comment='会话ID')
    battle_round = Column(Integer, default=0, comment='对抗轮次')
    
    # Agent信息
    agent_id = Column(String(64), index=True, nullable=False, comment='Agent ID')
    agent_name = Column(String(128), comment='Agent名称')
    agent_archetype = Column(String(32), index=True, comment='性格类型')
    agent_evolution_level = Column(Integer, default=1, comment='进化等级')
    
    # 攻击信息
    topic = Column(Text, comment='攻击主题')
    technique = Column(String(128), index=True, comment='使用的攻击技巧')
    content = Column(Text, nullable=False, comment='生成的攻击内容')
    complexity = Column(Float, default=1.0, comment='内容复杂度')
    
    # 审核结果
    bypass_success = Column(Boolean, index=True, nullable=False, comment='是否绕过')
    blocked_at = Column(String(32), index=True, comment='拦截层级 (L0/L1/L2/L3/L4/L5)')
    confidence = Column(Float, comment='检测置信度')
    matched_keywords = Column(JSON, comment='匹配的关键词')
    
    # 性能指标
    generation_time = Column(Float, comment='生成耗时(秒)')
    processing_time = Column(Float, comment='审核耗时(秒)')
    
    # 元数据
    metadata = Column(JSON, comment='其他元数据')
    created_at = Column(DateTime, index=True, nullable=False, default=datetime.now, comment='创建时间')
    
    # 索引优化
    __table_args__ = (
        Index('idx_session_agent', 'session_id', 'agent_id'),
        Index('idx_created_technique', 'created_at', 'technique'),
        Index('idx_bypass_blocked', 'bypass_success', 'blocked_at'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'agent_id': self.agent_id,
            'agent_name': self.agent_name,
            'topic': self.topic,
            'technique': self.technique,
            'content': self.content,
            'complexity': self.complexity,
            'bypass_success': self.bypass_success,
            'blocked_at': self.blocked_at,
            'confidence': self.confidence,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AgentMemory(Base):
    """
    Agent记忆表
    支持短期/长期/失败模式三种记忆类型
    """
    __tablename__ = 'agent_memories'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Agent信息
    agent_id = Column(String(64), index=True, nullable=False, comment='Agent ID')
    memory_type = Column(String(32), index=True, nullable=False, comment='记忆类型: short/long/failure')
    
    # 记忆内容
    content = Column(Text, nullable=False, comment='记忆内容')
    context = Column(JSON, comment='上下文信息')
    technique = Column(String(128), index=True, comment='相关技巧')
    
    # 统计信息
    success_count = Column(Integer, default=0, comment='成功次数')
    failure_count = Column(Integer, default=0, comment='失败次数')
    use_count = Column(Integer, default=0, comment='使用次数')
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    last_accessed = Column(DateTime, comment='最后访问时间')
    expires_at = Column(DateTime, index=True, comment='过期时间')
    
    # 索引
    __table_args__ = (
        Index('idx_agent_type', 'agent_id', 'memory_type'),
        Index('idx_agent_expires', 'agent_id', 'expires_at'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'memory_type': self.memory_type,
            'content': self.content,
            'technique': self.technique,
            'success_count': self.success_count,
            'use_count': self.use_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AuditRule(Base):
    """
    审核规则表
    存储用户配置的审核规则
    """
    __tablename__ = 'audit_rules'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 规则标识
    rule_id = Column(String(64), unique=True, nullable=False, comment='规则ID')
    rule_name = Column(String(256), comment='规则名称')
    
    # 规则内容
    rule_text = Column(Text, nullable=False, comment='规则描述')
    keywords = Column(JSON, comment='关键词列表')
    severity = Column(String(32), index=True, comment='严重程度: low/medium/high/critical')
    category = Column(String(64), index=True, comment='规则分类')
    
    # 状态
    enabled = Column(Boolean, default=True, index=True, comment='是否启用')
    version = Column(Integer, default=1, comment='版本号')
    
    # 统计
    hit_count = Column(Integer, default=0, comment='命中次数')
    false_positive_count = Column(Integer, default=0, comment='误报次数')
    last_hit_at = Column(DateTime, comment='最后命中时间')
    
    # 时间
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, onupdate=datetime.now, comment='更新时间')
    created_by = Column(String(64), comment='创建者')
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'rule_text': self.rule_text,
            'keywords': self.keywords,
            'severity': self.severity,
            'enabled': self.enabled,
            'hit_count': self.hit_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class SystemMetrics(Base):
    """
    系统指标表
    记录系统运行指标和健康度数据
    """
    __tablename__ = 'system_metrics'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 指标信息
    metric_name = Column(String(128), index=True, nullable=False, comment='指标名称')
    metric_value = Column(Float, nullable=False, comment='指标值')
    metric_unit = Column(String(32), comment='单位')
    
    # 附加数据
    metric_data = Column(JSON, comment='详细数据')
    tags = Column(JSON, comment='标签')
    
    # 时间
    recorded_at = Column(DateTime, index=True, nullable=False, default=datetime.now, comment='记录时间')
    
    # 分区索引
    __table_args__ = (
        Index('idx_metric_time', 'metric_name', 'recorded_at'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'metric_unit': self.metric_unit,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }


class SystemAlert(Base):
    """
    系统告警表
    记录系统异常和告警信息
    """
    __tablename__ = 'system_alerts'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 告警信息
    alert_type = Column(String(64), index=True, nullable=False, comment='告警类型')
    alert_level = Column(String(32), index=True, nullable=False, comment='告警级别: info/warning/critical')
    alert_message = Column(Text, nullable=False, comment='告警消息')
    
    # 详细信息
    alert_data = Column(JSON, comment='详细数据')
    source = Column(String(128), comment='告警来源')
    
    # 状态
    status = Column(String(32), index=True, default='open', comment='状态: open/acknowledged/resolved')
    resolved_at = Column(DateTime, comment='解决时间')
    resolved_by = Column(String(64), comment='解决人')
    
    # 时间
    created_at = Column(DateTime, index=True, nullable=False, default=datetime.now, comment='创建时间')
    
    # 索引
    __table_args__ = (
        Index('idx_level_status', 'alert_level', 'status'),
        Index('idx_type_created', 'alert_type', 'created_at'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'alert_type': self.alert_type,
            'alert_level': self.alert_level,
            'alert_message': self.alert_message,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class CollaborativeSession(Base):
    """
    协作会话表
    记录多Agent协作攻击的会话信息
    """
    __tablename__ = 'collaborative_sessions'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 会话信息
    session_id = Column(String(64), unique=True, nullable=False, comment='会话ID')
    topic = Column(Text, comment='协作主题')
    agent_ids = Column(JSON, comment='参与的Agent ID列表')
    
    # 结果
    total_rounds = Column(Integer, default=0, comment='总轮次')
    success_count = Column(Integer, default=0, comment='成功绕过次数')
    final_result = Column(String(32), comment='最终结果: success/failure')
    
    # 时间
    started_at = Column(DateTime, nullable=False, default=datetime.now, comment='开始时间')
    ended_at = Column(DateTime, comment='结束时间')
    duration = Column(Float, comment='持续时间(秒)')
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'topic': self.topic,
            'total_rounds': self.total_rounds,
            'success_count': self.success_count,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None
        }


# 辅助函数
def model_to_dict(model_instance):
    """通用的模型转字典函数"""
    if hasattr(model_instance, 'to_dict'):
        return model_instance.to_dict()
    
    result = {}
    for column in model_instance.__table__.columns:
        value = getattr(model_instance, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[column.name] = value
    return result
