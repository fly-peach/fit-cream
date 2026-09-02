# FitCream

AI 健身教练助手 —— FastAPI 健身业务后端 + LangGraph ReAct Agent + React/Capacitor 客户端（Web / Android）。

代码以 **MIT** 协议开源（第三方素材许可范围见 [NOTICE.md](./NOTICE.md)）。

## 项目简介

FitCream 把「健身业务系统」和「Agent 运行时」融合在同一个 FastAPI 进程里：业务 CRUD 提供确定性数据底座，Agent 通过工具在自然语言里完成计划制定、打卡、饮食记录、统计与知识问答。

- **AI 对话教练**：LangGraph ReAct Agent，自然语言制定计划、打卡、查询统计、记录饮食
- **训练计划管理**：按目标（减脂/增肌/维持/健康）、频率、水平、器材生成个性化计划，支持逐项增删改
- **目标路线图与动作组**：身材原型库（分性别）→ 目标动作组 → 阶段里程碑自动出关判定
- **饮食计划与记录**：AI 生成饮食计划，自然语言记餐，自动汇总热量与三大营养素并做达标分析
- **训练打卡**：自然语言描述即完成打卡，动作库模糊匹配 + rerank
- **数据统计**：周/月/累计训练量、连续打卡、肌群分布、体重趋势、营养达标
- **知识库 + RAG**：多知识库管理、多格式解析、pgvector 向量检索 + rerank、知识图谱可视化、用户自助订阅
- **认知记忆**：情景 / 语义 / 程序性三层记忆，后台自动提炼、向量回忆
- **MCP 服务**：健身全景与知识库以 MCP 协议对外暴露（用户 / 管理两级）
- **计费系统**：钱包 + 单价 + 流水，按 token 计量扣费、余额门控、扫码充值回调、BYOK 免计费
- **SSE 流式对话**：思考过程、工具调用状态、用量明细实时推送，支持中断与人工审批续跑

---

## 架构总览

```
┌── 客户端 ─────────────────────────────────────────────────┐
│ React 19 SPA (Vite)  ──Capacitor 8──>  Android APK        │
│ 对话 / 计划 / 饮食 / 打卡 / 统计 / 知识库 / 目标 / 个人中心 │
└──────────────────────────┬────────────────────────────────┘
                           │ /api（JWT）· SSE 流式
┌──────────────────────────▼────────────────────────────────┐
│ FastAPI 应用层  rogers/app                                 │
│  routers/  auth · chat · plans · diet_* · checkins · stats │
│            exercises · users · knowledge_bases · goal_*    │
│            memory · moods · activity · billing · admin/*   │
│  main.py   lifespan 建表与种子 · CORS · SPA 静态托管       │
│  mcp_server.py  /mcp/user  /mcp/admin                      │
├───────────────────────────────────────────────────────────┤
│ Agent 运行时  rogers/src/agents/harness                    │
│  LangChain create_agent + LangGraph（Postgres checkpointer）│
│  Middleware 管线 → 模型路由（qwen / 用户自带 key）→ 工具    │
│  HITL 审批 · Skills 渐进披露 · SSE 事件流                   │
├───────────────────────────────────────────────────────────┤
│ 领域与能力层  rogers/src                                   │
│  fitme/          业务模型 · 服务                           │
│  knowledge_base/ 解析 · 分块 · 索引 · 图谱 · 检索          │
│  agents/         models（计费·记忆·会话）· auth · memory   │
├───────────────────────────────────────────────────────────┤
│ PostgreSQL 16 + pgvector                                   │
│  业务表 · 向量索引 · Agent checkpoint · token 用量/流水    │
└──────────────────────────┬────────────────────────────────┘
                           │
   外部服务：DashScope（对话/视觉/embedding/rerank）· DeepSeek（BYOK）
            阿里云 OSS（图片）· 阿里云 SMS（验证码）· 虎皮椒（支付回调）
```

**融合要点**：Agent 工具与业务服务同进程、同数据库会话，工具直接调用 `fitme/services`（不走 HTTP 自调），因此 Agent 行为与业务数据强一致；对话持久化由 SSE 流（`chat.py`）同步落库，不经中间件。

---

## Agent 运行时

### 对话主流程

```
用户消息
  │ RequestGateMiddleware：意图识别 → 按需注入专项提示词
  ▼
create_agent（LangGraph ReAct 循环）
  │ ModelRoutingMiddleware：按请求选模型 / 思考开关 / 用户自带 key
  ▼
LLM 决策 ──需要数据──> 工具（计划 · 打卡 · 饮食 · 统计 · 知识 · 记忆 · 目标）
  │                        │ 副作用工具 → HITL 中断，等前端审批后 resume
  │                        ▼
  │                     业务服务 → PostgreSQL
  ▼
SSE 推送（thinking / token / step / tool_* / usage）→ 前端逐字渲染
  │ FitCreamSummarizationMiddleware：超阈值压缩历史 + 后台提炼记忆
  ▼
done
```

### 模型与路由

| 用途 | 默认 | 说明 |
|------|------|------|
| 对话 | `qwen3.8-flash` | 多模态（文本 + 图片），统一模型不再按文本/视觉切换 |
| 视觉兜底 | `qwen3-vl-flash` | 图片识别备选 |
| 第三方 | `deepseek-v4-flash-vision-exp` | 用户自带 DeepSeek key（BYOK）时经 `ModelRoutingMiddleware` 按请求切换，且不计费 |
| Embedding | `text-embedding-v3` | 1024 维，记忆与知识库共用 |
| Rerank | `qwen3-rerank` | 知识检索 / 动作匹配重排，`RERANK_TOP_N=20` |

思考策略按请求反转：默认不思考，仅知识库问答与计划设计（`plan_design`）开启思考，think / nothink 两条缓存路径，缓存失效自动回退。温度默认 `0.7`。

### Middleware 管线

编译期按序注入（`harness/orchestration/agent_factory.py`）：

| # | Middleware | 职责 |
|---|------------|------|
| 1 | `RequestGateMiddleware` | 意图识别与渐进式提示词注入；知识库回答开关；`plan_design` 门控 |
| 2 | `PlanQueueMiddleware` | 计划设计队列进度快照临时注入（仅队列非空时） |
| 3 | `ContentValidationMiddleware` | 大纲 / 当日设计 / 提案的确定性兜底校验提示 |
| 4 | `ContextMessageGateMiddleware` | 队列入口视图裁剪（只改 `request.messages`，不动状态） |
| 5 | `ModelRoutingMiddleware` | 按请求切换 qwen / 用户 DeepSeek key + 思考开关 + 缓存回退 |
| 6 | `ModelRetryMiddleware` | 瞬态异常指数退避（`retry_on` 过滤，认证类错误不回退重试） |
| 7 | `ToolErrorMiddleware` | 工具异常转 error `ToolMessage`，交模型自纠 |
| 8 | `HumanInTheLoopMiddleware` | 可选（需 checkpointer）：副作用工具中断等待用户审批 |
| 9 | `AgentLoggingMiddleware` | LLM / Tool 全链路日志 |
| 10 | 限流中间件组 | 单次对话 LLM / Tool 调用上限 + 同工具重复调用限制（`AGENT_RATE_LIMIT`） |
| 11 | `TokenUsageMiddleware` | Token 用量追踪，上限动态：默认 150K / `plan_design` 200K |
| 12 | `TerminalToolMiddleware` | 终止型工具命中即收尾，避免多余一轮生成 |
| 13 | `FitCreamSummarizationMiddleware` | 会话压缩（健身域结构化摘要）+ 内置后台记忆提炼 |

### 工具（按域）

工具以 `@tool` + Pydantic `args_schema` 定义，内部使用 `session_scope()` 直连业务服务：

| 域 | 模块 | 能力 |
|----|------|------|
| 计划 | `plan/plan_tools.py` | 创建训练/饮食计划、查详情、改名与目标难度、归档、增删同步训练日、增删改动作（含有氧时长） |
| 计划呈现 | `plan/plan_queue_tools.py`、`present_plan_tool.py`、`present_form_tool.py` | 设计队列进度卡、大纲卡、提案卡、表单卡（走结构化事件，不占正文流） |
| 训练 | `training/checkin_tools.py`、`exercise_tools.py`、`stats_tools.py` | 自然语言打卡与动作匹配、动作库检索、周月累计统计与体重趋势 |
| 饮食 | `diet/diet_tools.py` | 记餐（自动推断餐次与热量）、每日营养汇总、餐食增删改、营养目标设定 |
| 目标 | `goal/goal_knowledge_tools.py`、`roadmap_tools.py` | 身材原型与推荐动作组知识、路线图创建/呈现、基线记录、里程碑出关判定 |
| 知识 | `knowledge/knowledge_tools.py` | 检索已订阅知识库、列出我的知识库、读文档原文 |
| 记忆 | `memory/memory_tools.py` | 回忆用户记忆；写入情景 / 语义 / 程序性记忆 |
| 用户 | `user/user_tools.py`、`summary_tools.py` | 资料读取与更新、健身画像（中文名工具）、身体与训练摘要 |
| 技能 | `skill/skill_load_tool.py` | 按需加载 `SKILL.md`（渐进披露，当前：`plan-creation`） |

副作用类工具（如创建计划 / 饮食计划）在启用 HITL 时以 `approval_needed` 事件挂起，前端出现「批准」按钮，批准后由 checkpointer 续跑。

### SSE 事件

| 事件 | 含义 | 前端表现 |
|------|------|----------|
| `start` | 流开始（带 `thread_id`） | 建立消息气泡 |
| `thinking` | 进入思考阶段 | 折叠思考面板 |
| `token` | 正文增量 | 打字机逐字渲染 |
| `step` | 阶段事件（`type: reply` 等） | 步骤状态与阶段进度 |
| `tool_start` / `tool_result` | 工具调用开始 / 返回 | "正在创建计划…" 等状态条 |
| `approval_needed` | 等待人工审批 | 提案卡批准按钮，审批后 resume |
| `usage` | 用量明细（含 `max_tokens` / reasoning / cache 读写） | Token 用量与余额展示 |
| `ds_key_invalid` | 用户自带 key 校验失败 | 提示回退平台模型 |
| `stopped` | 用户手动停止（带已生成内容） | 保留部分回复 |
| `done` / `error` | 正常结束（带工具调用汇总）/ 异常 | 收尾与错误提示 |

---

## 认知记忆

`harness/runtime/memory/`：`store`（读写与容量约束）· `extractor`（LLM 提炼）· `pipeline`（后台任务编排）· `embeddings`（向量化）。

| 层 | 内容 | 容量上限（env） |
|----|------|-----------------|
| 情景记忆 | 具体经历与里程碑事件 | `MEMORY_EPISODIC_MAX=200` |
| 语义记忆 | 稳定事实（身体数据等） | `MEMORY_SEMANTIC_MAX=15` |
| 程序性记忆 | 偏好与习惯 | `MEMORY_PROCEDURAL_MAX=50` |

提炼由会话压缩中间件顺带触发（不额外占一轮 LLM 调用），产出走后台计费（`source=memory_extraction`）；召回用 pgvector 相似度检索，工具与 RAG 共用同一 embedding 通道。

---

## 知识库与 RAG

`src/knowledge_base/`：`frontmatter` / `schema_templates`（结构化文档）· `chunker`（分块）· `indexer`（向量化入库）· `graph`（知识图谱）· `references`（引用与关系）· `lint`（质量校验）· `embeddings`。

- 多知识库创建与管理（管理端），用户自助订阅，对话时只检索已订阅库
- 多格式解析（Markdown / Excel / CSV / HTML / 纯文本，`unstructured`）
- pgvector 向量检索 + `qwen3-rerank` 重排，可开关（`KB_EMBEDDING_ENABLED` / `RERANK_ENABLED`）
- 知识图谱构建与前端可视化（`@xyflow/react`）
- 检索质量可评测：`rogers/scripts/eval_kb_search.py` + `rogers/seeds/search_eval_queries.json`

### MCP 对外暴露

`rogers/app/mcp_server.py`（`fastapi-mcp`，HTTP transport）：

| 端点 | 内容 | 认证 |
|------|------|------|
| `/mcp/user` | 健身全景 + 知识库用户态（`FITME_OPERATIONS` + `KB_USER_OPERATIONS`） | 用户 API Key |
| `/mcp/admin` | 知识库只读 + 管理操作（`KB_ADMIN_OPERATIONS`） | 管理员 JWT |

---

## 计费与额度

模型：`rogers/src/agents/models/billing.py`；服务：`src/fitme/services/billing_service.py`；路由：`/api/billing/*` 与管理端 `/api/admin/billing/*`。

| 表 | 作用 |
|----|------|
| `BillingAccount` | 余额、累计充值 / 赠送 / 消费、状态 |
| `BillingTransaction` | 流水：来源（`chat` / `memory_extraction` …）、模型提供方、input/output/cache/reasoning token 明细、计费后余额 |
| `BillingPricing` | 单价（元/百万 token），消费价含加价，另存成本价用于毛利核算，管理端热更新 |
| `BillingPackage` | 充值套餐与赠送额 |
| `RechargeApplication` | 充值单：平台流水号、支付方式、状态、审核人与时间 |

- **计量与计费分离**：token 明细记于 `user_token_usages`，金额与余额只走 billing 表，二者通过流水关联
- **BYOK 免计费**：用户自带 DeepSeek key 的会话 `billed=false`，只计量不扣费
- **余额门控**：余额不足直接拦截对话请求并给出充值引导
- **支付**：虎皮椒（Xunhupay）扫码下单 → `/api/billing/pay/notify` 回调验签（参数对以 `&` 拼接，空值不参与签名）自动到账；未配置商户参数时回退收款码 + 人工/自动确认（`RECHARGE_AUTO_CONFIRM`）
- **注册赠送**：`REGISTRATION_BONUS_*` 控制开关、金额与前 N 名名额，存量用户回填幂等
- 用户侧：个人中心充值入口、Token 用量卡；管理端：计费页与手动加量

---

## 目标体系与其他业务

- **身材原型库 v2**：`goal_archetypes` 以 `(key, gender)` 为主键，一行含原型图 + 目标动作 + 达成兜底指标（扁平结构，种子按 `(key, gender)` upsert 全量重灌）
- **动作组**：原型图库页 + 动作组详情页（单原型大图、分组动作、兜底指标），原型图转 webp 后静态挂载
- **目标路线图**：`/api/goal-roadmap`，基线记录 → 阶段里程碑 → 出关自动判定（`evaluate_current_milestone` / `check_milestone`）
- **健身画像**：`user_fitness_profiles`（含 `female_only` / `training_focus`），与基本资料在个人中心合并为单卡多 Tab
- **活动水平 / 情绪**：`/api/activity-levels`（含体感汇总）、`/api/moods`（列表与 upsert）
- **登录安全**：短信验证码（阿里云 DYPNS）、失败锁定（`LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCK_MINUTES`）、验证码频率与小时上限
- **图片存储**：阿里云 OSS（留空回退 base64），签名 URL 有效期可配，JPEG alpha 通道自动转 RGB

---

## 数据层与迁移

- SQLAlchemy 2.0 async（`asyncpg`）；ORM 分两处：`src/fitme/models`（业务）与 `src/agents/models`（会话 / 记忆 / 计费 / 用量）
- 迁移以幂等 SQL 脚本为准（Alembic 仅作依赖保留，仓库内无 alembic 工程目录）
- `DEBUG=true`：`init_db()` 启动时自动建表、补列、补枚举 CHECK 约束并灌种子（管理员、动作库、身材原型），**schema 变更免手动迁移**
- `DEBUG=false`（生产 compose）：只认迁移脚本 —— `rogers/scripts/migrations/*.sql`，按日期命名、全部幂等，可先执行 SQL 再部署代码
- 备份：compose 内置 `pg_dump` sidecar，每日导出至 `/backups`，保留 7 天

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + uvicorn + SSE-Starlette + Python 3.12+ |
| Agent | LangChain `create_agent` + LangGraph（Postgres checkpointer） |
| 模型接入 | `langchain-qwq`（ChatQwen / DashScope）· `langchain-openai` · `langchain-deepseek` |
| RAG 与记忆 | LlamaIndex（core / dashscope embeddings / postgres vector / dashscope rerank）+ pgvector |
| 数据库 | PostgreSQL 16 + asyncpg + SQLAlchemy 2.0（async ORM）+ pgvector |
| 认证 | JWT（python-jose）+ passlib(bcrypt) + 阿里云 SMS 验证码 |
| 对象存储 | 阿里云 OSS（oss2） |
| 文档解析 | unstructured（md / xlsx / csv / html / txt）+ lxml + BeautifulSoup |
| MCP | fastapi-mcp |
| 配置 | pydantic-settings（`.env`） |
| 前端 | React 19 + Vite 8 + TypeScript 6 + TailwindCSS 4 + shadcn/ui |
| 前端数据与展示 | Zustand 5 · React Router 7 · Recharts 3 · @xyflow/react（图谱）· streamdown + shiki（流式 Markdown / 代码）· motion |
| 移动端 | Capacitor 8（Android 壳 → `fitcream.apk`，经后端静态目录分发） |
| 质量 | pytest（asyncio auto）· ruff · mypy · eslint · prettier |
| 包管理 | uv（后端）/ pnpm（前端） |

---

## 项目结构

```
fit-cream/
├── rogers/                       # 后端
│   ├── app/
│   │   ├── main.py               # 入口：lifespan、CORS、SPA 静态托管、异常处理
│   │   ├── config.py             # pydantic-settings 全量配置
│   │   ├── database.py           # 引擎与会话（session_scope）
│   │   ├── dependencies.py       # 依赖注入（当前用户 / 管理员 / DB）
│   │   ├── mcp_server.py         # /mcp/user · /mcp/admin
│   │   └── routers/
│   │       ├── auth.py chat.py plans.py diet_plans.py diet_meals.py
│   │       ├── checkins.py exercises.py stats.py users.py
│   │       ├── knowledge_bases.py goal_knowledge.py goal_roadmap.py
│   │       ├── memory.py moods.py activity.py billing.py
│   │       └── admin/            # users · knowledge_bases · billing · stats · search_quality
│   ├── src/
│   │   ├── agents/
│   │   │   ├── agent_graph.py    # graph / dev_graph / init_agent
│   │   │   ├── models/           # 会话 · 记忆 · 用量 · 计费 ORM
│   │   │   ├── schemas/          # Agent 侧请求/响应模型
│   │   │   └── harness/
│   │   │       ├── orchestration/# Agent 工厂、模型工厂、系统提示词
│   │   │       ├── runtime/      # middleware/ · memory/ · conversation_service
│   │   │       ├── tools/        # plan · training · diet · goal · knowledge · memory · user · skill
│   │   │       └── skills/       # SKILL.md（渐进披露）+ loader
│   │   ├── auth/                 # JWT、SMS、密码、种子管理员
│   │   ├── fitme/                # models · schemas · services（业务层）
│   │   └── knowledge_base/       # 解析 · 分块 · 索引 · 图谱 · 检索
│   ├── utils/                    # 日志 · 响应体 · 异常 · OSS · 请求日志 · UUID7 · 时区
│   ├── scripts/migrations/       # 生产幂等 SQL（按日期命名）
│   ├── seeds/                    # 动作库 · 身材原型 · 评测 query
│   ├── static/                   # 前端构建产物 + 媒体（exercises / goals / apk）
│   ├── tests/                    # 单测与工具-DB 集成测试（conftest 自动补列）
│   ├── tests_offline/            # 离线评测与实验脚本
│   └── cloud_tests/              # 云端环境冒烟
├── frontend/                     # React SPA
│   ├── src/                      # pages · components · hooks · lib · stores · types · assets
│   ├── android/                  # Capacitor 原生工程（出 APK）
│   └── capacitor.config.ts
├── docs/                         # 模块文档（agent · auth · fitme · knowledgebase · frontend · routers）
├── LICENSE                       # MIT（代码与自研内容）
├── NOTICE.md                     # 第三方素材许可范围（数据集 / Gym visual 媒体）
├── docker-compose.yml            # db + app + 备份 sidecar
├── langgraph.json                # LangGraph Studio
├── run.py                        # 后端启动（Windows 兼容）
├── build_web.py                  # 前端构建 → rogers/static
├── pyproject.toml                # 后端依赖（uv）
└── .env.example                  # 环境变量模板（注释齐全）
```

---

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.12+ | 后端 |
| Node.js | 20+ | 前端 |
| PostgreSQL | 15+/16 | 需 `pgvector` 扩展 |
| uv | latest | Python 包管理 |
| pnpm | 9+ | 前端包管理 |

### 1. 克隆与配置

```bash
git clone https://github.com/fly-peach/fit-cream.git
cd fit-cream
cp .env.example .env
```

`.env` 至少填这几项：

```env
DATABASE_URL=postgresql+asyncpg://fitcream:fitcream@localhost:5432/fitcream
DASHSCOPE_API_KEY=sk-your-actual-key
JWT_SECRET=至少32字符的随机串
SEED_ADMIN_PHONE=your-phone-number
SEED_ADMIN_PASSWORD=your-password-here
```

> 完整说明见 `.env.example` 注释；支付（`XUNHUPAY_*`）与 OSS 留空即自动降级，不影响本地跑通。

### 2. 初始化数据库

```bash
createdb fitcream
# 或：psql -U postgres -c "CREATE DATABASE fitcream;"
psql -U postgres -d fitcream -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 3. 启动后端

```bash
uv sync

# Windows（推荐，规避 psycopg 事件循环兼容性）
uv run python run.py

# Linux / macOS
cd rogers && uv run uvicorn app.main:app --reload --port 8000
```

`DEBUG=true` 时启动即自动建表 + 灌种子，无需手动迁移。默认端点：

- 健康检查 http://localhost:8000/health
- MCP 用户端点 http://localhost:8000/mcp/user （用户 API Key）
- MCP 管理端点 http://localhost:8000/mcp/admin （管理员 JWT）
- OpenAPI 文档 http://localhost:8000/docs —— 需先在 `.env` 里置 `API_DOCS_ENABLED=true`（默认关闭）

### 4. 启动前端

```bash
cd frontend
pnpm install
pnpm dev            # http://localhost:5173
```

> Vite 已把 `/api` 代理到 `http://localhost:8000`，本地无需处理 CORS。

### 5. LangGraph Studio（可选）

```bash
uv run langgraph dev
```

可视化调试 Agent（开发态自动注入管理员身份的 `DevAuthMiddleware` 仅在此路径生效）。

### 6. 生产构建

```bash
python build_web.py     # frontend/dist → rogers/static，后端直接托管 SPA
```

Android 端：`cd frontend && pnpm build && npx cap sync android`，用 Gradle 出包，产物替换 `rogers/static/fitcream.apk`。

---

## Docker 部署

### 前置

Docker 24+ · Docker Compose v2+

### 一键启动

```bash
cp .env.example .env      # 至少填 DASHSCOPE_API_KEY / JWT_SECRET / SEED_ADMIN_*
docker compose up -d --build
```

访问 http://localhost:8000

| 服务 | 镜像 | 说明 |
|------|------|------|
| `db` | `pgvector/pgvector:pg16` | 数据卷挂在宿主机 `/var/lib/docker/pgsql/fitcreamdata`，`down` 不丢数据 |
| `app` | 本地构建 | 后端 + SPA 静态托管；`DATABASE_URL` 已覆盖为 `db:5432` |
| 备份 sidecar | `postgres:16-alpine` | 每日 `pg_dump` 到 `/backups`，保留 7 天 |

**静态资源挂载**（更新即生效，不必重建镜像）：

| 挂载 | 用途 |
|------|------|
| `/opt/fitcream/rogers/static/exercises` | 动作库媒体 |
| `/opt/fitcream/rogers/static/goals` | 身材原型图 |
| `/opt/fitcream/rogers/static/fitcream.apk` | Android 安装包 |

> ⚠️ 替换文件用 `scp`/`cp` **覆盖写**，不要先删源文件——inode 变更后容器内绑定挂载会失效。

**本地覆盖**：`docker-compose.override.yml` 将 `DEBUG` 置 `true`，走 `init_db()` 自动建表/补列/种子。生产（`DEBUG=false`）需在重启前手动执行迁移：

```bash
docker exec -i <db容器> psql -U fitcream -d fitcream \
  < rogers/scripts/migrations/2026-08-31_billing.sql
```

迁移脚本幂等、可重复执行；纯新增表向后兼容，可先跑 SQL 再发代码。

### 常用命令

```bash
docker compose logs -f app      # 看日志
docker compose down             # 停止（保留数据）
docker compose down -v          # 停止并清卷（会删数据）
docker compose up -d --build    # 代码更新后重建
```

---

## 开发

```bash
# 后端
uv run pytest                       # testpaths = rogers/tests + rogers/tests_offline
uv run pytest rogers/tests/test_tools   # 工具 → DB 落库集成测试
uv run ruff check rogers/
uv run mypy rogers/

# 前端
cd frontend
pnpm dev / pnpm build / pnpm preview
pnpm lint / pnpm typecheck / pnpm format
```

提交前建议跑 `pytest`（含 `test_billing`、`test_tools`）与 `pnpm typecheck`。模块级设计文档见 `docs/`，其组织与命名规范在 `docs/agent.md`。

---

## 环境变量

以 `.env.example` 为准，关键项：

| 变量 | 说明 | 默认 |
|------|------|------|
| `DEBUG` | 自动建表 + 种子 | `true` |
| `API_DOCS_ENABLED` | 是否开放 `/docs`、`/redoc` | `false` |
| `DATABASE_URL` | PostgreSQL 异步连接串 | — |
| `JWT_SECRET` / `JWT_ALGORITHM` | JWT 签名 | — / `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 访问令牌有效期 | `10080` |
| `DASHSCOPE_API_KEY` | 通义千问 Key | — |
| `DASHSCOPE_MODEL` / `DASHSCOPE_VISION_MODEL` | 对话 / 视觉模型 | `qwen3.8-flash` / `qwen3-vl-flash` |
| `DASHSCOPE_TEMPERATURE` / `DASHSCOPE_ENABLE_THINKING` | 温度 / 思考 | `0.7` / `true` |
| `RERANK_ENABLED` / `RERANK_MODEL` / `RERANK_TOP_N` | 检索重排 | `true` / `qwen3-rerank` / `20` |
| `KB_EMBEDDING_ENABLED` / `EXERCISE_RERANK_ENABLED` | 向量与动作重排开关 | `true` |
| `DEEPSEEK_API_KEY` | BYOK 兜底平台 key | 空 |
| `MEMORY_EPISODIC_MAX` / `MEMORY_SEMANTIC_MAX` / `MEMORY_PROCEDURAL_MAX` | 三层记忆容量 | `200` / `15` / `50` |
| `AGENT_RATE_LIMIT` | 每用户对话限流（次/分钟） | `10` |
| `REGISTRATION_BONUS_ENABLED` / `_AMOUNT` / `_FIRST_N` | 注册赠送额度 | `true` / `50` / `150` |
| `XUNHUPAY_APPID` / `_APP_SECRET` / `_NOTIFY_URL` | 支付（留空回退收款码） | 空 |
| `RECHARGE_AUTO_CONFIRM` | 到账方式 | `true` |
| `PAYMENT_QR_CODE_URL` | 收款码 | 空 |
| `ALIBABA_CLOUD_ACCESS_KEY_ID` / `_SECRET` / `_SMS_SIGN_NAME` / `_SMS_TEMPLATE_CODE` | 短信验证码 | — |
| `OSS_BUCKET_NAME` / `OSS_ENDPOINT` / `OSS_SIGN_URL_EXPIRES` | 图片存储（Bucket 留空回退 base64） | — |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCK_MINUTES` | 登录失败锁定 | `5` / `15` |
| `CORS_ORIGINS` | 允许来源 | 见 `.env.example` |
| `LOG_LEVEL` / `LOG_DIR` / `LOG_RETENTION_DAYS` / `SLOW_REQUEST_MS` | 日志与慢请求阈值 | `INFO` / `logs` / `30` / `3000` |
| `VITE_API_URL` | 前端 API 前缀 | `http://localhost:8000/api` |

---

## License

[MIT](./LICENSE) © 2026 wangtong —— 本项目代码可自由使用、修改、再分发与商用，保留版权声明即可。

许可范围与第三方素材署名见 **[NOTICE.md](./NOTICE.md)**，要点：

| 内容 | 许可 |
|------|------|
| 代码、自研种子（`goal_knowledge.json`、身材原型图等） | MIT（本仓库 `LICENSE`） |
| `rogers/seeds/exercises_dataset_*.json` 动作文本数据 | 上游 [exercises-dataset](https://github.com/hasaneyldrm/exercises-dataset) 的 MIT（其条款明确覆盖 data files 与指令文本），NOTICE 内已按要求保留上游版权声明 |
| 动作示意图 / GIF | **© Gym visual，不在 MIT 内**；`rogers/static/` 已 gitignore，本仓库不分发该媒体。若在你的产品中展示，需**自行向 Gym visual 取得许可**（保留署名是其条款要求，但不构成授权）——详见 [NOTICE.md](./NOTICE.md) |

> 依赖库（FastAPI / LangChain / LlamaIndex / React / shadcn 等）各自适用其上游许可。
