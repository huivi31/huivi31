# -*- coding: utf-8 -*-
"""
中间件:限流、错误处理、日志
v2.1.0
"""

import time
import json
import logging
from functools import wraps
from flask import request, jsonify, g
from typing import Dict, Any
from collections import defaultdict, deque


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# 限流器
# ============================================================================

class RateLimiter:
    """简单的基于内存的限流器"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Args:
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口(秒)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
    
    def is_allowed(self, key: str) -> tuple[bool, Dict[str, Any]]:
        """
        检查是否允许请求
        
        Args:
            key: 限流key(通常是IP或用户ID)
        
        Returns:
            (是否允许, 元信息字典)
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # 清理过期记录
        while self.requests[key] and self.requests[key][0] < window_start:
            self.requests[key].popleft()
        
        current_count = len(self.requests[key])
        
        if current_count >= self.max_requests:
            return False, {
                "limit": self.max_requests,
                "remaining": 0,
                "reset": int(self.requests[key][0] + self.window_seconds)
            }
        
        # 记录本次请求
        self.requests[key].append(now)
        
        return True, {
            "limit": self.max_requests,
            "remaining": self.max_requests - current_count - 1,
            "reset": int(now + self.window_seconds)
        }


# 全局限流器实例
_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)


def rate_limit(max_requests: int = 100, window: int = 60):
    """
    限流装饰器
    
    Args:
        max_requests: 时间窗口内最大请求数
        window: 时间窗口(秒)
    
    使用方法:
        @app.route("/api/test")
        @rate_limit(max_requests=10, window=60)
        def test():
            return {"status": "ok"}
    """
    limiter = RateLimiter(max_requests, window)
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 使用IP作为限流key
            key = request.remote_addr or "unknown"
            
            allowed, info = limiter.is_allowed(key)
            
            # 添加限流信息到响应头
            g.rate_limit_info = info
            
            if not allowed:
                return jsonify({
                    "success": False,
                    "error": "Rate limit exceeded",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "rate_limit": info
                }), 429
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


# ============================================================================
# 错误处理
# ============================================================================

class APIError(Exception):
    """自定义API异常"""
    
    def __init__(self, message: str, code: str = "API_ERROR", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


def error_handler(app):
    """
    注册全局错误处理器
    
    使用方法:
        app = Flask(__name__)
        error_handler(app)
    """
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = {
            "success": False,
            "error": error.message,
            "code": error.code
        }
        return jsonify(response), error.status_code
    
    @app.errorhandler(404)
    def handle_404(error):
        return jsonify({
            "success": False,
            "error": "Endpoint not found",
            "code": "NOT_FOUND"
        }), 404
    
    @app.errorhandler(500)
    def handle_500(error):
        logger.error(f"Internal server error: {error}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "code": "INTERNAL_ERROR"
        }), 500


# ============================================================================
# 请求日志
# ============================================================================

def log_request():
    """
    记录请求日志
    
    使用方法:
        @app.before_request
        def before():
            log_request()
    """
    g.request_start_time = time.time()
    
    logger.info(f"→ {request.method} {request.path} from {request.remote_addr}")


def log_response(response):
    """
    记录响应日志
    
    使用方法:
        @app.after_request
        def after(response):
            return log_response(response)
    """
    duration = time.time() - getattr(g, 'request_start_time', time.time())
    
    logger.info(
        f"← {request.method} {request.path} "
        f"[{response.status_code}] {duration:.3f}s"
    )
    
    # 添加限流信息到响应头
    if hasattr(g, 'rate_limit_info'):
        info = g.rate_limit_info
        response.headers['X-RateLimit-Limit'] = str(info['limit'])
        response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
        response.headers['X-RateLimit-Reset'] = str(info['reset'])
    
    return response


# ============================================================================
# 结构化日志
# ============================================================================

def log_event(event_type: str, data: Dict[str, Any], level: str = "info"):
    """
    记录结构化事件日志
    
    Args:
        event_type: 事件类型
        data: 事件数据
        level: 日志级别(debug/info/warning/error)
    """
    log_data = {
        "timestamp": time.time(),
        "event_type": event_type,
        "data": data,
        "request_id": getattr(g, 'request_id', None)
    }
    
    log_func = getattr(logger, level, logger.info)
    log_func(json.dumps(log_data, ensure_ascii=False))
