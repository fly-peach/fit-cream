# FitCream

AI 健身教练助手 —— FastAPI 健身业务后端 + LangGraph Agent 融合架构 + React 前端。

## 项目简介

FitCream 是一个智能健身训练管理平台，核心功能包括：

- **AI 对话教练**：基于 LangGraph ReAct Agent，支持自然语言制定计划、打卡、查询统计
- **训练计划管理**：创建/调整个性化训练计划，支持按目标（减脂/增肌/维持/健康）智能生成
- **训练打卡**：自然语言描述即可完成打卡，自动匹配动作库
- **数据统计**：周/月/累计训练统计，连续打卡天数，体重趋势
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
| `adjust_plan` | 调整现有计划 | "把周三的深蹲换成腿举" / "减少一天训练" |
| `checkin` | 记录训练打卡 | "今天做了 3 组深蹲 80kg" / "打卡：跑步 5 公里" |
| `query_stats` | 查询统计数据 | "这周练了几次" / "我的连续打卡天数" / "本月训练量" |
| `get_exercises` | 查询动作库 | "有哪些胸部动作" / "深蹲怎么做" |
| `get_user_profile` | 获取用户信息 | "我的身高体重是多少" / "我的训练目标" |

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

### 打卡能力

- 自然语言解析训练内容（动作名、重量、组数、次数）
- 自动匹配动作库（支持模糊匹配）
- 记录训练时长、消耗卡路里
- 支持有氧/力量/混合训练类型

### 统计能力

- 周/月/累计训练次数和时长
- 连续打卡天数（streak）
- 各肌群训练频率分布
- 体重变化趋势
- 训练量（总重量）统计

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

Agent 编译时注入以下中间件，提供可观测性和安全控制：

| Middleware | 功能 |
|------------|------|
| `AgentLoggingMiddleware` | 全链路日志（对话开始/结束/耗时） |
| `ModelCallLimitMiddleware` | 单次对话 LLM 调用次数上限 |
| `ToolCallLimitMiddleware` | 单次对话 Tool 调用总次数上限 |
| `SameToolLimitMiddleware` | 同一 Tool 重复调用限制（防死循环） |
| `TokenUsageMiddleware` | Token 消耗追踪与统计 |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + SSE-Starlette |
| Agent | LangChain `create_agent` + LangGraph |
| LLM | 通义千问 qwen3.5-flash（DashScope OpenAI 兼容接口） |
| 数据库 | PostgreSQL + SQLAlchemy 2.0 (async) |
| 认证 | JWT (python-jose) + bcrypt |
| 前端框架 | React 19 + Vite 6 + TypeScript |
| 前端 UI | TailwindCSS 4 + shadcn/ui |
| 状态管理 | Zustand |
| 路由 | React Router 7 |
| 包管理 | uv (后端) / pnpm (前端) |

---

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.12+ | 后端运行时 |
| Node.js | 20+ | 前端构建 |
| PostgreSQL | 15+ | 数据库 |
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
```

> 完整变量说明参见 `.env.example` 文件注释。

### 3. 初始化数据库

```bash
createdb fitcream
# 或通过 psql:
# psql -U postgres -c "CREATE DATABASE fitcream;"
```

### 4. 启动后端

```bash
uv sync

# Windows（推荐，解决 psycopg EventLoop 兼容性问题）
uv run python rogers/run.py

# Linux / macOS
cd rogers && uv run uvicorn app.main:app --reload --port 8000
```

启动后：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

> `DEBUG=true` 时自动建表，无需手动执行 migration。

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
cd rogers
uv run langgraph dev
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
```

---

## 环境变量

参见根目录 `.env.example`，关键配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 异步连接串 | — |
| `DASHSCOPE_API_KEY` | 通义千问 API Key | — |
| `JWT_SECRET` | JWT 签名密钥 | — |
| `DEBUG` | 调试模式（自动建表） | `true` |
| `AGENT_MODEL` | Agent 使用的模型 | `qwen3.5-flash` |
| `AGENT_TEMPERATURE` | 生成温度 | `0.7` |
| `AGENT_MAX_TOKENS` | 最大输出 Token | `2000` |
| `CORS_ORIGINS` | 允许的跨域来源 | `["http://localhost:5173"]` |
| `VITE_API_URL` | 前端 API 地址 | `http://localhost:8000/api` |

---

## License

Private