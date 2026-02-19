# 🌀 数字孪生风控风洞 | Digital Twin Risk Wind Tunnel

> 基于多智能体攻防演练的 3D 可视化内容风控系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-Backend-green?logo=flask" alt="Flask" />
  <img src="https://img.shields.io/badge/Three.js-3D_Engine-black?logo=threedotjs" alt="Three.js" />
  <img src="https://img.shields.io/badge/Render-Deployed-purple?logo=render" alt="Render" />
</p>

---

## ✨ 系统概览

72 个外国攻击 Agent 围攻 1 个中心质检 Agent 的 3D 实时对抗模拟平台。

**核心能力：**

- 🎯 **3D 风洞可视化** — Three.js 球体拓扑，实时渲染 72 个攻击节点 + 1 个质检中心
- ⚔️ **多智能体攻防** — 攻击体自学习、协作、变体生成，能力持续增强
- 📋 **规则治理** — 快照、变更申请、审批、应用，完整审计流程
- 🏢 **企业编排** — Campaign 基线/对抗、A/B 对比、回归矩阵
- 📚 **文档投喂** — PDF/TXT/JSON 上传，全体攻击体自动吸收知识

**在线演示：** [digital-twin-risk-demo.onrender.com](https://digital-twin-risk-demo.onrender.com/)

---

## 🎨 UI 设计

### 布局架构

```
┌─────────────────────────────────────────────┐
│  RISK WIND TUNNEL          72  38  0  0  -- │  ← 顶部状态栏
├──────────────────────┬──────────────────────┤
│                      │ ① → ② → ③ Stepper   │  ← 横向步骤指示
│   [Category 浮层]    │  主题 / 规则 / 测试    │
│                      │                      │
│                      │ 🚀 全员对抗测试        │  ← 始终可见主按钮
│     3D SPHERE        │                      │
│      (70%)           │ ▸ 测试结果             │  ← 可折叠区
│                      │ ▸ System Log          │
│                      │ ▸ Agent 配置           │
│                      │ ▸ OpenClaw 情报局      │
│                      │ ▸ 知识投喂              │
│                      │ ▸ 高级配置              │
│                      │ ▸ 企业级总控            │
└──────────────────────┴──────────────────────┘
```

### 视觉特性

| 特性 | 实现 |
|------|------|
| **Glassmorphism** | `backdrop-filter: blur(20px)` 毛玻璃效果 |
| **横向 Stepper** | 3 步工作流（主题→规则→测试），可点击切换 |
| **微动效** | 步骤脉冲、内容淡入滑动、按钮涟漪、弹簧过渡 |
| **字体** | Google Fonts Inter |
| **色彩** | 统一青蓝色系 `#00d4ff`，去除粉色 |
| **折叠面板** | 原生 `<details>` + 动画箭头旋转 |
| **左侧浮层** | 200px 紧凑分类面板，可折叠为图标 |

---

## 🔧 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Flask (`web_app.py`) |
| 前端 | Three.js + 原生 JS (`templates/index.html`) |
| 字体 | Google Fonts (Inter) |
| 持久化 | SQLite (`data/config.db`) |
| 部署 | Gunicorn + Render |

### 核心文件

| 文件 | 职责 |
|------|------|
| `web_app.py` | API 入口 + 页面路由 |
| `agents.py` | 攻击体/质检体定义与能力演化 |
| `battle.py` | 单测、迭代、协作等攻防流程 |
| `orchestrator.py` | 企业战役编排 |
| `rule_engine.py` | 规则引擎 |
| `attack_knowledge.py` | 知识库与投喂吸收 |
| `config_store.py` | 规则/快照/回归/告警持久化 |
| `templates/index.html` | 3D 控制台前端 |

---

## 🚀 快速启动

### 环境要求

- Python 3.11+
- 可选模型密钥（Gemini / OpenAI / Minimax）

### 安装 & 运行

```bash
# 安装依赖
pip install -r requirements.txt

# 开发模式
python web_app.py

# 生产模式
gunicorn web_app:app --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 600
```

访问 `http://127.0.0.1:8000`

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AI_PROVIDER` | `gemini` / `openai` / `minimax` | — |
| `GEMINI_API_KEY` | Gemini API Key | — |
| `OPENAI_API_KEY` | OpenAI API Key | — |
| `MINIMAX_API_KEY` | Minimax API Key | — |
| `RISK_CONFIG_DB_PATH` | SQLite 路径 | `data/config.db` |
| `KNOWLEDGE_CONTEXT_BUDGET` | 知识注入上下文预算 | `6000` |
| `MAX_DOC_UPLOAD_MB` | 文档上传上限 | `1024` |

---

## 📡 API 清单

<details>
<summary><b>规则与治理</b></summary>

- `POST /rules` — 设定规则
- `GET /rules` — 查看规则
- `POST /rules/snapshots` — 创建快照
- `GET /rules/snapshots` — 查看快照
- `POST /rules/snapshots/<id>/apply` — 应用快照
- `POST /rules/change-requests` — 变更申请
- `GET /rules/change-requests` — 查看变更
- `POST /rules/change-requests/<id>/review` — 审批
- `POST /rules/change-requests/<id>/apply` — 应用变更

</details>

<details>
<summary><b>攻防与 Agent</b></summary>

- `POST /battle/run` — 运行对抗
- `POST /battle/iterate` — 迭代攻击
- `POST /battle/collaborate` — 协作攻击
- `GET /battle/history` — 对抗历史
- `GET /agent/<id>/state` — Agent 状态
- `GET /agent/<id>/techniques/unlocked` — 已解锁技能
- `POST /agent/<id>/config` — 配置 Agent
- `GET /agents/progression` — 能力演进
- `GET /agents/states` — 全部状态

</details>

<details>
<summary><b>知识库</b></summary>

- `POST /knowledge/feed` — 直接投喂
- `POST /knowledge/feed/document` — 文档投喂 (multipart)
- `GET /knowledge/list` — 知识列表
- `POST /knowledge/clear` — 清空知识

</details>

<details>
<summary><b>企业编排与回归</b></summary>

- `POST /campaigns/run` — 运行战役
- `GET /campaigns` — 战役列表
- `GET /campaigns/<id>` — 战役详情
- `GET /campaigns/<id>/replay` — 回放
- `POST /campaigns/compare` — 对比
- `POST /campaigns/ab-run` — A/B 测试
- `POST /regressions/run` — 回归测试
- `GET /regressions/reports` — 回归报告
- `GET /regressions/reports/<id>/markdown` — Markdown 报告
- `POST /regressions/reports/<id>/dispatch-alerts` — 告警分发

</details>

<details>
<summary><b>告警与审计</b></summary>

- `GET /alerts/channels` — 告警通道
- `POST /alerts/channels` — 创建通道
- `POST /alerts/channels/<id>/toggle` — 开关通道
- `GET /alerts/incidents` — 事件列表
- `POST /alerts/incidents/<id>/ack` — 确认事件
- `GET /alerts/deliveries` — 投递记录
- `GET /audit/logs` — 审计日志

</details>

<details>
<summary><b>系统</b></summary>

- `GET /health` — 健康检查
- `GET /events` — SSE 事件流
- `POST /system/reset` — 系统重置

</details>

---

## 🏗️ 部署（Render）

仓库已含 `render.yaml` + `Procfile`，push 到 `main` 自动部署。

手动部署：Render 控制台 → `digital-twin-risk-demo` → Manual Deploy → `main`

---

## 🌙 夜间回归

```bash
python nightly_regression.py \
  --snapshot-ids rs_xxx,rs_yyy \
  --scenario nightly-regression \
  --baseline-rounds 1 \
  --adversarial-rounds 1 \
  --max-degradation 10 \
  --min-adversarial-detection 60 \
  --max-top-bypass-rate 55 \
  --dispatch-alerts 1 \
  --alert-channel-ids default_event_bus \
  --fail-on warning \
  --output-json nightly_result.json \
  --output-md nightly_report.md
```
