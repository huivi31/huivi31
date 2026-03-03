"""
自进化系统Web服务 - 独立版本
只提供进化系统Dashboard，不依赖主系统
"""

from flask import Flask, render_template, jsonify
import json
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def index():
    """首页重定向到Dashboard"""
    return render_template("evolution_dashboard.html")

@app.route("/api/evolution/status")
def get_evolution_status():
    """获取进化系统状态"""
    # 查找最新的进化日志
    output_dir = Path("/tmp/evolution_demo")
    if not output_dir.exists():
        # 返回演示数据
        return jsonify({
            "status": "demo",
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "today_intelligence": 13,
                "total_techniques": 9,
                "high_value_count": 6,
                "avg_score": 0.60
            },
            "sources": {
                "arxiv": 5,
                "github": 3,
                "cve": 5,
                "news": 0
            },
            "techniques": [
                {
                    "name": "代理/隧道技术",
                    "value_score": 0.80,
                    "category": "技术绕过",
                    "detection_difficulty": 7,
                    "description": "利用代理和隧道技术进行红队行动，隐藏真实IP地址，绕过防火墙规则，建立隐蔽通信信道"
                },
                {
                    "name": "供应链攻击 (Vendor Lock-in)",
                    "value_score": 0.72,
                    "category": "技术绕过",
                    "detection_difficulty": 7,
                    "description": "利用厂商锁定策略，诱导用户使用过时系统，从而实施针对性攻击，突破边界防护"
                },
                {
                    "name": "游戏作弊API滥用",
                    "value_score": 0.70,
                    "category": "技术绕过",
                    "detection_difficulty": 7,
                    "description": "自动化游戏作弊机器人，利用API接口进行farming和clicker活动，绕过安全机制"
                },
                {
                    "name": "Java反序列化漏洞",
                    "value_score": 0.70,
                    "category": "技术绕过",
                    "detection_difficulty": 8,
                    "description": "Apache Commons Collections库不安全反序列化机制，触发任意代码执行"
                },
                {
                    "name": "Source Inference Attack (SIA)",
                    "value_score": 0.66,
                    "category": "其他",
                    "detection_difficulty": 7,
                    "description": "针对联邦学习的隐私攻击，通过梯度信息推断客户端数据所有权"
                },
                {
                    "name": "Reflected XSS (CVE-2018-12234)",
                    "value_score": 0.60,
                    "category": "技术绕过",
                    "detection_difficulty": 6,
                    "description": "HRMS软件参数存在反射型XSS漏洞，可窃取用户会话信息和cookie"
                }
            ]
        })
    
    # 读取真实数据
    log_files = list(output_dir.glob("evolution_log_*.json"))
    if not log_files:
        return jsonify({"status": "no_data", "message": "没有找到进化日志"})
    
    latest_log = sorted(log_files)[-1]
    with open(latest_log, 'r', encoding='utf-8') as f:
        log_data = json.load(f)
    
    # 读取技术列表
    tech_files = list(output_dir.glob("techniques_*.json"))
    techniques = []
    if tech_files:
        latest_tech = sorted(tech_files)[-1]
        with open(latest_tech, 'r', encoding='utf-8') as f:
            techniques = json.load(f)
    
    return jsonify({
        "status": "success",
        "timestamp": log_data["timestamp"],
        "stats": {
            "today_intelligence": log_data["stages"]["intelligence_collection"]["total_collected"],
            "total_techniques": log_data["stages"]["knowledge_extraction"]["extracted_count"],
            "high_value_count": log_data["stages"]["filtering"]["high_value_count"],
            "avg_score": log_data["stages"]["value_assessment"]["avg_score"]
        },
        "sources": log_data["stages"]["intelligence_collection"]["by_source"],
        "techniques": techniques[:10]
    })


if __name__ == "__main__":
    print("🚀 自进化系统Web服务启动中...")
    print("=" * 60)
    print("📱 访问地址: http://localhost:5000")
    print("🎨 Dashboard: http://localhost:5000/")
    print("📊 API接口: http://localhost:5000/api/evolution/status")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False)
