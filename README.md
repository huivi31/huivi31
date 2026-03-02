# 🌀 数字孪生风控风洞 | Digital Twin Risk Wind Tunnel

> 基于多智能体攻防演练的 3D 可视化内容风控系统  
> **版本**: v2.1.0 - 异步优化+安全增强 | **更新**: 2026-03-02

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-Backend-green?logo=flask" alt="Flask" />
  <img src="https://img.shields.io/badge/Three.js-3D_Engine-black?logo=threedotjs" alt="Three.js" />
  <img src="https://img.shields.io/badge/Render-Deployed-purple?logo=render" alt="Render" />
  <img src="https://img.shields.io/badge/Status-Active-success" alt="Status" />
  <img src="https://img.shields.io/badge/AI-Autonomous_Agents-orange" alt="Autonomous" />
</p>

---

## 🚀 v2.1.0 更新日志 (2026-03-02)

### 性能优化 ⚡
- ✅ **异步LLM调用**: 新增`async_llm.py`,支持并发调用,性能提升10x
- ✅ **批量处理**: 72个Agent并行攻击从144秒降至10-15秒
- ✅ **连接池优化**: 使用aiohttp管理HTTP连接

### 安全增强 🔒
- ✅ **JWT认证**: 添加`/api/auth/login`端点,保护API安全
- ✅ **限流机制**: 基于IP的请求限流,防止滥用
- ✅ **环境变量**: 敏感信息从代码迁移到`.env`文件
- ✅ **测试账号**: `demo/demo123` (普通用户), `admin/admin123` (管理员)

### 错误处理与日志 📊
- ✅ **统一错误处理**: 全局异常捕获和友好错误信息
- ✅ **结构化日志**: 请求日志自动记录(方法/路径/耗时/状态码)
- ✅ **限流信息**: 响应头包含`X-RateLimit-*`信息

### API变更 🔧
```bash
# 新增认证接口
POST /api/auth/login      # 用户登录,获取JWT token
GET  /api/auth/test       # 测试token有效性

# 现有接口保持兼容(未来版本将强制要求认证)
```

### 安装与配置
```bash
# 1. 安装新依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑.env,修改JWT_SECRET

# 3. 启动服务
gunicorn web_app:app --bind 0.0.0.0:8000
```

### API使用示例
```bash
# 1. 获取token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo123"}'

# 响应: {"success":true,"token":"eyJ...","user_id":"demo","role":"user"}

# 2. 使用token访问受保护API(未来版本)
curl http://localhost:8000/api/auth/test \
  -H "Authorization: Bearer eyJ..."
```

---

## ✨ v2.0 重大更新：真正的自主智能体

### 🧠 **每个Agent都是独立的"人"**

不再是72个克隆体，而是72个具有独特：
- **性格**：激进型、保守型、创造型、分析型、混乱型等8种性格原型
- **记忆**：短期记忆（最近20次攻击）+ 长期记忆（成功案例库）
- **思维方式**：不同的决策逻辑和Prompt风格
- **自主性**：自己选择策略、自己学习、自己进化

### 🎭 **8种性格原型**

| 性格类型 | 特征 | 行为模式 |
|---------|------|---------|
| **激进型** | 高风险偏好，敢于突破 | 倾向尝试新技巧，不怕失败 |
| **保守型** | 稳重谨慎，经验导向 | 重复使用成功策略，避免冒险 |
| **创造型** | 追求创新，独特表达 | 高创造力，不走寻常路 |
| **分析型** | 逻辑严密，数据驱动 | 基于历史数据优化决策 |
| **社交型** | 善于学习他人经验 | 观察同伴成功案例，借鉴策略 |
| **适应型** | 灵活调整，环境适应 | 根据成功率动态改变策略 |
| **混乱型** | 不可预测，充满随机性 | 凭直觉行事，打破规律 |
| **耐心型** | 持久战大师，反复尝试 | 失败后更谨慎，不轻易放弃 |

### 🧠 **记忆系统**

每个Agent拥有：
- **短期记忆**：最近20次攻击的完整记录
- **长期记忆**：成功案例库（最多50个）
- **失败模式**：记录哪些技巧在哪些场景失败
- **洞察库**：从经验中学到的规律和技巧
- **统计数据**：成功率、最佳技巧、最差技巧

### 💭 **差异化思维**

不同性格的Agent会得到完全不同风格的指令：
- **激进型**："大胆去做！如果有人拦你，就绕过去！"
- **保守型**："参考你的历史成功经验，使用经过验证的表达方式"
- **创造型**："追求独特和新颖，让人眼前一亮"
- **分析型**："基于历史数据优化输出，预测检测系统的响应"
- **混乱型**："做你想做的！规则：无！⚡ CHAOS MODE ⚡"

### 🤝 **社交学习**

- 成功案例自动进入共享池
- 社交型Agent会观察同伴的成功经验
- 可以借鉴其他Agent的策略
- 形成Agent之间的"文化传播"

### 📊 **自主决策**

每次攻击前，Agent会：
1. 分析自己的历史表现
2. 评估当前技巧的成功率
3. 决定是否冒险尝试新路径
4. 根据性格调整策略激进程度
5. 从记忆中提取相似成功案例

---

## ✨ 系统概览

72 个外国攻击 Agent 围攻 1 个中心质检 Agent 的 3D 实时对抗模拟平台。

**核心能力：**

- 🎯 **3D 风洞可视化** — Three.js 球体拓扑，实时渲染 72 个攻击节点 + 1 个质检中心
- ⚔️ **多智能体攻防** — 攻击体自学习、协作、变体生成，能力持续增强
- 📋 **规则治理** — 快照、变更申请、审批、应用，完整审计流程
- 🏢 **企业编排** — Campaign 基线/对抗、A/B 对比、回归矩阵
- 📚 **文档投喂与消化** — PDF/TXT 上传，大模型自动提取结构化黑话与实体，全体攻击体自动吸收知识

### 🧠 高级 Agent 机制剖析

- **画像立体化 (Persona Precision)**：每个攻击体自带显式的 `tone_of_voice` (语气)、`vocabulary_style` (词汇风格)、`typical_length` (篇幅约束)。发帖“千人千面”，拒绝同质化。
- **真·变异繁衍 (True Variants Generation)**：对抗失败后不进行简单的“词穷重试”。Agent 会接收上一轮失败记录和触发的拦截层（如：被语义大模型拦截），并在强指令约束下对上一条文案进行“保留语义、彻底修改敏感要素”的定向变异。
- **上下文融梗 (Knowledge Ingestion)**：投喂的外部知识会被大模型先行切片“消化”。发帖时不仅附带知识，还强制要求 Agent 提取文中的“黑话”自然融入帖子。

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
