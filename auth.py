# -*- coding: utf-8 -*-
"""
JWT认证模块
v2.1.0 - API安全保护
"""

import os
import jwt
import time
from functools import wraps
from flask import request, jsonify
from typing import Optional, Dict, Any


# JWT配置(从环境变量读取)
JWT_SECRET = os.environ.get("JWT_SECRET", "digital-twin-risk-secret-key-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = 3600 * 24  # 24小时


def generate_token(user_id: str, role: str = "user") -> str:
    """
    生成JWT token
    
    Args:
        user_id: 用户ID
        role: 用户角色
    
    Returns:
        JWT token字符串
    """
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": int(time.time()) + JWT_EXPIRATION,
        "iat": int(time.time())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证JWT token
    
    Args:
        token: JWT token字符串
    
    Returns:
        解码后的payload,失败返回None
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token过期
    except jwt.InvalidTokenError:
        return None  # Token无效


def require_auth(f):
    """
    装饰器:要求API调用提供有效token
    
    使用方法:
        @app.route("/api/protected")
        @require_auth
        def protected_route():
            return {"data": "secret"}
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从Header获取token
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "success": False,
                "error": "Missing or invalid Authorization header",
                "code": "AUTH_REQUIRED"
            }), 401
        
        token = auth_header[7:]  # 移除"Bearer "前缀
        payload = verify_token(token)
        
        if not payload:
            return jsonify({
                "success": False,
                "error": "Invalid or expired token",
                "code": "TOKEN_INVALID"
            }), 401
        
        # 将用户信息注入到request对象
        request.user_id = payload.get("user_id")
        request.user_role = payload.get("role")
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_role(role: str):
    """
    装饰器:要求特定角色
    
    使用方法:
        @app.route("/api/admin")
        @require_auth
        @require_role("admin")
        def admin_route():
            return {"data": "admin only"}
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = getattr(request, "user_role", None)
            
            if user_role != role:
                return jsonify({
                    "success": False,
                    "error": f"Requires {role} role",
                    "code": "INSUFFICIENT_PERMISSION"
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


# 默认测试用户(生产环境应该从数据库读取)
DEFAULT_USERS = {
    "demo": {"password": "demo123", "role": "user"},
    "admin": {"password": "admin123", "role": "admin"}
}


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    验证用户凭据
    
    Args:
        username: 用户名
        password: 密码
    
    Returns:
        用户信息字典,失败返回None
    """
    user = DEFAULT_USERS.get(username)
    
    if user and user["password"] == password:
        return {
            "user_id": username,
            "role": user["role"]
        }
    
    return None
