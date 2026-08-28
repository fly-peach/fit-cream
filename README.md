# FitCream

AI 健身教练助手 —— FastAPI 健身业务后端 + LangGraph Agent 融合架构 + React 前端。

## 项目简介

FitCream 是一个智能健身训练管理平台，核心功能包括：

- **AI 对话教练**：基于 LangGraph ReAct Agent，支持自然语言制定计划、打卡、查询统计、记录饮食
- **训练计划管理**：创建/调整个性化训练计划，支持按目标（减脂/增肌/维持/健康）智能生成
- **饮食计划与记录**：AI 生成饮食计划，自然语言记录每日餐食，自动统计热量与宏量营养素
- **训练打卡**：自然语言描述即可完成打卡，自动匹配动作库
- **数据统计**：周/月/累计训练统计，连续打卡天数，体重趋势，饮食营养达标分析
- **知识库系统**：多知识库管理，文档上传/解析/向量检索，知识图谱可视化，MCP 协议对外暴露
- **认知记忆**：分层记忆架构（情景/语义/程序性），Agent 自动提取并回忆用户偏好与历史
- **SSE 流式对话**：实时流式输出 AI 回复（含思考过程、Tool 调用状态）

---

## Agent 能力详解

FitCream 的核心是一个基于 LangGraph 的 ReAct Agent，通过自然语言理解用户意图，自动调用对应的业务工具完成任务。

### 对话流程

```
用户: "帮我制定一个减脂计划，每周练 4 天"
  │
  ▼
Agent 理解意图 → 调用 create_plan 工具
  │
  ▼
工具执行: 根据目标/频率/水平生成个性化计划
  │
  ▼
Agent 组织回复: "已为你创建减脂计划，包含 4 天训练安排..."
```

### 工具列表

| 工具 | 功能 | 触发示例 |
|------|------|----------|
| `create_plan` | 创建训练计划 | "帮我制定一个增肌计划" / "我想减脂，每周 3 天" |
| `create_diet_plan` | 创建饮食计划 | "帮我做个饮食计划" / "安排一周的餐食" |
| `get_plan_detail` | 查看计划详情（含动作ID） | "我的计划里有哪些动作" / "周三练什么" |
| `update_plan` | 改计划名称/目标/难度/周期 | "把难度改成中级" / "计划改名叫增肌期" |
| `delete_plan` | 归档计划（可恢复） | "这个计划不要了" |
| `add_plan_day` / `remove_plan_day` | 增删训练日（按星期） | "加个周五训练日" / "周三改成休息日" |
| `add_exercise` / `update_exercise` / `remove_exercise` | 增删改动作 | "周三加个卧推4组8次" / "删掉二头弯举" |
| `list_plans` | 查看计划列表 | "看看我的计划" / "我有哪些计划" |
| `checkin` | 记录训练打卡 | "今天做了 3 组深蹲 80kg" / "打卡：跑步 5 公里" |
| `get_streak` | 查询连续打卡 | "我连续练了几天" / "我的打卡记录" |
| `query_stats` | 查询统计数据 | "这周练了几次" / "本月训练量" / "体重变化" |
| `get_exercises` | 查询动作库 | "有哪些胸部动作" / "深蹲怎么做" |
| `get_user_profile` | 获取用户信息 | "我的身高体重是多少" / "我的训练目标" |
| `update_user_profile` | 更新用户资料 | "我体重改成 75kg" / "目标改成增肌" |
| `record_meal` | 记录一餐饮食 | "我刚吃了一碗牛肉面" / "午餐米饭+红烧肉 600 大卡" |
| `query_diet_summary` | 查询饮食汇总 | "我今天吃了多少" / "昨天营养达标了吗" |
| `manage_meal` | 管理餐食记录 | "删掉今天的零食记录" / "修改早餐热量" |
| `set_nutrition_goals` | 设置营养目标 | "每天蛋白质目标 150g" / "热量控制在 2000" |
| `search_knowledge_base` | 搜索知识库 | "哑铃卧推怎么做" / "减脂的原理是什么" |
| `read_kb_document` | 阅读知识库文档 | "详细看看那篇关于蛋白质的文章" |
| `recall_memory` | 回忆用户记忆 | Agent 自动调用，回忆用户偏好与历史 |
| `save_preference` | 保存用户偏好 | Agent 自动调用，记住用户喜好 |
| `save_user_fact` | 保存用户事实 | Agent 自动调用，记录用户身体数据变化 |
| `save_event` | 记录重要事件 | Agent 自动调用，记录里程碑事件 |

### 计划生成能力

Agent 根据以下维度智能生成训练计划：

- **训练目标**：减脂 / 增肌 / 维持 / 健康
- **训练频率**：每周 1-7 天
- **经验水平**：新手 / 中级 / 高级
- **可用器材**：健身房 / 家庭 / 无器材
- **特殊需求**：伤病回避、时间限制等

生成的计划包含：
- 每日训练安排（分化训练）
- 具体动作、组数、次数、休息时间
- 渐进超负荷建议

饮食计划生成包含：
- 每日热量与宏量目标
- 按餐次（早/午/晚/加餐）分配
- 具体食物、份量、营养数据

### 打卡能力

- 自然语言解析训练内容（动作名、重量、组数、次数）
- 自动匹配动作库（支持模糊匹配）
- 记录训练时长、消耗卡路里
- 支持有氧/力量/混合训练类型

### 饮食记录能力

- 自然语言记录餐食（自动推断餐次、估算热量）
- 每日营养汇总（热量/蛋白质/碳水/脂肪）
- 营养目标设定与达标分析
- 餐食增删改管理

### 统计能力

- 周/月/累计训练次数和时长
- 连续打卡天数（streak）
- 各肌群训练频率分布
- 体重变化趋势
- 训练量（总重量）统计

### 知识库能力

- 多知识库创建与管理（管理员）
- 文档上传与多格式解析（Markdown/Excel/CSV/HTML/纯文本）
- 向量化索引与语义检索（LlamaIndex + pgvector）
- 知识图谱构建与可视化
- 用户自助订阅，Agent 对话时自动检索已订阅知识库
- MCP 协议暴露（只读 / 管理两级权限）

### 记忆能力

- 分层认知记忆：情景记忆（经历）/ 语义记忆（事实）/ 程序性记忆（偏好）
- 对话中自动提取用户信息并持久化
- 向量检索回忆相关记忆
- 用户画像构建与更新

### SSE 流式输出

对话通过 Server-Sent Events 实时推送，前端可展示：

| SSE 事件 | 含义 | 前端展示 |
|----------|------|----------|
| `start` | 流式开始 | 显示 AI 消息气泡 |
| `thinking` | 模型思考过程 | 可折叠的思考面板 |
| `token` | 正式回复内容 | 打字机效果逐字显示 |
| `tool_start` | 开始调用工具 | 显示 "正在创建计划..." |
| `tool_result` | 工具返回结果 | 显示工具执行状态 |
| `done` | 对话结束 | 隐藏加载状态 |
| `stopped` | 用户手动停止 | 显示已生成内容 |
| `error` | 错误 | 显示错误提示 |

### Middleware 机制

Agent 编译时注入以下中间件：

| Middleware | 功能 |
|------------|------|
| `IntentMiddleware` | 意图识别，渐进式提示词注入 |
| `AgentLoggingMiddleware` | 全链路日志（LLM/Tool 调用记录） |
| `RateLimitMiddleware` | 单次对话 LLM/Tool 调用次数上限 + 同工具重复调用限制 |
| `TokenUsageMiddleware` | Token 消耗追踪与统计 |
| `SummarizationMiddleware` | 长对话自动压缩（100K token 触发，保留最近 10 条） |
| `MemoryUpdateMiddleware` | 定期触发记忆提取（每 20K token） |
| `DevAuthMiddleware` | 开发环境自动注入管理员身份（仅 LangGraph Studio） |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + SSE-Starlette |
| Agent | LangChain `create_agent` + LangGraph |
| LLM | 通义千问 qwen3.5-flash / qwen3-vl-flash（视觉）（DashScope OpenAI 兼容接口） |
| 记忆 & 检索 | LlamaIndex + pgvector |
| 数据库 | PostgreSQL + SQLAlchemy 2.0 (async) + Alembic |
| 认证 | JWT (python-jose) + bcrypt + 阿里云 SMS 验证码 |
| 对象存储 | 阿里云 OSS（聊天图片） |
| MCP | fastapi-mcp（知识库只读/管理两级 MCP 服务） |
| 前端框架 | React 19 + Vite 8 + TypeScript 6 |
| 前端 UI | TailwindCSS 4 + shadcn/ui |
| 图表 | Recharts |
| 状态管理 | Zustand |
| 路由 | React Router 7 |
| 包管理 | uv (后端) / pnpm (前端) |

---

## 项目结构

```
fit-cream/
├── rogers/                  # 后端
│   ├── app/                 # FastAPI 应用
│   │   ├── main.py          # 入口（lifespan、CORS、静态文件、异常处理）
│   │   ├── config.py        # 配置（pydantic-settings）
│   │   ├── database.py      # 数据库引擎与会话
│   │   ├── mcp_server.py    # MCP 服务（/mcp/user、/mcp/admin）
│   │   ├── models/          # SQLAlchemy ORM 模型
│   │   ├── routers/         # API 路由
│   │   │   ├── auth.py      # 注册/登录/SMS/密码管理
│   │   │   ├── chat.py      # AI 对话（SSE 流式）
│   │   │   ├── plans.py     # 训练计划 CRUD
│   │   │   ├── diet_plans.py    # 饮食计划
│   │   │   ├── diet_meals.py    # 饮食记录
│   │   │   ├── checkins.py  # 打卡
│   │   │   ├── exercises.py # 动作库
│   │   │   ├── stats.py     # 统计
│   │   │   ├── users.py     # 用户资料
│   │   │   └── knowledge_bases.py  # 知识库
│   │   └── schemas/         # Pydantic 请求/响应模型
│   ├── src/
│   │   ├── agents/          # LangGraph Agent
│   │   │   ├── agent_graph.py   # Agent 入口（graph / dev_graph / init_agent）
│   │   │   └── harness/
│   │   │       ├── orchestration/   # Agent 工厂、模型工厂、系统提示词
│   │   │       ├── runtime/         # 中间件、记忆系统、会话服务
│   │   │       └── tools/           # Agent 工具（计划/打卡/饮食/统计/知识库/记忆）
│   │   ├── auth/            # 认证服务（JWT、SMS、种子管理员）
│   │   ├── fitme/           # 业务层
│   │   │   ├── models/      # ORM 模型
│   │   │   ├── schemas/     # Pydantic 模型
│   │   │   └── services/    # 业务服务
│   │   └── knowledge_base/  # 知识库（解析/分块/索引/图谱/检索）
│   ├── alembic/             # 数据库迁移
│   ├── seeds/               # 种子数据
│   ├── static/              # 前端构建产物（SPA 托管）
│   └── tests/               # 后端测试
├── frontend/                # React 前端
│   └── src/
│       ├── pages/           # 页面（dashboard/chat/plans/exercises/knowledge-bases/...）
│       ├── components/      # 组件
│       ├── hooks/           # 自定义 Hooks
│       └── lib/             # 工具函数、API 客户端
├── langgraph.json           # LangGraph Studio 配置
├── run.py                   # 后端启动脚本（Windows 兼容）
├── build_web.py             # 前端构建 → 后端 static/
├── pyproject.toml           # 后端依赖（uv）
└── .env.example             # 环境变量模板
```

---

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.12+ | 后端运行时 |
| Node.js | 20+ | 前端构建 |
| PostgreSQL | 15+ | 数据库（需安装 pgvector 扩展） |
| [uv](https://docs.astral.sh/uv/) | latest | Python 包管理器 |
| [pnpm](https://pnpm.io/) | 9+ | 前端包管理器 |

### 1. 克隆项目

```bash
git clone https://github.com/fly-peach/fit-cream.git
cd fit-cream
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入实际配置：

```env
# 数据库（必须修改）
DATABASE_URL=postgresql+asyncpg://fitcream:fitcream@localhost:5432/fitcream

# LLM API Key（必须修改）
DASHSCOPE_API_KEY=sk-your-actual-key

# JWT 密钥（至少 32 字符）
JWT_SECRET=your-super-secret-key-change-in-production-min-32-chars

# 种子管理员（首次启动自动创建）
SEED_ADMIN_PHONE=your-phone-number
SEED_ADMIN_PASSWORD=your-password-here
```

> 完整变量说明参见 `.env.example` 文件注释。

### 3. 初始化数据库

```bash
createdb fitcream
# 或通过 psql:
# psql -U postgres -c "CREATE DATABASE fitcream;"

# 安装 pgvector 扩展（知识库向量检索需要）
# psql -U postgres -d fitcream -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 4. 启动后端

```bash
uv sync

# Windows（推荐，解决 psycopg EventLoop 兼容性问题）
uv run python run.py

# Linux / macOS
cd rogers && uv run uvicorn app.main:app --reload --port 8000
```

启动后：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- MCP 用户端点：http://localhost:8000/mcp/user（用户 API Key 认证）
- MCP 管理端点：http://localhost:8000/mcp/admin（管理员 JWT）

> `DEBUG=true` 时自动建表 + 种子数据（管理员、动作库），无需手动执行 migration。

### 5. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

访问：http://localhost:5173

> Vite 已配置 `/api` 代理到 `http://localhost:8000`，前端请求自动转发到后端，无需处理 CORS。

### 6. LangGraph Studio（可选）

用于可视化调试 Agent 对话流程：

```bash
uv run langgraph dev
```

### 7. 构建前端到后端（生产部署）

```bash
python build_web.py
```

将前端 `dist/` 复制到 `rogers/static/`，后端直接托管 SPA。

---

## Docker 部署

### 前置条件

- Docker 24+
- Docker Compose v2+

### 一键启动

```bash
cp .env.example .env
# 编辑 .env，至少填写 DASHSCOPE_API_KEY、JWT_SECRET、SEED_ADMIN_PHONE、SEED_ADMIN_PASSWORD

docker compose up -d --build
```

启动后访问：http://localhost:8000

### 说明

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| `db` | `pgvector/pgvector:pg16` | 5432 | PostgreSQL + pgvector 扩展 |
| `app` | 本地构建 | 8000 | FastAPI 后端 + 前端静态文件 |

- `docker-compose.yml` 中 `DATABASE_URL` 已覆盖为容器内部地址（`db:5432`），`.env` 中的数据库配置仅用于本地开发。
- 数据库数据持久化在 `pgdata` volume 中，`docker compose down` 不会丢失数据。
- 本地部署通过 `docker-compose.override.yml` 覆盖 `DEBUG: "true"`：`init_db()` 自动建表 /
  补列 + 枚举 CHECK 约束 + 种子数据（管理员、动作库），**schema 变更无需手动迁移**。

### 数据库迁移（DEBUG=false 环境）

`init_db()` 仅 `DEBUG=true` 时运行；`docker-compose.yml` 生产 `DEBUG=false`，
**新增表/列不会自动创建**，须在部署重启前手动执行迁移脚本：

- 迁移脚本位于 `rogers/scripts/migrations/`，按日期命名（如 `2026-08-28_user_fitness_profiles.sql`），
  全部幂等、可重复执行；纯新增表向后兼容，可先执行 SQL 再部署代码。
- 在 db 容器内执行：

```bash
docker exec -i <db容器名> psql -U fitcream -d fitcream < rogers/scripts/migrations/<脚本名>.sql
```

- 本地验证迁移脚本（模拟生产路径）：`docker compose up -d db` 后手动执行上述命令即可，
  不影响 `app` 服务 `DEBUG=true` 的自动建表。

### 常用命令

```bash
# 查看日志
docker compose logs -f app

# 停止
docker compose down

# 停止并清除数据（会清空 pgdata 卷）
docker compose down -v

# 重新构建（代码更新后）
docker compose up -d --build
```

---

## 开发

```bash
# 后端测试
uv run pytest

# 代码检查
uv run ruff check rogers/

# 类型检查
uv run mypy rogers/

# 前端开发
cd frontend && pnpm dev

# 前端构建
cd frontend && pnpm build

# 前端 lint
cd frontend && pnpm lint

# 前端类型检查
cd frontend && pnpm typecheck
```

---

## 环境变量

参见根目录 `.env.example`，关键配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 异步连接串 | — |
| `DASHSCOPE_API_KEY` | 通义千问 API Key | — |
| `DASHSCOPE_MODEL` | Agent 对话模型 | `qwen3.7-flash` |
| `DASHSCOPE_VISION_MODEL` | 视觉理解模型 | `qwen3-vl-flash` |
| `DASHSCOPE_TEMPERATURE` | 生成温度 | `1.2` |
| `DASHSCOPE_ENABLE_THINKING` | 启用思考模式 | `true` |
| `JWT_SECRET` | JWT 签名密钥 | — |
| `DEBUG` | 调试模式（自动建表 + 种子数据） | `true` |
| `SEED_ADMIN_PHONE` | 种子管理员手机号 | — |
| `SEED_ADMIN_PASSWORD` | 种子管理员密码 | — |
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | 阿里云 AK（SMS/OSS） | — |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | 阿里云 SK | — |
| `ALIBABA_CLOUD_SMS_SIGN_NAME` | SMS 签名 | — |
| `ALIBABA_CLOUD_SMS_TEMPLATE_CODE` | SMS 模板 | — |
| `OSS_BUCKET_NAME` | OSS Bucket（留空回退 base64） | — |
| `AGENT_RATE_LIMIT` | Agent 对话限流（次/分钟） | `10` |
| `CORS_ORIGINS` | 允许的跨域来源 | `["http://localhost:3000","http://localhost:5173"]` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `LOG_DIR` | 日志输出目录 | `logs` |
| `VITE_API_URL` | 前端 API 地址 | `http://localhost:8000/api` |

---

## License

Private
