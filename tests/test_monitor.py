# -*- coding: utf-8 -*-
"""
监控系统测试
"""

import unittest
import time

from monitor import Monitor, Alert


class TestAlert(unittest.TestCase):
    """告警对象测试"""
    
    def test_create_alert(self):
        """测试创建告警"""
        alert = Alert(
            level="warning",
            title="测试告警",
            message="这是一条测试告警",
            metric_name="test_metric",
            metric_value=0.8,
            threshold=0.5
        )
        
        self.assertEqual(alert.level, "warning")
        self.assertEqual(alert.title, "测试告警")
        self.assertIsNotNone(alert.id)
        self.assertIsNotNone(alert.timestamp)
    
    def test_alert_to_dict(self):
        """测试告警转字典"""
        alert = Alert(
            level="error",
            title="错误",
            message="错误信息"
        )
        
        data = alert.to_dict()
        
        self.assertEqual(data['level'], "error")
        self.assertEqual(data['title'], "错误")
        self.assertIn('id', data)
        self.assertIn('timestamp', data)


class TestMonitor(unittest.TestCase):
    """监控系统测试"""
    
    def setUp(self):
        """测试前准备"""
        self.monitor = Monitor()
    
    def test_record_metric(self):
        """测试记录指标"""
        self.monitor.record_metric("test_metric", 0.5)
        
        # 验证指标被记录
        metrics = self.monitor.get_metrics("test_metric", duration=60)
        self.assertGreater(len(metrics), 0)
        
        # 验证最新值
        latest = self.monitor.get_latest_metric("test_metric")
        self.assertEqual(latest, 0.5)
    
    def test_alert_trigger(self):
        """测试告警触发"""
        # 添加告警规则
        self.monitor.add_alert_rule(
            name="high_value",
            metric="test_metric",
            threshold=0.7,
            operator=">",
            level="warning",
            message="值过高"
        )
        
        # 记录超过阈值的指标
        self.monitor.record_metric("test_metric", 0.9)
        
        # 验证告警被触发
        alerts = self.monitor.get_alerts()
        self.assertGreater(len(alerts), 0)
        
        # 验证告警内容
        alert = alerts[0]
        self.assertEqual(alert['level'], "warning")
        self.assertEqual(alert['metric_value'], 0.9)
    
    def test_get_metrics_with_duration(self):
        """测试获取时间窗口内的指标"""
        # 记录多个指标
        for i in range(5):
            self.monitor.record_metric("test_metric", float(i))
            time.sleep(0.1)
        
        # 获取最近60秒的指标
        metrics = self.monitor.get_metrics("test_metric", duration=60)
        self.assertEqual(len(metrics), 5)
    
    def test_get_stats(self):
        """测试获取统计信息"""
        self.monitor.record_metric("metric1", 1.0)
        self.monitor.record_metric("metric2", 2.0)
        
        stats = self.monitor.get_stats()
        
        self.assertEqual(stats['metrics_count'], 2)
        self.assertIn('metric1', stats['metrics'])
        self.assertIn('metric2', stats['metrics'])
    
    def test_alert_callback(self):
        """测试告警回调"""
        callback_called = []
        
        def test_callback(alert):
            callback_called.append(alert)
        
        self.monitor.register_alert_callback(test_callback)
        
        # 添加规则并触发
        self.monitor.add_alert_rule(
            name="test",
            metric="test_metric",
            threshold=0.5,
            operator=">",
            level="info"
        )
        
        self.monitor.record_metric("test_metric", 0.8)
        
        # 验证回调被调用
        self.assertGreater(len(callback_called), 0)


if __name__ == '__main__':
    unittest.main()
