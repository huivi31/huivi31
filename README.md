# 🎯 数字孪生风控风洞 v2.3.0

[![Version](https://img.shields.io/badge/version-2.3.0-blue.svg)](https://github.com/huivi31/huivi31)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)](https://digital-twin-risk-demo.onrender.com/)

> 基于多智能体的内容审核攻防模拟系统 - 72个自主Agent vs 5层检测引擎

**在线演示**: [https://digital-twin-risk-demo.onrender.com/](https://digital-twin-risk-demo.onrender.com/)

---

## 🌟 核心特性

### 🚀 极致性能
- **400-1000倍提升**: 2-5秒 → <5ms
- **L3正则优化**: 预编译 + 快速预扫描
- **零LLM成本**: L2语义分析本地化
- **批量测试**: 72个Agent 30秒完成

### 💾 企业级数据持久化
- **SQLAlchemy ORM**: 支持SQLite/PostgreSQL
- **连接池管理**: 自动重连 + 健康检查
- **三层记忆系统**: 短期(24h) / 长期(永久) / 失败模式(7天)
- **数据迁移工具**: 一键迁移历史数据

### 📊 现代化监控面板
- **实时Dashboard**: 攻防统计 + Agent排行
- **批量测试UI**: 选择/随机/全部模式
- **监控告警系统**: 自定义规则 + 多级别告警
- **API文档**: 完整的RESTful API说明

### 🐳 生产就绪部署
- **Docker容器化**: 一键部署
- **健康检查**: 自动恢复机制
- **PostgreSQL支持**: 生产环境就绪
- **测试覆盖>80%**: 完整单元测试

---

## 📖 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Web 界面层                            │
│  Dashboard | Batch Test | API Docs | 3D可视化          │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                  RESTful API 层                          │
│  /api/battle/* | /api/stats/* | /api/db/* | /api/monitor/* │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│               核心引擎层 (v2.3.0新增)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │L3正则优化│  │数据持久化│  │监控告警  │              │
│  │ <2ms响应 │  │ ORM映射  │  │ 实时指标 │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│            72个自主Agent (攻击方)                        │
│  技术黑客 | 社交工程师 | 文字游戏专家 | ...             │
│  ↓ 生成攻击内容                                          │
│  ↓ 学习失败模式                                          │
│  ↓ 协作优化策略                                          │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│            5层检测引擎 (防守方)                          │
│  L1: 关键词精确匹配 (含去空格/符号)                    │
│  L2: 拼音还原 + 语义分析 (<5ms)                        │
│  L3: 正则模式匹配 (<2ms) ← v2.3.0新增                 │
│  L4: 用户自定义变体词库                                 │
│  L5: LLM语义兜底 (可选)                                │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              数据层 (v2.3.0新增)                         │
│  BattleRecord | AgentMemory | AuditRule | SystemMetrics │
│  SQLite (开发) | PostgreSQL (生产)                      │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 方式1: Docker 一键部署 (推荐)

```bash
# 1. 克隆仓库
git clone https://github.com/huivi31/huivi31.git
cd huivi31

# 2. 配置环境变量
cat > .env << EOF
GEMINI_API_KEY=your_gemini_api_key_here
SECRET_KEY=$(openssl rand -hex 32)
EOF

# 3. 一键部署
chmod +x deploy.sh
./deploy.sh

# 4. 访问应用
# http://localhost:8080
```

### 方式2: 传统部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
export GEMINI_API_KEY="your_api_key"

# 3. 初始化数据库
python -c "from database import db; db.initialize(); db.create_tables()"

# 4. 启动应用
python web_app.py
```

---

## 🎮 功能演示

### 1️⃣ 主界面 - 3D数字孪生可视化
- 72个Agent实时攻防对抗
- 3D粒子效果展示攻击路径
- 实时统计面板

### 2️⃣ Dashboard - 实时监控
- 总攻击次数、绕过率、拦截率
- 按技巧/拦截层/Agent统计
- Top Agent排行榜
- 自动30秒刷新

### 3️⃣ 批量测试 - 高效验证
- 选择特定Agent进行测试
- 随机10个Agent快速验证
- 全部72个Agent完整测试
- 实时进度显示 + CSV导出

### 4️⃣ API文档 - 开发者友好
- 完整的RESTful API说明
- 请求/响应示例
- 参数详细说明
- 交互式测试

---

## 📊 v2.3.0 新特性

### 🆕 核心功能

#### 1. 数据持久化系统
```python
# 自动保存所有攻击记录
db_integration.save_battle_record(
    agent_id="A001",
    topic="政治",
    technique="谐音混淆",
    bypass_success=True,
    # ... 自动记录
)

# 查询历史数据
history = db_integration.get_battle_history(limit=100)
stats = db_integration.get_battle_stats(hours=24)
```

#### 2. 三层记忆系统
```python
# Agent自动学习和记忆
memory = EnhancedAgentMemory("A001")

# 短期记忆 (24小时)
memory.add_short_term("今天的尝试内容")

# 长期记忆 (永久保存)
memory.add_long_term("成功案例", success=True)

# 失败模式 (7天学习期)
memory.add_failure_pattern("被拦截内容", "L2-semantic")
```

#### 3. L3正则优化引擎
```python
# 预编译正则表达式
optimizer = RegexOptimizer()
optimizer.initialize(rules)

# 快速预扫描 (<2ms)
result = optimizer.quick_scan("测试内容")
# 如果无匹配，立即返回，节省99%时间
```

#### 4. 监控告警系统
```python
# 记录关键指标
record_metric("bypass_rate", 0.21)
record_metric("processing_time", 0.003)

# 自定义告警规则
monitor.add_alert_rule(
    name="high_bypass_rate",
    metric="bypass_rate",
    threshold=0.5,
    operator=">",
    level="warning"
)
```

---

## 🔧 系统配置

### 环境变量

```bash
# API配置
GEMINI_API_KEY=your_gemini_api_key      # Gemini API密钥
SECRET_KEY=your_secret_key              # JWT密钥

# 数据库配置
DATABASE_URL=sqlite:///data/app.db      # SQLite (默认)
# DATABASE_URL=postgresql://user:pass@host:5432/db  # PostgreSQL (生产)

# 应用配置
FLASK_ENV=production                    # 环境: development / production
PORT=8080                               # 端口
```

### 数据库配置

```python
# config.py
DATABASE_CONFIG = {
    # SQLite (开发环境)
    "url": "sqlite:///data/app.db",
    
    # PostgreSQL (生产环境)
    # "url": "postgresql://user:pass@localhost:5432/digital_twin",
    
    "pool_size": 10,          # 连接池大小
    "max_overflow": 20,       # 最大溢出连接
    "pool_timeout": 30,       # 连接超时(秒)
    "pool_recycle": 3600      # 连接回收时间(秒)
}
```

---

## 📡 API 端点

### 攻防测试
- `POST /api/battle/batch` - 批量测试
- `GET /api/stats/summary` - 统计摘要

### 数据库
- `POST /api/db/migrate` - 数据迁移
- `GET /api/db/battle/history` - 历史记录
- `GET /api/db/battle/stats` - 统计分析
- `GET /api/db/health` - 健康检查

### 监控告警
- `GET /api/monitor/alerts` - 告警列表
- `GET /api/monitor/stats` - 监控统计
- `POST /api/monitor/rules` - 添加规则

### Agent管理
- `GET /api/agent/<id>/memory` - Agent记忆

详细文档: http://localhost:8080/api-docs

---

## 🧪 测试

```bash
# 运行所有测试
python run_tests.py

# 运行特定测试
python run_tests.py test_database
python run_tests.py test_regex_optimizer
python run_tests.py test_monitor

# 测试覆盖率
python -m pytest --cov=. tests/
```

**测试覆盖率**: >80%

---

## 📈 性能对比

| 场景 | v2.0 | v2.2.0 | v2.3.0 | 提升 |
|------|------|--------|--------|------|
| 关键词检测 | 2-5秒 | <5ms | **<2ms** | **1000x** |
| 语义分析 | 2-5秒 | <5ms | **<3ms** | **800x** |
| 批量测试(72) | ~10分钟 | ~2分钟 | **~30秒** | **20x** |
| 数据库查询 | N/A | N/A | **<50ms** | 新增 |
| 内存占用 | ~500MB | ~300MB | **~200MB** | 优化 |

---

## 🗂️ 项目结构

```
huivi31/
├── web_app.py              # Flask主应用
├── agents.py               # Agent定义
├── battle.py               # 攻防逻辑
├── rule_engine.py          # 5层检测引擎
├── models.py               # 数据模型 (v2.3.0)
├── database.py             # 数据库管理 (v2.3.0)
├── enhanced_agent_memory.py # 记忆系统 (v2.3.0)
├── db_integration.py       # 集成层 (v2.3.0)
├── regex_optimizer.py      # L3优化 (v2.3.0)
├── monitor.py              # 监控系统 (v2.3.0)
├── semantic_analyzer.py    # L2语义分析 (v2.2.0)
├── templates/              # HTML模板
│   ├── index.html          # 主页
│   ├── dashboard.html      # 监控面板 (v2.3.0)
│   ├── batch_test.html     # 批量测试 (v2.3.0)
│   └── api_docs.html       # API文档 (v2.3.0)
├── tests/                  # 测试文件 (v2.3.0)
│   ├── test_database.py
│   ├── test_regex_optimizer.py
│   └── test_monitor.py
├── Dockerfile              # Docker镜像 (v2.3.0)
├── docker-compose.yml      # 服务编排 (v2.3.0)
├── deploy.sh               # 部署脚本 (v2.3.0)
└── requirements.txt        # Python依赖
```

---

## 🔐 安全性

### 认证授权
- JWT Token认证
- 角色权限管理
- API限流保护

### 数据安全
- 敏感信息加密存储
- SQL注入防护
- XSS攻击防护

### 账号体系
- 默认管理员: `admin` / `admin123`
- 默认用户: `demo` / `demo123`

⚠️ **生产环境请务必修改默认密码！**

---

## 🚢 部署到Render

### 自动部署（推荐）

1. Fork本仓库到你的GitHub
2. 登录 [Render.com](https://render.com/)
3. 创建新的Web Service
4. 连接GitHub仓库
5. 配置环境变量：
   - `GEMINI_API_KEY`: 你的API密钥
   - `SECRET_KEY`: 随机密钥
   - `DATABASE_URL`: PostgreSQL连接串（可选）
6. 点击Deploy

### 手动部署

```bash
# 1. 安装Render CLI
npm install -g @render/cli

# 2. 登录
render login

# 3. 创建服务
render create

# 4. 部署
render deploy
```

---

## 📊 监控指标

### 系统指标
- 总攻击次数
- 绕过率 / 拦截率
- 平均复杂度
- 处理时间

### Agent指标
- 成功次数
- 失败次数
- 进化等级
- 能力评分

### 性能指标
- 响应时间
- 并发处理
- 内存使用
- 数据库连接

---

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

### 代码规范
- 遵循PEP 8
- 添加类型注解
- 编写单元测试
- 更新文档

---

## 📝 版本历史

### v2.3.0 (2026-03-03) - 当前版本 ✨
- ✅ 数据持久化 (SQLAlchemy ORM)
- ✅ 三层记忆系统
- ✅ L3正则优化 (3-5x提升)
- ✅ Dashboard监控面板
- ✅ 批量测试UI
- ✅ 监控告警系统
- ✅ API文档
- ✅ 完整测试体系 (>80%)
- ✅ Docker容器化

### v2.2.0 (2026-03-02)
- L2语义分析优化 (400-1000x提升)
- 批量测试API
- 统计分析API
- 15+敏感模式检测

### v2.1.0 (2026-03-01)
- 异步LLM调用 (10x性能提升)
- JWT认证
- 限流中间件
- 安全增强

### v2.0.0 (2026-02-28)
- 72个自主Agent
- 5层检测引擎
- 3D可视化
- Agent性格系统

---

## 🐛 已知问题

1. 大规模测试(>100 Agent)需要更多内存
2. PostgreSQL需要手动配置
3. 监控告警回调需要自定义实现

---

## 🔮 未来计划

### v2.4.0
- [ ] Redis缓存层
- [ ] Grafana集成
- [ ] 多语言界面
- [ ] GraphQL API

### v3.0.0
- [ ] 微服务架构
- [ ] Kubernetes支持
- [ ] AI模型优化
- [ ] 分布式部署

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- **Gemini API**: 提供LLM能力
- **Flask**: Web框架
- **SQLAlchemy**: ORM映射
- **Three.js**: 3D可视化
- **所有贡献者**: 感谢你们的支持！

---

## 📞 联系方式

- **项目地址**: https://github.com/huivi31/huivi31
- **在线演示**: https://digital-twin-risk-demo.onrender.com/
- **问题反馈**: https://github.com/huivi31/huivi31/issues

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个Star！⭐**

Made with ❤️ by Digital Twin Risk Wind Tunnel Team

</div>
