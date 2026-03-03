# -*- coding: utf-8 -*-
"""
增强的Agent记忆系统
v2.3.0 - 数据库持久化支持
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import logging

from database import db
from models import AgentMemory

logger = logging.getLogger(__name__)


class EnhancedAgentMemory:
    """
    增强的Agent记忆系统
    支持短期/长期/失败模式三种记忆,并持久化到数据库
    """
    
    def __init__(self, agent_id: str):
        """
        初始化Agent记忆系统
        
        Args:
            agent_id: Agent的唯一标识
        """
        self.agent_id = agent_id
        self.db = db
        
        # 内存缓存(用于快速访问)
        self._short_term_cache = []
        self._long_term_cache = []
        self._cache_loaded = False
    
    def _load_cache(self):
        """从数据库加载缓存"""
        if self._cache_loaded:
            return
        
        try:
            with self.db.get_session() as session:
                # 加载短期记忆
                short_memories = session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .filter(AgentMemory.memory_type == 'short')\
                    .filter(AgentMemory.expires_at > datetime.now())\
                    .order_by(AgentMemory.created_at.desc())\
                    .limit(10)\
                    .all()
                
                self._short_term_cache = [m.content for m in short_memories]
                
                # 加载长期记忆(成功模式)
                long_memories = session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .filter(AgentMemory.memory_type == 'long')\
                    .filter(AgentMemory.success_count > 0)\
                    .order_by(AgentMemory.success_count.desc())\
                    .limit(5)\
                    .all()
                
                self._long_term_cache = [m.content for m in long_memories]
                
                self._cache_loaded = True
        except Exception as e:
            logger.error(f"Failed to load memory cache for {self.agent_id}: {e}")
    
    # ========== 短期记忆 ==========
    
    def add_short_term(self, content: str, context: Optional[Dict] = None, technique: Optional[str] = None):
        """
        添加短期记忆
        短期记忆会在24小时后自动过期
        
        Args:
            content: 记忆内容
            context: 上下文信息
            technique: 相关技巧
        """
        try:
            with self.db.get_session() as session:
                memory = AgentMemory(
                    agent_id=self.agent_id,
                    memory_type='short',
                    content=content,
                    context=context,
                    technique=technique,
                    created_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(hours=24)
                )
                session.add(memory)
                session.flush()
                
                # 更新缓存
                if len(self._short_term_cache) >= 10:
                    self._short_term_cache.pop()
                self._short_term_cache.insert(0, content)
                
                # 清理过期记忆
                session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .filter(AgentMemory.memory_type == 'short')\
                    .filter(AgentMemory.expires_at < datetime.now())\
                    .delete()
                
                logger.debug(f"Added short-term memory for {self.agent_id}")
        except Exception as e:
            logger.error(f"Failed to add short-term memory: {e}")
    
    def get_short_term(self, limit: int = 10) -> List[str]:
        """
        获取短期记忆
        
        Args:
            limit: 返回数量限制
        
        Returns:
            记忆内容列表
        """
        self._load_cache()
        return self._short_term_cache[:limit]
    
    # ========== 长期记忆 ==========
    
    def add_long_term(self, content: str, success: bool, context: Optional[Dict] = None, technique: Optional[str] = None):
        """
        添加或更新长期记忆
        长期记忆会永久保存,并记录成功/失败次数
        
        Args:
            content: 记忆内容
            success: 是否成功
            context: 上下文信息
            technique: 相关技巧
        """
        try:
            with self.db.get_session() as session:
                # 查找是否已存在
                existing = session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .filter(AgentMemory.memory_type == 'long')\
                    .filter(AgentMemory.content == content)\
                    .first()
                
                if existing:
                    # 更新统计
                    if success:
                        existing.success_count += 1
                    else:
                        existing.failure_count += 1
                    existing.use_count += 1
                    existing.last_accessed = datetime.now()
                    
                    logger.debug(f"Updated long-term memory (success={success})")
                else:
                    # 创建新记忆
                    memory = AgentMemory(
                        agent_id=self.agent_id,
                        memory_type='long',
                        content=content,
                        context=context,
                        technique=technique,
                        success_count=1 if success else 0,
                        failure_count=0 if success else 1,
                        use_count=1,
                        created_at=datetime.now(),
                        last_accessed=datetime.now()
                    )
                    session.add(memory)
                    
                    logger.debug(f"Created new long-term memory")
                
                # 刷新缓存
                self._cache_loaded = False
        except Exception as e:
            logger.error(f"Failed to add long-term memory: {e}")
    
    def get_long_term(self, limit: int = 5) -> List[str]:
        """
        获取长期记忆
        
        Args:
            limit: 返回数量限制
        
        Returns:
            记忆内容列表
        """
        self._load_cache()
        return self._long_term_cache[:limit]
    
    def get_successful_patterns(self, limit: int = 5) -> List[Dict]:
        """
        获取成功的攻击模式
        返回成功率最高的记忆
        
        Args:
            limit: 返回数量限制
        
        Returns:
            记忆详情列表 [{'content': ..., 'success_rate': ..., 'use_count': ...}]
        """
        try:
            with self.db.get_session() as session:
                memories = session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .filter(AgentMemory.memory_type == 'long')\
                    .filter(AgentMemory.success_count > 0)\
                    .order_by(AgentMemory.success_count.desc())\
                    .limit(limit)\
                    .all()
                
                patterns = []
                for m in memories:
                    total = m.success_count + m.failure_count
                    success_rate = m.success_count / total if total > 0 else 0
                    patterns.append({
                        'content': m.content,
                        'technique': m.technique,
                        'success_rate': round(success_rate, 3),
                        'use_count': m.use_count,
                        'success_count': m.success_count
                    })
                
                return patterns
        except Exception as e:
            logger.error(f"Failed to get successful patterns: {e}")
            return []
    
    # ========== 失败模式记忆 ==========
    
    def add_failure_pattern(self, content: str, blocked_at: str, reason: str):
        """
        添加失败模式记忆
        记录被拦截的内容,避免重复失败
        
        Args:
            content: 失败的内容
            blocked_at: 拦截层级
            reason: 失败原因
        """
        try:
            with self.db.get_session() as session:
                context = {
                    'blocked_at': blocked_at,
                    'reason': reason
                }
                
                # 查找是否已存在
                existing = session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .filter(AgentMemory.memory_type == 'failure')\
                    .filter(AgentMemory.content == content)\
                    .first()
                
                if existing:
                    # 更新失败次数
                    existing.failure_count += 1
                    existing.use_count += 1
                    existing.last_accessed = datetime.now()
                else:
                    # 创建新失败记忆
                    memory = AgentMemory(
                        agent_id=self.agent_id,
                        memory_type='failure',
                        content=content,
                        context=context,
                        failure_count=1,
                        use_count=1,
                        created_at=datetime.now(),
                        last_accessed=datetime.now(),
                        expires_at=datetime.now() + timedelta(days=7)  # 7天后过期
                    )
                    session.add(memory)
                
                logger.debug(f"Added failure pattern: {blocked_at}")
        except Exception as e:
            logger.error(f"Failed to add failure pattern: {e}")
    
    def get_failure_patterns(self, limit: int = 5) -> List[Dict]:
        """
        获取失败模式
        
        Args:
            limit: 返回数量限制
        
        Returns:
            失败模式列表
        """
        try:
            with self.db.get_session() as session:
                memories = session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .filter(AgentMemory.memory_type == 'failure')\
                    .filter(AgentMemory.expires_at > datetime.now())\
                    .order_by(AgentMemory.failure_count.desc())\
                    .limit(limit)\
                    .all()
                
                patterns = []
                for m in memories:
                    patterns.append({
                        'content': m.content,
                        'failure_count': m.failure_count,
                        'blocked_at': m.context.get('blocked_at') if m.context else None,
                        'reason': m.context.get('reason') if m.context else None
                    })
                
                return patterns
        except Exception as e:
            logger.error(f"Failed to get failure patterns: {e}")
            return []
    
    # ========== 记忆管理 ==========
    
    def compress_memories(self):
        """
        压缩记忆
        删除低价值的记忆,保留重要的
        """
        try:
            with self.db.get_session() as session:
                cutoff_date = datetime.now() - timedelta(days=7)
                
                # 删除低价值长期记忆
                session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .filter(AgentMemory.memory_type == 'long')\
                    .filter(AgentMemory.use_count < 2)\
                    .filter(AgentMemory.success_count == 0)\
                    .filter(AgentMemory.created_at < cutoff_date)\
                    .delete()
                
                # 删除过期的短期记忆
                session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .filter(AgentMemory.memory_type == 'short')\
                    .filter(AgentMemory.expires_at < datetime.now())\
                    .delete()
                
                # 删除过期的失败记忆
                session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .filter(AgentMemory.memory_type == 'failure')\
                    .filter(AgentMemory.expires_at < datetime.now())\
                    .delete()
                
                logger.info(f"Compressed memories for {self.agent_id}")
                
                # 刷新缓存
                self._cache_loaded = False
        except Exception as e:
            logger.error(f"Failed to compress memories: {e}")
    
    def get_memory_stats(self) -> Dict:
        """
        获取记忆统计信息
        
        Returns:
            统计信息字典
        """
        try:
            with self.db.get_session() as session:
                stats = {
                    'short_term_count': session.query(AgentMemory)
                        .filter(AgentMemory.agent_id == self.agent_id)
                        .filter(AgentMemory.memory_type == 'short')
                        .filter(AgentMemory.expires_at > datetime.now())
                        .count(),
                    
                    'long_term_count': session.query(AgentMemory)
                        .filter(AgentMemory.agent_id == self.agent_id)
                        .filter(AgentMemory.memory_type == 'long')
                        .count(),
                    
                    'failure_pattern_count': session.query(AgentMemory)
                        .filter(AgentMemory.agent_id == self.agent_id)
                        .filter(AgentMemory.memory_type == 'failure')
                        .filter(AgentMemory.expires_at > datetime.now())
                        .count()
                }
                
                return stats
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {}
    
    def clear_all(self):
        """
        清空所有记忆 (危险操作!)
        """
        try:
            with self.db.get_session() as session:
                session.query(AgentMemory)\
                    .filter(AgentMemory.agent_id == self.agent_id)\
                    .delete()
                
                logger.warning(f"Cleared all memories for {self.agent_id}")
                
                # 清空缓存
                self._short_term_cache = []
                self._long_term_cache = []
                self._cache_loaded = False
        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")


# 兼容旧接口的适配器
class AgentMemoryAdapter:
    """
    兼容旧版agent_memory.py的适配器
    保持API向后兼容
    """
    
    def __init__(self):
        self.short_term = []
        self.long_term = {}
        self.failure_patterns = []
        self._enhanced = None
    
    def _get_enhanced(self, agent_id):
        """获取增强记忆实例"""
        if self._enhanced is None or self._enhanced.agent_id != agent_id:
            self._enhanced = EnhancedAgentMemory(agent_id)
        return self._enhanced
    
    def add_short(self, agent_id, content):
        """添加短期记忆"""
        enhanced = self._get_enhanced(agent_id)
        enhanced.add_short_term(content)
        # 同步到内存列表
        if len(self.short_term) >= 5:
            self.short_term.pop(0)
        self.short_term.append(content)
    
    def add_long(self, agent_id, technique, content):
        """添加长期记忆"""
        enhanced = self._get_enhanced(agent_id)
        enhanced.add_long_term(content, success=True, technique=technique)
        # 同步到内存字典
        if technique not in self.long_term:
            self.long_term[technique] = []
        if content not in self.long_term[technique]:
            self.long_term[technique].append(content)
    
    def add_failure(self, agent_id, content, blocked_at, reason):
        """添加失败记忆"""
        enhanced = self._get_enhanced(agent_id)
        enhanced.add_failure_pattern(content, blocked_at, reason)
