# FitCream

AI 健身教练助手 —— FastAPI 健身业务后端 + LangGraph Agent 融合架构。

## 项目简介

FitCream 是一个智能健身训练管理平台，核心功能包括：

- **AI 对话教练**：基于 LangGraph ReAct Agent，支持自然语言制定计划、打卡、查询统计
- **训练计划管理**：创建/调整个性化训练计划，支持按目标（减脂/增肌/维持/健康）智能生成
- **训练打卡**：自然语言描述即可完成打卡，自动匹配动作库
- **数据统计**：周/月/累计训练统计，连续打卡天数，体重趋势
- **SSE 流式对话**：实时流式输出 AI 回复（含思考过程）

## 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI + SSE-Starlette |
| Agent | LangChain `create_agent` + LangGraph |
| LLM | 通义千问 qwen3.5-flash（DashScope OpenAI 兼容接口） |
| 数据库 | PostgreSQL + SQLAlchemy 2.0 (async) |
| 认证 | JWT (python-jose) + bcrypt |
| 包管理 | uv |
| Python | 3.12+ |

## 项目结构

```
fit-cream/
├── rogers/                     # 后端主目录
│   ├── app/                    # FastAPI 业务应用
│   │   ├── main.py             # 应用入口 & lifespan
│   │   ├── config.py           # pydantic-settings 配置
│   │   ├── database.py         # 异步引擎 & Session 工厂
│   │   ├── dependencies.py     # 公共依赖（JWT 鉴权）
│   │   ├── models/             # SQLAlchemy ORM 模型
│   │   ├── routers/            # API 路由（auth/users/chat）
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── services/           # 业务逻辑层
│   │   └── utils/              # 工具函数（安全/异常/日志）
│   ├── agents/                 # LangGraph Agent
│   │   ├── agent_graph.py      # Agent 主入口（graph 变量）
│   │   ├── agent/              # Agent 工厂 & 模型工厂
│   │   │   ├── agent_factory.py    # create_agent + middleware
│   │   │   └── model_factory.py    # ChatDashScope（思考内容提取）
│   │   └── harness/            # Agent 辅助组件
│   │       ├── prompts/        # System Prompt 模板
│   │       ├── tools/          # LangChain Tools（调用 Service 层）
│   │       └── middleware/     # AgentMiddleware（日志/限流/Token追踪）
│   ├── .env.example            # 环境变量模板
│   └── langgraph.json          # LangGraph Studio 配置
├── frontend/                   # 前端（待开发）
├── docs/                       # 设计文档
├── pyproject.toml              # 项目依赖 & 工具配置
└── uv.lock                     # 锁定依赖版本
```

## 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL 15+
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装

```bash
# 克隆项目
git clone <repo-url> && cd fit-cream

# 安装依赖
uv sync

# 配置环境变量
cd rogers
cp .env.example .env
# 编辑 .env 填入数据库连接串和 API Key
```

### 初始化数据库

```bash
# 创建数据库
createdb fitcream

# 启动应用（DEBUG 模式自动建表）
cd rogers
uv run uvicorn app.main:app --reload --port 8000
```

### 启动服务

```bash
# FastAPI 后端
cd rogers
uv run uvicorn app.main:app --reload --port 8000

# LangGraph Studio（可选，用于调试 Agent）
cd rogers
uv run langgraph dev
```

### 访问

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/auth/refresh` | 刷新 Token |
| GET | `/api/users/me` | 获取当前用户 |
| PUT | `/api/users/me` | 更新用户资料 |
| POST | `/api/chat/send` | 发送消息（SSE 流式回复） |
| GET | `/api/chat/threads` | 对话线程列表 |
| GET | `/api/chat/threads/{id}/messages` | 线程消息历史 |
| DELETE | `/api/chat/threads/{id}` | 删除线程 |

## Agent 架构

```
用户消息 → create_agent (middleware 编译时注入)
              │
              ├── before_agent  → 日志初始化
              ├── before_model  → LLM 调用计数 / 限流检查
              ├── wrap_tool_call → Tool 执行监控 / 重复调用限制
              ├── after_model   → Token 追踪 / 日志
              └── after_agent   → 对话持久化 / 统计
              │
              ▼
         ReAct Loop: LLM → Tools → LLM → ... → 最终回复
```

**Middleware 列表（编译时注入）：**
- `AgentLoggingMiddleware` — 全链路日志
- `ModelCallLimitMiddleware` — LLM 调用次数限制
- `ToolCallLimitMiddleware` — Tool 调用次数限制
- `SameToolLimitMiddleware` — 同一 Tool 重复调用限制
- `TokenUsageMiddleware` — Token 消耗追踪
- `ConversationPersistenceMiddleware` — 对话持久化（按需）

## 开发

```bash
# 运行测试
uv run pytest

# 代码检查
uv run ruff check rogers/

# 类型检查
uv run mypy rogers/
```

## 环境变量

参见 `rogers/.env.example`，关键配置：

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 异步连接串 |
| `DASHSCOPE_API_KEY` | 通义千问 API Key |
| `JWT_SECRET` | JWT 签名密钥（生产环境必须修改） |
| `DEBUG` | 调试模式（自动建表） |

## License

Private
