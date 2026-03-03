# -*- coding: utf-8 -*-
"""
数据库模块测试
"""

import unittest
import os
import tempfile
from datetime import datetime

from database import Database
from models import BattleRecord, AgentMemory, AuditRule


class TestDatabase(unittest.TestCase):
    """数据库测试"""
    
    def setUp(self):
        """测试前准备"""
        # 使用临时数据库
        self.db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_file.close()
        
        self.db = Database(f"sqlite:///{self.db_file.name}")
        self.db.initialize()
        self.db.create_tables()
    
    def tearDown(self):
        """测试后清理"""
        try:
            os.unlink(self.db_file.name)
        except:
            pass
    
    def test_health_check(self):
        """测试健康检查"""
        health = self.db.health_check()
        self.assertTrue(health['healthy'])
        self.assertEqual(health['status'], 'connected')
    
    def test_save_battle_record(self):
        """测试保存攻击记录"""
        with self.db.get_session() as session:
            record = BattleRecord(
                session_id="test_session",
                agent_id="A001",
                agent_name="Test Agent",
                topic="测试话题",
                technique="测试技巧",
                content="测试内容",
                bypass_success=True,
                created_at=datetime.now()
            )
            session.add(record)
            session.flush()
            
            # 验证保存成功
            self.assertIsNotNone(record.id)
            
            # 查询验证
            found = session.query(BattleRecord).filter_by(agent_id="A001").first()
            self.assertIsNotNone(found)
            self.assertEqual(found.agent_name, "Test Agent")
    
    def test_agent_memory(self):
        """测试Agent记忆"""
        with self.db.get_session() as session:
            memory = AgentMemory(
                agent_id="A001",
                memory_type="short_term",
                content="测试记忆",
                created_at=datetime.now()
            )
            session.add(memory)
            session.flush()
            
            # 验证保存成功
            self.assertIsNotNone(memory.id)
            
            # 查询验证
            found = session.query(AgentMemory).filter_by(agent_id="A001").first()
            self.assertIsNotNone(found)
            self.assertEqual(found.content, "测试记忆")
    
    def test_audit_rules(self):
        """测试审核规则"""
        with self.db.get_session() as session:
            rule = AuditRule(
                rule_id="R001",
                rule_name="测试规则",
                rule_text="测试规则内容",
                keywords=["关键词1", "关键词2"],
                enabled=True,
                created_at=datetime.now()
            )
            session.add(rule)
            session.flush()
            
            # 验证保存成功
            self.assertIsNotNone(rule.id)
            
            # 查询验证
            found = session.query(AuditRule).filter_by(rule_id="R001").first()
            self.assertIsNotNone(found)
            self.assertEqual(found.rule_name, "测试规则")
            self.assertEqual(len(found.keywords), 2)


if __name__ == '__main__':
    unittest.main()
