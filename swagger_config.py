# -*- coding: utf-8 -*-
"""
Swagger API文档配置
v2.3.0
"""

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "数字孪生风控风洞 API",
        "description": "多智能体攻防模拟系统 - v2.3.0",
        "version": "2.3.0",
        "contact": {
            "name": "Support",
            "email": "support@example.com"
        }
    },
    "basePath": "/",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Token, format: Bearer <token>"
        }
    }
}

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs"
}


API_DOCS = {
    "/api/battle/batch": {
        "post": {
            "tags": ["Battle"],
            "summary": "批量攻防测试",
            "description": "对多个Agent进行批量测试",
            "parameters": [
                {
                    "name": "body",
                    "in": "body",
                    "required": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "agent_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Agent ID列表"
                            },
                            "target_keyword": {
                                "type": "string",
                                "description": "目标话题（可选）"
                            }
                        },
                        "required": ["agent_ids"]
                    }
                }
            ],
            "responses": {
                "200": {
                    "description": "测试成功",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "total_tests": {"type": "integer"},
                            "results": {"type": "array"},
                            "bypass_summary": {"type": "object"}
                        }
                    }
                }
            }
        }
    },
    "/api/stats/summary": {
        "get": {
            "tags": ["Statistics"],
            "summary": "获取系统统计摘要",
            "description": "获取攻防测试的统计数据",
            "parameters": [
                {
                    "name": "limit",
                    "in": "query",
                    "type": "integer",
                    "default": 100,
                    "description": "分析最近N条记录"
                }
            ],
            "responses": {
                "200": {
                    "description": "统计数据",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "overall": {"type": "object"},
                            "by_technique": {"type": "object"},
                            "by_layer": {"type": "object"},
                            "top_agents": {"type": "array"}
                        }
                    }
                }
            }
        }
    },
    "/api/db/health": {
        "get": {
            "tags": ["Database"],
            "summary": "数据库健康检查",
            "description": "检查数据库连接状态",
            "responses": {
                "200": {
                    "description": "健康状态",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "status": {"type": "string"},
                            "info": {"type": "object"}
                        }
                    }
                }
            }
        }
    },
    "/api/db/battle/history": {
        "get": {
            "tags": ["Database"],
            "summary": "获取攻击历史记录",
            "description": "从数据库查询历史记录",
            "parameters": [
                {
                    "name": "limit",
                    "in": "query",
                    "type": "integer",
                    "default": 100
                },
                {
                    "name": "offset",
                    "in": "query",
                    "type": "integer",
                    "default": 0
                }
            ],
            "responses": {
                "200": {
                    "description": "历史记录列表"
                }
            }
        }
    },
    "/api/db/battle/stats": {
        "get": {
            "tags": ["Database"],
            "summary": "获取攻击统计",
            "description": "从数据库获取统计数据",
            "parameters": [
                {
                    "name": "hours",
                    "in": "query",
                    "type": "integer",
                    "default": 24,
                    "description": "统计最近N小时"
                }
            ],
            "responses": {
                "200": {
                    "description": "统计数据"
                }
            }
        }
    },
    "/api/monitor/alerts": {
        "get": {
            "tags": ["Monitor"],
            "summary": "获取监控告警",
            "description": "查询系统告警列表",
            "parameters": [
                {
                    "name": "level",
                    "in": "query",
                    "type": "string",
                    "enum": ["info", "warning", "error", "critical"]
                },
                {
                    "name": "limit",
                    "in": "query",
                    "type": "integer",
                    "default": 50
                }
            ],
            "responses": {
                "200": {
                    "description": "告警列表"
                }
            }
        }
    },
    "/api/monitor/stats": {
        "get": {
            "tags": ["Monitor"],
            "summary": "监控统计",
            "description": "获取监控系统统计信息",
            "responses": {
                "200": {
                    "description": "监控统计"
                }
            }
        }
    },
    "/api/agent/<agent_id>/memory": {
        "get": {
            "tags": ["Agent"],
            "summary": "获取Agent记忆",
            "description": "查询Agent的记忆系统",
            "parameters": [
                {
                    "name": "agent_id",
                    "in": "path",
                    "type": "string",
                    "required": True
                }
            ],
            "responses": {
                "200": {
                    "description": "记忆数据"
                }
            }
        }
    }
}
