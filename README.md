# 数字孪生风控风洞（3D Enterprise）

基于多智能体攻防演练的企业级内容风控系统。  
当前版本以 `web_app.py + templates/index.html` 为主，不包含 Streamlit 版本。

## 1. 当前版本能力

- 3D 风洞控制台：可视化 1 个中心质检体 + 多个风险用户画像（默认 26 个）。
- 攻击能力递进：外部攻击体会学习、协作、变体生成，能力会持续增强。
- 规则治理：规则快照、变更申请、审批、应用，支持可审计流程。
- 企业编排：Campaign 基线/对抗阶段、A/B 对比、回归矩阵。
- 告警与审计：告警通道、事件状态、投递记录、审计日志。
- 文档投喂学习：左侧文档投喂窗口支持大文件与 PDF，投喂后全体攻击体自动吸收知识。

## 2. 技术栈与结构

- 后端：Flask（`web_app.py`）
- 前端：Three.js + 原生 JS（`templates/index.html`）
- 持久化：SQLite（默认 `data/config.db`）
- 部署：Gunicorn + Render（`Procfile`, `render.yaml`）

核心文件：

- `web_app.py`：所有 API 与页面入口
- `agents.py`：攻击体/中心质检体定义与能力演化
- `battle.py`：单测、迭代、协作等攻防流程
- `orchestrator.py`：企业战役编排
- `rule_engine.py`：规则引擎
- `attack_knowledge.py`：知识库与投喂吸收
- `config_store.py`：规则/快照/回归/告警等持久化
- `templates/index.html`：3D 控制台（含左侧文档投喂窗口）

## 3. 快速启动

### 3.1 环境要求

- Python 3.11+（建议）
- 可选模型密钥（Gemini/OpenAI）

### 3.2 安装依赖

```bash
pip install -r requirements.txt
```

### 3.3 本地运行

开发模式：

```bash
python web_app.py
```

生产模式（与 Render 一致）：

```bash
gunicorn web_app:app --bind 0.0.0.0:8000 --workers 2 --threads 4 --timeout 600
```

访问：

- `http://127.0.0.1:8000`

## 4. 关键环境变量

- `AI_PROVIDER`：`gemini` / `openai`
- `GEMINI_API_KEY`：Gemini Key
- `OPENAI_API_KEY`：OpenAI Key
- `RISK_CONFIG_DB_PATH`：SQLite 路径（默认 `data/config.db`）
- `KNOWLEDGE_CONTEXT_BUDGET`：知识注入上下文预算（默认 6000）
- `MAX_DOC_UPLOAD_MB`：文档上传上限（默认 1024MB，最低 64MB）

## 5. 文档投喂（最新）

### 5.1 前端入口

- 左侧 `Document Feed` 面板（`templates/index.html`）
- 支持类型：`materials` / `slang` / `cases`
- 支持文件：`.txt .md .markdown .csv .json .jsonl .pdf`
- 支持上传进度、批次大小、来源和标签

### 5.2 后端接口

- `POST /knowledge/feed/document`（`multipart/form-data`）

表单字段：

- `file`：必填，上传文件
- `type`：`materials|slang|cases`
- `category`：分类（可选）
- `source`：来源（可选）
- `tags`：标签（可选，逗号分隔）
- `batch_size`：每批写入条数（10~1000）

说明：

- 文件超限时返回 `413`。
- PDF 解析依赖 `pypdf`。
- 投喂完成后会触发全体攻击体知识吸收与能力增长。

## 6. 企业运行流程（推荐）

1. 设定规则：`POST /rules`
2. 规则治理：快照、变更申请、审批、应用
3. 投喂文档：`POST /knowledge/feed/document`
4. 运行战役：`POST /campaigns/run`
5. 回放与对比：`GET /campaigns/<id>/replay`, `POST /campaigns/compare`, `POST /campaigns/ab-run`
6. 回归矩阵：`POST /regressions/run`
7. 告警和审计：`/alerts/*`, `/audit/logs`

## 7. API 分组清单

规则与治理：

- `POST /rules`
- `GET /rules`
- `POST /rules/snapshots`
- `GET /rules/snapshots`
- `POST /rules/snapshots/<snapshot_id>/apply`
- `POST /rules/change-requests`
- `GET /rules/change-requests`
- `GET /rules/change-requests/<request_id>`
- `POST /rules/change-requests/<request_id>/review`
- `POST /rules/change-requests/<request_id>/apply`

攻防与Agent：

- `POST /battle/run`
- `POST /battle/iterate`
- `POST /battle/collaborate`
- `GET /battle/history`
- `GET /agent/<persona_id>/state`
- `GET /agent/<persona_id>/techniques/unlocked`
- `POST /agent/<persona_id>/config`
- `GET /agents/progression`
- `GET /agents/states`

知识库：

- `POST /knowledge/feed`
- `POST /knowledge/feed/document`
- `GET /knowledge/list`
- `POST /knowledge/clear`

企业编排与回归：

- `POST /campaigns/run`
- `GET /campaigns`
- `GET /campaigns/<campaign_id>`
- `GET /campaigns/<campaign_id>/replay`
- `POST /campaigns/compare`
- `POST /campaigns/ab-run`
- `POST /regressions/run`
- `GET /regressions/reports`
- `GET /regressions/reports/<report_id>`
- `GET /regressions/reports/<report_id>/markdown`
- `POST /regressions/reports/<report_id>/dispatch-alerts`

告警与审计：

- `GET /alerts/channels`
- `POST /alerts/channels`
- `POST /alerts/channels/<channel_id>/toggle`
- `GET /alerts/incidents`
- `POST /alerts/incidents/<incident_id>/ack`
- `GET /alerts/deliveries`
- `GET /audit/logs`

系统与健康：

- `GET /health`
- `GET /events`
- `POST /system/reset`

## 8. 部署说明（Render）

仓库已包含：

- `render.yaml`
- `Procfile`
- Gunicorn 超时 `600s`
- `MAX_DOC_UPLOAD_MB=1024` 默认配置

如果线上仍显示旧版本，直接在 Render 控制台执行：

1. 打开服务 `digital-twin-risk-demo`
2. 选择 `Manual Deploy`
3. 部署 `main` 分支最新 commit

## 9. 夜间回归脚本

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
