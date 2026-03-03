# -*- coding: utf-8 -*-
"""
监控告警系统
v2.3.0 - 简单的监控和告警机制
"""

import time
import logging
from typing import Dict, List, Callable, Optional
from datetime import datetime
from collections import deque
import threading

logger = logging.getLogger(__name__)


class Alert:
    """告警对象"""
    def __init__(
        self,
        level: str,  # info / warning / error / critical
        title: str,
        message: str,
        metric_name: Optional[str] = None,
        metric_value: Optional[float] = None,
        threshold: Optional[float] = None
    ):
        self.level = level
        self.title = title
        self.message = message
        self.metric_name = metric_name
        self.metric_value = metric_value
        self.threshold = threshold
        self.timestamp = datetime.now()
        self.id = f"{self.level}_{int(time.time() * 1000)}"
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "level": self.level,
            "title": self.title,
            "message": self.message,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat()
        }


class Monitor:
    """
    监控系统
    跟踪关键指标并在超过阈值时触发告警
    """
    
    def __init__(self):
        self.metrics: Dict[str, deque] = {}  # metric_name -> deque of (timestamp, value)
        self.alerts: deque = deque(maxlen=100)  # 最近100条告警
        self.alert_rules: List[Dict] = []
        self.alert_callbacks: List[Callable] = []
        
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread = None
        
        # 默认规则
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认告警规则"""
        self.alert_rules = [
            {
                "name": "high_bypass_rate",
                "metric": "bypass_rate",
                "threshold": 0.5,  # 50%
                "operator": ">",
                "level": "warning",
                "message": "绕过率超过 50%，需要加强规则"
            },
            {
                "name": "very_high_bypass_rate",
                "metric": "bypass_rate",
                "threshold": 0.8,  # 80%
                "operator": ">",
                "level": "critical",
                "message": "绕过率超过 80%，规则失效严重！"
            },
            {
                "name": "low_detection_rate",
                "metric": "detection_rate",
                "threshold": 0.3,  # 30%
                "operator": "<",
                "level": "warning",
                "message": "检测率低于 30%，规则可能过于宽松"
            },
            {
                "name": "high_processing_time",
                "metric": "avg_processing_time",
                "threshold": 0.1,  # 100ms
                "operator": ">",
                "level": "warning",
                "message": "平均处理时间超过 100ms"
            },
        ]
    
    def record_metric(self, metric_name: str, value: float):
        """
        记录指标值
        
        Args:
            metric_name: 指标名称
            value: 指标值
        """
        with self._lock:
            if metric_name not in self.metrics:
                self.metrics[metric_name] = deque(maxlen=1000)  # 保留最近1000个点
            
            self.metrics[metric_name].append((time.time(), value))
            
            # 检查告警规则
            self._check_alerts(metric_name, value)
    
    def _check_alerts(self, metric_name: str, value: float):
        """检查是否触发告警"""
        for rule in self.alert_rules:
            if rule["metric"] != metric_name:
                continue
            
            threshold = rule["threshold"]
            operator = rule["operator"]
            
            triggered = False
            if operator == ">" and value > threshold:
                triggered = True
            elif operator == "<" and value < threshold:
                triggered = True
            elif operator == ">=" and value >= threshold:
                triggered = True
            elif operator == "<=" and value <= threshold:
                triggered = True
            elif operator == "==" and abs(value - threshold) < 1e-6:
                triggered = True
            
            if triggered:
                alert = Alert(
                    level=rule["level"],
                    title=rule["name"],
                    message=rule["message"],
                    metric_name=metric_name,
                    metric_value=value,
                    threshold=threshold
                )
                self._add_alert(alert)
    
    def _add_alert(self, alert: Alert):
        """添加告警"""
        with self._lock:
            self.alerts.append(alert)
            
            logger.warning(f"[ALERT] {alert.level.upper()}: {alert.title} - {alert.message}")
            
            # 调用回调函数
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")
    
    def get_metrics(self, metric_name: str, duration: int = 60) -> List[tuple]:
        """
        获取指标历史数据
        
        Args:
            metric_name: 指标名称
            duration: 时间窗口（秒）
        
        Returns:
            [(timestamp, value), ...]
        """
        with self._lock:
            if metric_name not in self.metrics:
                return []
            
            cutoff = time.time() - duration
            return [
                (ts, val) for ts, val in self.metrics[metric_name]
                if ts >= cutoff
            ]
    
    def get_latest_metric(self, metric_name: str) -> Optional[float]:
        """获取最新指标值"""
        with self._lock:
            if metric_name not in self.metrics or not self.metrics[metric_name]:
                return None
            return self.metrics[metric_name][-1][1]
    
    def get_alerts(self, level: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """
        获取告警列表
        
        Args:
            level: 告警级别过滤
            limit: 返回数量
        
        Returns:
            告警列表
        """
        with self._lock:
            alerts = list(self.alerts)
            
            if level:
                alerts = [a for a in alerts if a.level == level]
            
            # 最新的在前
            alerts.reverse()
            
            return [a.to_dict() for a in alerts[:limit]]
    
    def add_alert_rule(
        self,
        name: str,
        metric: str,
        threshold: float,
        operator: str = ">",
        level: str = "warning",
        message: str = ""
    ):
        """
        添加自定义告警规则
        
        Args:
            name: 规则名称
            metric: 指标名称
            threshold: 阈值
            operator: 比较运算符 (>, <, >=, <=, ==)
            level: 告警级别
            message: 告警消息
        """
        with self._lock:
            rule = {
                "name": name,
                "metric": metric,
                "threshold": threshold,
                "operator": operator,
                "level": level,
                "message": message or f"{metric} {operator} {threshold}"
            }
            self.alert_rules.append(rule)
    
    def register_alert_callback(self, callback: Callable):
        """注册告警回调函数"""
        self.alert_callbacks.append(callback)
    
    def get_stats(self) -> Dict:
        """获取监控统计"""
        with self._lock:
            return {
                "metrics_count": len(self.metrics),
                "alerts_count": len(self.alerts),
                "alert_rules_count": len(self.alert_rules),
                "metrics": list(self.metrics.keys())
            }
    
    def start_monitoring(self):
        """启动后台监控"""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Monitor started")
    
    def stop_monitoring(self):
        """停止监控"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Monitor stopped")
    
    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                # 每10秒检查一次
                time.sleep(10)
                
                # 可以在这里添加周期性检查逻辑
                # 例如：检查数据库连接、内存使用等
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")


# 全局实例
monitor = Monitor()


def get_monitor() -> Monitor:
    """获取监控实例"""
    return monitor


# 便捷函数
def record_metric(metric_name: str, value: float):
    """记录指标"""
    monitor.record_metric(metric_name, value)


def get_alerts(level: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """获取告警"""
    return monitor.get_alerts(level=level, limit=limit)


def add_alert_rule(**kwargs):
    """添加告警规则"""
    monitor.add_alert_rule(**kwargs)
