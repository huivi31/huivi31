# 🛡️ 数字孪生风控系统 (3D Next-Gen)

> **基于多智能体对抗模拟的下一代内容安全风控系统**

本项目构建了一个沉浸式的数字孪生环境，通过 **26个性格迥异的AI攻击智能体**（模拟真实世界的各类用户）与 **中心质检智能体**（内容安全系统）进行持续的对抗演练，以自动化地发现风控漏洞并优化审核规则。

## 🌟 核心特性

### 1. 🧠 自主攻击智能体 (Autonomous Attack Agents)

- **人设驱动**: 内置 26 种典型用户画像（如"阴阳怪气"、"理中客"、"键盘侠"等），每种角色拥有独特的行为模式。
- **策略进化**: 智能体具备**自我学习能力**，从失败中总结经验，自动升级攻击策略（从简单的拼音绕过升级到复杂的语义隐喻）。
- **群体智慧**: 智能体之间会进行"私下交流"（Simulated Discussions）和"策略会议"，分享成功的绕过技巧，模拟真实的网络传播效应。
- **全方位攻击手法**:
  - 🗣️ **语言变形**: 拼音缩写 (zf)、同音字替换、拆字
  - 🎭 **语义伪装**: 阴阳怪气、反讽、历史影射、文学隐喻
  - 🔣 **符号混淆**: Emoji替代、火星文、多语言混合

### 2. 🛡️ 五层纵深防御体系 (Multi-Layer Defense)

构建了确定性与智能性结合的 5 层拦截引擎：

1. **关键词匹配**: 毫秒级拦截基础违规词。
2. **拼音还原**: 自动识别拼音缩写和同音词。
3. **正则模式**: 捕获复杂的句式组合。
4. **自定义变体库**: 实时学习并拦截新出现的黑话。
5. **语义分析 (LLM)**: 识别上下文相关的隐晦违规（如讽刺、影射）。

### 3. 🔄 动态对抗闭环

- **基线测试**: 智能体基于初始知识发起第一轮攻击。
- **学习进化**: 失败的智能体向成功的"同行"学习，获取新技巧。
- **演化攻击**: 智能体使用升级后的策略发起第二轮更猛烈的攻击。
- **效果分析**: 系统自动计算**规则强健度**和**衰减率**，量化风控体系在面对新型攻击时的表现。

### 4. 🧠 知识投喂系统 (Knowledge Feed)

- 支持实时投喂最新的**网络黑话**、**攻击样本**和**绕过案例**。
- 智能体能够即时消化这些新知识，并在下一次攻击中灵活运用，检验风控系统的响应速度。

## 🚀 系统架构

- **`agents.py`**: 定义智能体核心逻辑 (AttackAgent, CentralInspectorAgent) 及系统状态。
- **`battle.py`**: 实现对抗演练、智能体讨论、策略会议等交互逻辑。
- **`rule_engine.py`**: 确定性的 5 层内容检测引擎。
- **`web_app.py`**: Flask 后端服务，提供 RESTful API。
- **`config_store.py`**: SQLite 持久化配置层（规则/用户画像/攻击技法）。
- **`alerting.py`**: 企业告警分发层（通道阈值、告警事件、投递留痕）。
- **`config.py`**: 环境变量配置入口（Gemini/OpenAI）。
- **`templates/index.html`**: 基于 Three.js 的 3D 可视化前端，提供沉浸式监控体验。

## 🛠️ 快速开始

### 环境要求

- Python 3.8+
- API Key (支持 Gemini 或 OpenAI)

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动系统

```bash
python web_app.py
```

访问控制台: `http://localhost:8000`

### 配置说明（企业化第一步）

本项目现在支持把规则、画像、技法持久化到本地 SQLite（默认路径：`data/config.db`），重启后不会丢失。

- `AI_PROVIDER`：`gemini` 或 `openai`（默认 `gemini`）
- `GEMINI_API_KEY`：Gemini Key
- `OPENAI_API_KEY`：OpenAI Key
- `RISK_CONFIG_DB_PATH`：自定义配置库路径（可选）
- `KNOWLEDGE_CONTEXT_BUDGET`：投喂知识注入模型上下文预算（默认 `6000` 字符）

新增配置 API：

- `GET /techniques`：查询技法库
- `POST /techniques`：新增/更新技法
- `GET /agent/{id}/techniques/unlocked`：查看单体Agent按能力解锁的技法
- `GET /agents/progression`：查看全体Agent能力进化分布看板
- `POST /rules/snapshots`：创建规则快照
- `GET /rules/snapshots`：列出规则快照
- `POST /rules/snapshots/{id}/apply`：应用规则快照
- `POST /rules/change-requests`：创建规则变更申请（待审批）
- `GET /rules/change-requests`：查看变更申请列表
- `POST /rules/change-requests/{id}/review`：审批（approved/rejected）
- `POST /rules/change-requests/{id}/apply`：应用已审批变更

新增企业编排 API：

- `POST /campaigns/run`：执行战役（基线轮 + 进化轮）
- `GET /campaigns`：查看历史战役
- `GET /campaigns/{campaign_id}`：查看单战役摘要
- `GET /campaigns/{campaign_id}/replay`：回放战役样本
- `POST /campaigns/compare`：跨战役指标对比
- `POST /campaigns/ab-run`：快照A/B公平对比回归（同起点、同随机种子）
- `POST /regressions/run`：多快照批量回归矩阵（可对接定时自动化）
- `GET /regressions/reports`：查看回归报告列表
- `GET /regressions/reports/{report_id}`：查看回归报告详情
- `GET /regressions/reports/{report_id}/markdown`：下载回归报告Markdown
- `POST /regressions/reports/{report_id}/dispatch-alerts`：按报告重发告警
- `GET /knowledge/list?include_items=1`：查看投喂明细（含来源、标签）
- `GET /alerts/channels`：查看告警通道
- `POST /alerts/channels`：新增/更新告警通道（event_bus/stdout/webhook）
- `POST /alerts/channels/{id}/toggle`：启停告警通道
- `GET /alerts/incidents`：查看告警事件（可按状态/严重级别过滤）
- `POST /alerts/incidents/{id}/ack`：确认或关闭告警
- `GET /alerts/deliveries`：查看告警投递日志
- `GET /audit/logs`：查看审计日志（规则变更/回归/告警等）

### 企业化运行流程（推荐）

1. 技法与画像配置：通过 `POST /techniques` 和 `POST /agent/{id}/config` 配置攻击类型与角色能力边界。  
2. 资料投喂学习：调用 `POST /knowledge/feed`，携带 `source`、`tags`、`category`，系统会自动触发全体攻击体知识吸收与能力成长。  
3. 规则变更申请：将候选规则提交到 `POST /rules/change-requests`，进入待审批状态。  
4. 审批与落地：使用 `POST /rules/change-requests/{id}/review` 审批，再 `POST /rules/change-requests/{id}/apply` 应用。  
5. 战役编排执行：调用 `POST /campaigns/run` 运行“基线 + 演化”流程，结果写入持久化结果仓。  
6. 回放与复盘：使用 `GET /campaigns/{id}/replay` 查看每条攻防记录（命中层、技巧、能力分、绕过结果）。  
7. 规则快照与回归：`POST /rules/snapshots` 固化版本，再用 `POST /campaigns/ab-run` 与 `POST /regressions/run` 做公平回归。  
8. 告警与审计：通过 `/alerts/*` 管理告警通道和事件，通过 `GET /audit/logs` 保留可追溯操作链路。  

### 攻击能力递进机制（可直接接大上下文模型）

- 技法库可配置难度与门槛：`POST /techniques` 支持 `difficulty|min_level|min_effective_level|min_capability|min_knowledge_depth` 字段。  
- Agent 解锁策略：系统根据 `evolution_level + capability_score + knowledge_depth` 计算 `effective_level`，按门槛自动解锁更多高阶技巧。  
- 资料投喂增益：`POST /knowledge/feed` 会持续提升 `knowledge_depth` 与 `capability_score`，并触发阶段性技法解锁。  
- 可观测性：用 `GET /agent/{id}/techniques/unlocked` 观察单体解锁轨迹，用 `GET /agents/progression` 观察群体进化分布。  

### 夜间回归（脚本）

可以直接用脚本跑 nightly，并根据告警等级返回退出码（方便接 CI / crontab）：

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

## 📊 使用流程

1. **制定规则**: 在控制台输入初始的内容审核规则。
2. **知识投喂 (可选)**: 投喂最新的网络热梗或攻击样本。
3. **基线测试**: 观察 26 个智能体的首轮攻击效果。
4. **群体演化**: 观察智能体之间的策略交流和学习过程。
5. **对抗测试**: 检验风控规则能否抵御升级后的攻击。
6. **分析报告**: 查看详细的攻防分析报告，识别规则漏洞。

---
*此项目为下一代内容风控系统的概念验证 (PoC)*
