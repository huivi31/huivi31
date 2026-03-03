# -*- coding: utf-8 -*-
"""
数据库集成适配器
v2.3.0 - 将现有系统与数据库无缝集成
"""

from datetime import datetime
from typing import List, Dict, Optional
import logging
import uuid

from database import db
from models import BattleRecord, AgentMemory, AuditRule, SystemMetrics
from enhanced_agent_memory import EnhancedAgentMemory

logger = logging.getLogger(__name__)


class DatabaseIntegration:
    """
    数据库集成类
    提供简化的接口供agents.py和web_app.py使用
    """
    
    def __init__(self):
        self.db = db
        self._session_id = None
    
    def generate_session_id(self) -> str:
        """生成新的会话ID"""
        self._session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        return self._session_id
    
    def get_current_session_id(self) -> str:
        """获取当前会话ID"""
        if not self._session_id:
            self.generate_session_id()
        return self._session_id
    
    # ========== 攻击记录管理 ==========
    
    def save_battle_record(
        self,
        agent_id: str,
        agent_name: str,
        topic: str,
        technique: str,
        content: str,
        bypass_success: bool,
        blocked_at: Optional[str] = None,
        confidence: float = 0.0,
        complexity: float = 1.0,
        agent_archetype: Optional[str] = None,
        evolution_level: int = 1,
        generation_time: float = 0.0,
        processing_time: float = 0.0,
        matched_keywords: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[int]:
        """
        保存攻击记录到数据库
        
        Returns:
            记录ID，失败返回None
        """
        try:
            with self.db.get_session() as session:
                record = BattleRecord(
                    session_id=self.get_current_session_id(),
                    agent_id=agent_id,
                    agent_name=agent_name,
                    agent_archetype=agent_archetype,
                    agent_evolution_level=evolution_level,
                    topic=topic,
                    technique=technique,
                    content=content,
                    complexity=complexity,
                    bypass_success=bypass_success,
                    blocked_at=blocked_at,
                    confidence=confidence,
                    matched_keywords=matched_keywords,
                    generation_time=generation_time,
                    processing_time=processing_time,
                    metadata=metadata,
                    created_at=datetime.now()
                )
                session.add(record)
                session.flush()
                record_id = record.id
                
                logger.debug(f"Saved battle record #{record_id} for {agent_id}")
                return record_id
        except Exception as e:
            logger.error(f"Failed to save battle record: {e}")
            return None
    
    def get_battle_history(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        获取攻击历史记录
        
        Args:
            limit: 返回数量
            offset: 偏移量
        
        Returns:
            记录列表
        """
        try:
            with self.db.get_session() as session:
                records = session.query(BattleRecord)\
                    .order_by(BattleRecord.created_at.desc())\
                    .offset(offset)\
                    .limit(limit)\
                    .all()
                
                return [r.to_dict() for r in records]
        except Exception as e:
            logger.error(f"Failed to get battle history: {e}")
            return []
    
    def get_battle_stats(self, hours: int = 24) -> Dict:
        """
        获取攻击统计数据
        
        Args:
            hours: 统计最近N小时的数据
        
        Returns:
            统计字典
        """
        try:
            from datetime import timedelta
            
            with self.db.get_session() as session:
                cutoff = datetime.now() - timedelta(hours=hours)
                
                records = session.query(BattleRecord)\
                    .filter(BattleRecord.created_at >= cutoff)\
                    .all()
                
                total = len(records)
                bypassed = sum(1 for r in records if r.bypass_success)
                
                # 按技巧统计
                technique_stats = {}
                for r in records:
                    tech = r.technique or "未知"
                    if tech not in technique_stats:
                        technique_stats[tech] = {"total": 0, "bypassed": 0}
                    technique_stats[tech]["total"] += 1
                    if r.bypass_success:
                        technique_stats[tech]["bypassed"] += 1
                
                # 按拦截层统计
                layer_stats = {}
                for r in records:
                    if r.bypass_success:
                        layer = "bypassed"
                    else:
                        layer = r.blocked_at or "unknown"
                    layer_stats[layer] = layer_stats.get(layer, 0) + 1
                
                return {
                    "total": total,
                    "bypassed": bypassed,
                    "detected": total - bypassed,
                    "bypass_rate": bypassed / total if total > 0 else 0,
                    "by_technique": technique_stats,
                    "by_layer": layer_stats
                }
        except Exception as e:
            logger.error(f"Failed to get battle stats: {e}")
            return {}
    
    # ========== Agent记忆管理 ==========
    
    def get_agent_memory(self, agent_id: str) -> EnhancedAgentMemory:
        """
        获取Agent的增强记忆系统
        
        Args:
            agent_id: Agent ID
        
        Returns:
            EnhancedAgentMemory实例
        """
        return EnhancedAgentMemory(agent_id)
    
    def save_agent_short_memory(self, agent_id: str, content: str, technique: Optional[str] = None):
        """保存短期记忆"""
        memory = self.get_agent_memory(agent_id)
        memory.add_short_term(content, technique=technique)
    
    def save_agent_long_memory(self, agent_id: str, content: str, success: bool, technique: Optional[str] = None):
        """保存长期记忆"""
        memory = self.get_agent_memory(agent_id)
        memory.add_long_term(content, success=success, technique=technique)
    
    def save_agent_failure(self, agent_id: str, content: str, blocked_at: str, reason: str):
        """保存失败模式"""
        memory = self.get_agent_memory(agent_id)
        memory.add_failure_pattern(content, blocked_at, reason)
    
    def get_agent_successful_patterns(self, agent_id: str, limit: int = 5) -> List[Dict]:
        """获取成功模式"""
        memory = self.get_agent_memory(agent_id)
        return memory.get_successful_patterns(limit)
    
    # ========== 审核规则管理 ==========
    
    def save_audit_rules(self, rules: List[Dict]) -> bool:
        """
        保存审核规则到数据库
        
        Args:
            rules: 规则列表
        
        Returns:
            是否成功
        """
        try:
            with self.db.get_session() as session:
                for rule in rules:
                    rule_id = rule.get("id")
                    if not rule_id:
                        continue
                    
                    # 查找是否已存在
                    existing = session.query(AuditRule)\
                        .filter(AuditRule.rule_id == rule_id)\
                        .first()
                    
                    if existing:
                        # 更新现有规则
                        existing.rule_text = rule.get("rule", "")
                        existing.keywords = rule.get("keywords", [])
                        existing.severity = rule.get("severity", "medium")
                        existing.enabled = rule.get("enabled", True)
                        existing.version += 1
                        existing.updated_at = datetime.now()
                    else:
                        # 创建新规则
                        new_rule = AuditRule(
                            rule_id=rule_id,
                            rule_name=rule.get("name", f"规则{rule_id}"),
                            rule_text=rule.get("rule", ""),
                            keywords=rule.get("keywords", []),
                            severity=rule.get("severity", "medium"),
                            enabled=rule.get("enabled", True),
                            created_at=datetime.now()
                        )
                        session.add(new_rule)
                
                logger.info(f"Saved {len(rules)} audit rules to database")
                return True
        except Exception as e:
            logger.error(f"Failed to save audit rules: {e}")
            return False
    
    def get_audit_rules(self, enabled_only: bool = True) -> List[Dict]:
        """
        从数据库获取审核规则
        
        Args:
            enabled_only: 是否只返回启用的规则
        
        Returns:
            规则列表
        """
        try:
            with self.db.get_session() as session:
                query = session.query(AuditRule)
                
                if enabled_only:
                    query = query.filter(AuditRule.enabled == True)
                
                rules = query.order_by(AuditRule.created_at).all()
                
                return [
                    {
                        "id": r.rule_id,
                        "name": r.rule_name,
                        "rule": r.rule_text,
                        "keywords": r.keywords or [],
                        "severity": r.severity,
                        "enabled": r.enabled
                    }
                    for r in rules
                ]
        except Exception as e:
            logger.error(f"Failed to get audit rules: {e}")
            return []
    
    # ========== 系统指标管理 ==========
    
    def save_metric(self, metric_name: str, metric_value: float, unit: Optional[str] = None, data: Optional[Dict] = None):
        """
        保存系统指标
        
        Args:
            metric_name: 指标名称
            metric_value: 指标值
            unit: 单位
            data: 附加数据
        """
        try:
            with self.db.get_session() as session:
                metric = SystemMetrics(
                    metric_name=metric_name,
                    metric_value=metric_value,
                    metric_unit=unit,
                    metric_data=data,
                    recorded_at=datetime.now()
                )
                session.add(metric)
                
                logger.debug(f"Saved metric: {metric_name}={metric_value}")
        except Exception as e:
            logger.error(f"Failed to save metric: {e}")
    
    def get_metrics(self, metric_name: str, hours: int = 24) -> List[Dict]:
        """
        获取指标历史
        
        Args:
            metric_name: 指标名称
            hours: 获取最近N小时的数据
        
        Returns:
            指标列表
        """
        try:
            from datetime import timedelta
            
            with self.db.get_session() as session:
                cutoff = datetime.now() - timedelta(hours=hours)
                
                metrics = session.query(SystemMetrics)\
                    .filter(SystemMetrics.metric_name == metric_name)\
                    .filter(SystemMetrics.recorded_at >= cutoff)\
                    .order_by(SystemMetrics.recorded_at)\
                    .all()
                
                return [m.to_dict() for m in metrics]
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return []
    
    # ========== 数据迁移 ==========
    
    def migrate_battle_history(self, history_list: List[Dict]) -> int:
        """
        迁移现有的battle_history到数据库
        
        Args:
            history_list: 历史记录列表
        
        Returns:
            迁移的记录数
        """
        count = 0
        try:
            for record in history_list:
                result = self.save_battle_record(
                    agent_id=record.get("persona_id", "unknown"),
                    agent_name=record.get("persona_name", "Unknown"),
                    topic=record.get("topic", ""),
                    technique=record.get("technique", ""),
                    content=record.get("content", ""),
                    bypass_success=record.get("result", {}).get("bypass_success", False),
                    blocked_at=record.get("result", {}).get("blocked_at"),
                    confidence=record.get("result", {}).get("confidence", 0),
                    complexity=record.get("complexity", 1.0)
                )
                if result:
                    count += 1
            
            logger.info(f"Migrated {count} battle records to database")
        except Exception as e:
            logger.error(f"Failed to migrate battle history: {e}")
        
        return count


# 全局实例
db_integration = DatabaseIntegration()


# 便捷函数
def get_db_integration() -> DatabaseIntegration:
    """获取数据库集成实例"""
    return db_integration
