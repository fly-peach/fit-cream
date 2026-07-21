# FitCream — AI 健身待办协作平台

> **项目状态：M0 初始化阶段** — 目录骨架已创建，核心代码待实现

构建一个 **FastAPI + LangGraph Agent + React** 的智能健身待办系统。

**核心衡量标准**：Agent 协作率 ≥ 80%——用户说的每句话 Agent 必须有真反馈（生成计划 / 调整日程 / 打卡确认 / 数据洞察），不能只是复读机。

---

## 目录

1. [技术栈](#技术栈)
2. [项目结构](#项目结构)
3. [当前实现状态](#当前实现状态)
4. [API 设计](#api-设计)
5. [LangGraph Agent](#langgraph-agent)
6. [数据库设计](#数据库设计)
7. [前端设计](#前端设计)
8. [认证与安全](#认证与安全)
9. [开发指南](#开发指南)
10. [验收标准](#验收标准)
11. [里程碑](#里程碑)
12. [禁止项](#禁止项)

---

## 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 前端 | React 18 + Vite + Zustand + React Router + TailwindCSS | React 18+ |
| 后端 | FastAPI + SQLAlchemy 2.0 + Alembic | FastAPI 0.115+ |
| Agent | LangGraph + LangChain（`create_react_agent`） | LangGraph 0.4+ |
| 包管理 | uv（后端）/ pnpm（前端） | uv 0.5+ |
| 数据库 | PostgreSQL | 16 |
| 认证 | JWT（access + refresh token） | — |
| 部署 | Docker Compose | — |

---

## 项目结构

```
fit-cream/
├── docs/
│   ├── app-docs.md              ← 本文档
│   └── app-docs-plan1.md        ← 实施计划
├── rogers/                      ← 后端（uv 管理）
│   ├── app/                     ← FastAPI 应用
│   │   ├── __init__.py
│   │   ├── main.py              ← FastAPI app 入口
│   │   ├── config.py            ← Settings（pydantic-settings）
│   │   ├── database.py          ← async engine + session
│   │   ├── models/              ← SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── plan.py
│   │   │   ├── checkin.py
│   │   │   ├── exercise.py
│   │   │   └── conversation.py
│   │   ├── schemas/             ← Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── plan.py
│   │   │   ├── checkin.py
│   │   │   └── stats.py
│   │   ├── routers/             ← API routes
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── plans.py
│   │   │   ├── checkins.py
│   │   │   ├── stats.py
│   │   │   └── agent.py         ← Agent chat 端点（SSE）
│   │   ├── services/            ← 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── plan_service.py
│   │   │   ├── checkin_service.py
│   │   │   └── stats_service.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── security.py      ← JWT / bcrypt
│   │       └── response.py      ← 统一响应格式
│   ├── agents/                  ← LangGraph Agent
│   │   ├── agent_graph.py       ← create_react_agent 定义
│   │   ├── agent/
│   │   │   ├── agent_factory.py ← Agent 工厂
│   │   │   └── model_factory.py ← LLM 模型工厂
│   │   └── harness/
│   │       ├── middleware/      ← Agent 中间件
│   │       ├── prompts/         ← System prompts
│   │       └── tools/           ← LangChain Tools
│   ├── alembic/                 ← DB migrations
│   │   ├── versions/
│   │   ├── env.py
│   │   └── alembic.ini
│   ├── seeds/                   ← 动作库种子数据
│   │   └── exercises.json       ← 100+ 健身动作
│   ├── tests/
│   ├── langgraph.json           ← langgraph dev 配置
│   ├── pyproject.toml           ← uv 项目配置
│   ├── uv.lock
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/               ← 页面组件
│   │   ├── components/          ← 通用组件
│   │   ├── store/               ← Zustand stores
│   │   ├── api/                 ← axios 封装
│   │   ├── hooks/               ← useSSE, useAuth
│   │   ├── router/              ← React Router 配置
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── Dockerfile
├── docker-compose.yml           ← postgres + rogers + frontend
├── .env.example
└── README.md
```

---

## 当前实现状态

| 模块 | 状态 | 说明 |
|---|---|---|
| 项目骨架 | ✅ 已创建 | 目录结构已建立 |
| 后端 FastAPI | ❌ 待实现 | 无 main.py、无路由、无模型 |
| 数据库 Models | ❌ 待实现 | models/ 目录为空 |
| Alembic 迁移 | ❌ 待实现 | 无迁移文件 |
| LangGraph Agent | 🔄 骨架 | agent_graph.py 等文件已创建但为空 |
| 前端 React | ❌ 待实现 | frontend/ 目录为空 |
| Docker 配置 | ❌ 待实现 | 无 docker-compose.yml |
| 种子数据 | ❌ 待实现 | seeds/ 目录为空 |

---

## API 设计

### 统一规范

- **响应格式**：`{ "code": 0, "message": "success", "data": {...} }`
- **分页参数**：`?page=1&size=20`
- **时间格式**：UTC 存储，响应带 timezone（ISO 8601）
- **错误码**：0=成功，401=未认证，403=无权限，404=不存在，422=参数错误

### 用户认证模块

| 方法 | 路径 | 说明 | 认证 |
|---|---|---|---|
| POST | `/api/auth/register` | 注册（邮箱 + 密码 bcrypt 哈希） | ❌ |
| POST | `/api/auth/login` | 登录 → 返回 JWT access_token（15min）+ refresh_token（7d） | ❌ |
| POST | `/api/auth/refresh` | 刷新 token | ❌ |
| GET | `/api/users/me` | 获取当前用户 profile | ✅ |
| PUT | `/api/users/me` | 更新身体数据 / 目标 | ✅ |

### 训练计划模块

| 方法 | 路径 | 说明 | 认证 |
|---|---|---|---|
| POST | `/api/plans` | 创建训练计划（名称、目标、周期、难度） | ✅ |
| GET | `/api/plans` | 列表（分页 + 筛选：active / archived / completed） | ✅ |
| GET | `/api/plans/{id}` | 详情（含所有 workout days） | ✅ |
| PUT | `/api/plans/{id}` | 更新 | ✅ |
| DELETE | `/api/plans/{id}` | 软删除 | ✅ |
| POST | `/api/plans/{id}/days` | 添加训练日（周一~周日 + 动作列表） | ✅ |

**训练动作字段**：名称、组数、次数、重量（kg）、休息时间（秒）

### 每日打卡模块

| 方法 | 路径 | 说明 | 认证 |
|---|---|---|---|
| POST | `/api/checkins` | 打卡（日期、完成动作列表、耗时、心情评分 1-5、备注） | ✅ |
| GET | `/api/checkins` | 按日期范围查询（`?start=&end=`） | ✅ |
| GET | `/api/checkins/streak` | 连续打卡天数 | ✅ |
| PUT | `/api/checkins/{id}` | 补卡 / 修改 | ✅ |

**校验规则**：
- 打卡日期不能是未来
- 心情评分范围 1-5
- 耗时必须 > 0

### 进度统计模块

| 方法 | 路径 | 说明 | 认证 |
|---|---|---|---|
| GET | `/api/stats/weekly` | 本周训练量（总组数、总时长、完成率） | ✅ |
| GET | `/api/stats/monthly` | 月度趋势（折线图数据） | ✅ |
| GET | `/api/stats/body` | 体重 / 体脂变化曲线 | ✅ |
| GET | `/api/stats/achievements` | 成就徽章列表（解锁条件真计算） | ✅ |

### Agent 对话模块

| 方法 | 路径 | 说明 | 认证 |
|---|---|---|---|
| POST | `/api/agent/chat` | 发送消息（SSE 流式响应） | ✅ |
| GET | `/api/agent/history` | 获取对话历史 | ✅ |
| DELETE | `/api/agent/history` | 清空对话历史 | ✅ |

---

## LangGraph Agent

### 架构设计

使用 LangChain 1.x 的 `create_react_agent`（来自 `langgraph.prebuilt`）构建 ReAct Agent：

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")
agent = create_react_agent(
    model=llm,
    tools=[
        create_plan_tool,
        adjust_plan_tool,
        checkin_tool,
        query_stats_tool,
        get_exercises_tool,
        get_user_profile_tool,
    ],
    prompt=SYSTEM_PROMPT,
    checkpointer=PostgresSaver(...),  # 多轮对话持久化
)
```

### 流程图

```
[用户输入]
    │
    ▼
┌──────────────────────────────────────────┐
│  create_react_agent (ReAct Loop)         │
│                                          │
│  LLM 思考 → 选择 Tool → 执行 → 观察     │
│       ↑                          │       │
│       └──────── 循环直到完成 ─────┘       │
│                                          │
│  Tools:                                  │
│  ├── create_plan(goal, days_per_week)    │
│  ├── adjust_plan(plan_id, changes)       │
│  ├── checkin(exercises, duration, mood)  │
│  ├── query_stats(period)                 │
│  ├── get_exercises(muscle_group)         │
│  └── get_user_profile()                  │
└──────────────────────────────────────────┘
    │
    ▼
[结构化响应 + 自然语言]
```

### 核心能力（6 项必须真生效）

| 能力 | 触发示例 | 真行为 |
|---|---|---|
| 生成计划 | "我想减脂，每周练4天" | 调 Plan Generator → 真创建 plan + days 入库 → 返回结构化计划 |
| 调整计划 | "这太累了，减一天" | 调 Plan Adjuster → 真修改 DB → 返回 diff |
| 自然语言打卡 | "今天深蹲5x5 100kg，用了45分钟" | 解析 → 真写 checkin 表 → 返回确认 + streak |
| 数据洞察 | "我这周练得怎么样" | 查 stats → 生成分析文本 + 图表数据 |
| 激励对话 | "不想练了" | 查历史 → 个性化激励（引用真实数据） |
| 动作建议 | "练胸有什么动作" | 返回动作库列表 + 推荐组合 |

### 技术要点

- **开发模式**：`langgraph dev` 启动 LangGraph API Server（含 Studio 调试 UI）
- **生产集成**：FastAPI 通过 `langgraph-sdk` 或直接 import graph 调用
- **状态管理**：`MessagesState` + 自定义 state（`user_id`、`current_plan`）
- **Tool Calling**：Tools 内部直接调 service 层函数（同进程，不走 HTTP）
- **Memory**：`PostgresSaver` checkpointer 持久化对话状态到 PostgreSQL
- **流式输出**：`agent.astream_events()` → SSE 端点，token 逐个推送
- **结构化输出**：`response_format` 参数支持 Pydantic model 输出（前端渲染卡片）

---

## 数据库设计

### 核心表

```sql
-- 用户表
users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    height_cm DECIMAL(5,2),
    weight_kg DECIMAL(5,2),
    age INT,
    gender VARCHAR(10),
    goal VARCHAR(50),  -- lose_fat / gain_muscle / maintain / improve_health
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 训练计划表
plans (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name VARCHAR(200) NOT NULL,
    goal VARCHAR(50),
    difficulty VARCHAR(20),  -- beginner / intermediate / advanced
    weeks INT,
    status VARCHAR(20) DEFAULT 'active',  -- active / archived / completed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 计划训练日
plan_days (
    id UUID PRIMARY KEY,
    plan_id UUID REFERENCES plans(id) ON DELETE CASCADE,
    day_of_week INT NOT NULL,  -- 1=周一 ... 7=周日
    focus VARCHAR(100),        -- 训练重点：胸/背/腿/休息
    rest_seconds INT DEFAULT 60
);

-- 动作库（种子数据 100+）
exercises (
    id UUID PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    muscle_group VARCHAR(50),  -- chest / back / legs / shoulders / arms / core
    equipment VARCHAR(100),    -- barbell / dumbbell / machine / bodyweight
    description TEXT
);

-- 训练日动作
plan_day_exercises (
    id UUID PRIMARY KEY,
    plan_day_id UUID REFERENCES plan_days(id) ON DELETE CASCADE,
    exercise_id UUID REFERENCES exercises(id),
    sets INT NOT NULL,
    reps INT NOT NULL,
    weight_kg DECIMAL(6,2),
    sort_order INT DEFAULT 0
);

-- 打卡记录
checkins (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    plan_day_id UUID REFERENCES plan_days(id),  -- 可为空（自由打卡）
    date DATE NOT NULL,
    duration_min INT NOT NULL,
    mood INT CHECK (mood BETWEEN 1 AND 5),
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, date)  -- 每天只能打卡一次
);

-- 打卡动作详情
checkin_exercises (
    id UUID PRIMARY KEY,
    checkin_id UUID REFERENCES checkins(id) ON DELETE CASCADE,
    exercise_id UUID REFERENCES exercises(id),
    sets_done INT,
    reps_done INT,
    weight_kg DECIMAL(6,2)
);

-- 对话历史
conversations (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    thread_id VARCHAR(100),  -- LangGraph thread ID
    role VARCHAR(20),        -- user / assistant
    content TEXT,
    metadata_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 成就徽章
achievements (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    type VARCHAR(50),        -- streak_7 / streak_30 / first_plan / total_100_workouts
    unlocked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 索引

```sql
CREATE INDEX idx_checkins_user_date ON checkins(user_id, date);
CREATE INDEX idx_conversations_user_created ON conversations(user_id, created_at);
CREATE INDEX idx_plans_user_status ON plans(user_id, status);
```

### 种子数据

`seeds/exercises.json` 包含 100+ 常见健身动作，按肌群分类：
- 胸部：卧推、飞鸟、俯卧撑等
- 背部：引体向上、划船、硬拉等
- 腿部：深蹲、腿举、弓步蹲等
- 肩部：推举、侧平举等
- 手臂：弯举、三头下压等
- 核心：平板支撑、卷腹等

---

## 前端设计

### 技术选型

| 关注点 | 方案 |
|---|---|
| 框架 | React 18（函数组件 + Hooks） |
| 构建 | Vite 5 |
| 路由 | React Router 6 |
| 状态管理 | Zustand（轻量，替代 Pinia） |
| 样式 | TailwindCSS 3 |
| HTTP | axios（拦截器自动 refresh token） |
| 图表 | ECharts |
| SSE | 原生 `EventSource` / `fetch` + ReadableStream 封装为 `useSSE` hook |

### 关键页面

| 页面 | 路由 | 功能 |
|---|---|---|
| 登录/注册 | `/auth` | JWT 流程，token 存 localStorage + axios 拦截器自动 refresh |
| Dashboard | `/` | 今日待练卡片 + 本周进度环 + 连续打卡火焰 + 快捷打卡按钮 |
| Agent 对话 | `/chat` | 聊天气泡 UI + SSE 流式渲染 + 结构化卡片 |
| 训练计划 | `/plans` | 周视图（周一~周日），每天动作列表，可拖拽排序 |
| 打卡日历 | `/calendar` | 月视图，绿/灰/红标记完成/未练/休息 |
| 统计 | `/stats` | ECharts 折线图（体重趋势、训练量趋势）+ 成就徽章墙 |
| 个人设置 | `/settings` | 身体数据编辑 + 目标设定 |

### Agent 对话页特性

- 聊天气泡 UI（用户右 / Agent 左）
- **流式渲染**：SSE 逐 token 显示，打字机效果
- Agent 返回结构化计划时渲染为**可交互卡片**（勾选动作 → 一键打卡）
- 快捷指令按钮：生成计划 / 打卡 / 看统计

### 设计语言

- 主色：`#10B981`（emerald）
- 暗色模式支持
- 字体：Inter / system-ui
- 卡片圆角：12px，阴影 subtle
- Agent 头像：🏋️
- 图表：ECharts 暗色主题

---

## 认证与安全

| 项目 | 实现 |
|---|---|
| 密码存储 | bcrypt（cost=12） |
| JWT 签名 | RS256（开发环境 HS256 可） |
| Token 有效期 | access: 15min, refresh: 7d |
| API 保护 | 所有 `/api/*` 除 auth 外需 Bearer token |
| Rate limit | Agent chat 10 req/min/user |
| CORS | 配置白名单 |
| SQL 注入 | SQLAlchemy ORM 参数化查询 |

---

## 开发指南

### 环境准备

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 后端依赖
cd rogers
uv sync

# 前端依赖
cd frontend
pnpm install
```

### 开发命令

```bash
# 后端
cd rogers
uv run uvicorn app.main:app --reload --port 8000

# LangGraph Agent 开发
uv run langgraph dev    # 启动 LangGraph Studio（含调试 UI）

# 前端
cd frontend
pnpm dev                # 启动 Vite dev server

# 数据库迁移
cd rogers
uv run alembic upgrade head    # 执行迁移
uv run alembic revision --autogenerate -m "message"  # 生成迁移
```

### Docker Compose 一键起

```yaml
services:
  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: fitcream
      POSTGRES_PASSWORD: fitcream
      POSTGRES_DB: fitcream
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fitcream"]
      interval: 5s
      timeout: 5s
      retries: 5

  rogers:
    build: ./rogers
    ports: ["8000:8000"]
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://fitcream:fitcream@postgres:5432/fitcream
    command: uv run uvicorn app.main:app --host 0.0.0.0 --reload

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [rogers]

volumes:
  pgdata:
```

启动后：
- API Swagger UI → http://localhost:8000/docs
- 前端 → http://localhost:3000

---

## 验收标准

| # | 场景 | 预期结果 |
|---|---|---|
| 1 | 注册登录 | 注册 → 登录 → 拿 token → 访问 /users/me 返回正确数据；token 过期后 refresh 无感续期 |
| 2 | Agent 生成计划 | 对话 "我想增肌，每周练5天" → Agent 流式回复 + 真创建 plan 入库 → 前端渲染计划卡片 → 数据库 plans 表有记录 |
| 3 | 自然语言打卡 | 对话 "今天练了背，引体向上4x8，划船4x10 60kg" → 真写 checkin + checkin_exercises → 返回确认 + 当前 streak |
| 4 | 计划调整 | 对话 "把周三改成休息日" → 真修改 plan_days → 返回更新后的周视图 |
| 5 | 统计查询 | 对话 "这周练得怎么样" → 返回真聚合数据（不是硬编码）+ 自然语言分析 |
| 6 | 连续打卡 | 连续 3 天打卡 → streak API 返回 3 → 前端火焰显示 3 |
| 7 | 流式输出 | Agent 回复是逐 token SSE 推送（浏览器 Network 面板可见 event-stream），不是一次性 JSON |
| 8 | Docker 一键起 | `docker compose up` → 3 个服务全绿 → 前端能正常对话 + 打卡 + 看统计 |

---

## 里程碑

| 阶段 | 内容 | 产出 | 状态 |
|---|---|---|---|
| M0 | 项目初始化 + 目录骨架 | 目录结构、配置文件 | ✅ 完成 |
| M1 | 后端骨架 + DB + Auth | 可跑 /docs，注册登录通 | ⬜ 待开始 |
| M2 | 训练计划 + 打卡 CRUD | 全部 REST 接口可用 | ⬜ 待开始 |
| M3 | LangGraph Agent 核心 | 对话生成计划 + 打卡入库 | ⬜ 待开始 |
| M4 | 统计 + 成就 | 聚合查询 + 徽章解锁 | ⬜ 待开始 |
| M5 | 前端全部页面 | 可交互 UI + SSE 对话 | ⬜ 待开始 |
| M6 | Docker + 种子数据 + 联调 | 一键部署，验收通过 | ⬜ 待开始 |

---

## 禁止项

- ❌ Agent 只是套壳 ChatGPT 单轮问答（必须多节点图 + 真调 DB）
- ❌ 打卡接口不校验日期合理性（不能打卡未来日期）
- ❌ 训练计划生成不考虑用户身体数据（150cm/50kg 不能推 100kg 计划）
- ❌ JWT token 过期后前端不自动 refresh（必须无感续期）
- ❌ Agent 流式输出是假的（必须真 SSE，不能一次性返回假装打字）
- ❌ 对话历史不持久化（刷新页面历史丢失）
- ❌ 密码明文存储
- ❌ 统计接口返回硬编码假数据（必须真聚合查询）
- ❌ 前端 Agent 返回的计划不可交互（必须能勾选 → 一键打卡）
- ❌ 没有种子数据，动作库为空

---

## 输入/输出

### 输入
- 用户基本信息（身高、体重、年龄、性别、健身目标）
- 用户自然语言对话（通过 Agent 交互）
- 可选：用户上传体测数据 / 饮食记录

### 输出
- 结构化训练计划（JSON + 可视化卡片）
- 打卡确认 + 连续天数
- 统计图表数据
- 个性化建议与激励