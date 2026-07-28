# 文档维护规范

## 文档结构

每个模块目录包含三类文档和一个 `update/` 更新计划目录。三类文档因模块类型而异：

- **后端模块（rogers/）**：Overview / Database / Services
- **接口模块（routers/）**：Overview / Endpoints
- **前端模块（frontend/）**：Overview / Pages / Components / Services

```
docs/
├── agent.md                         # 本文件 — 文档维护规范
│
├── rogers/                          # 后端模块
│   ├── agent/
│   │   ├── Overview-01-架构.md
│   │   ├── Overview-02-模型层.md
│   │   ├── Overview-03-中间件管道.md
│   │   ├── Overview-04-Prompt系统.md
│   │   ├── Services-01-工具系统.md
│   │   ├── Services-02-Memory系统.md
│   │   └── update/                  # agent 模块的更新计划
│   ├── auth/
│   │   ├── Overview-01-认证与授权.md
│   │   ├── Database-01-用户表.md
│   │   ├── Services-01-用户服务.md
│   │   └── update/                  # auth 模块的更新计划
│   ├── fitme/
│   │   ├── Overview-01-Router与认证.md
│   │   ├── Database-01-训练计划数据表.md
│   │   ├── Database-02-饮食计划数据表.md
│   │   ├── Services-01-Service层.md
│   │   └── update/                  # fitme 模块的更新计划
│   └── knowledgebase/
│       ├── Overview-01-Agent集成与MCP.md
│       ├── Database-01-数据表.md
│       ├── Services-01-文档处理管道.md
│       ├── Services-02-搜索系统.md
│       └── update/                  # knowledgebase 模块的更新计划
│
├── routers/                         # API 接口文档
│   ├── Overview-01-路由总览.md       # 路由注册、响应信封、错误码、认证依赖、中间件
│   ├── Endpoints-01-认证与用户.md     # auth + users
│   ├── Endpoints-02-聊天.md          # chat（SSE 流式）
│   ├── Endpoints-03-训练计划.md       # plans + exercises
│   ├── Endpoints-04-饮食计划.md       # diet_plans
│   ├── Endpoints-05-打卡与统计.md     # checkins + stats + achievements
│   ├── Endpoints-06-知识库.md         # knowledge_bases（含 MCP）
│   └── update/                      # routers 模块的更新计划
│
└── frontend/                        # 前端文档
    ├── Overview-01-架构.md           # 技术栈、项目结构、构建配置、样式系统
    ├── Overview-02-路由与状态.md       # 路由表、zustand 状态、认证流程
    ├── Pages-01-页面.md              # 10 个页面描述（路径/守卫/API 依赖）
    ├── Components-01-组件.md          # 组件层级（UI 基件/App 组件/ai-elements）
    ├── Services-01-服务层.md          # API 客户端、知识库 API、SSE 客户端、Hooks
    └── update/                      # frontend 模块的更新计划
```

### 文件功能与源码映射

#### rogers/ — 后端

##### agent/ — Agent 系统

| 文档 | 功能 | 对应源码 |
|------|------|----------|
| Overview-01-架构.md | Agent 整体架构、LangGraph 流程、Agent 注册机制、生命周期 | `rogers/src/agent/graph.py`, `rogers/src/agent/registry.py`, `rogers/src/agent/nodes/` |
| Overview-02-模型层.md | LLM 模型配置、Provider 抽象、token 统计、模型路由 | `rogers/src/agent/models.py`, `rogers/src/agent/providers/` |
| Overview-03-中间件管道.md | 请求中间件链、上下文注入、限流、错误处理 | `rogers/src/agent/middleware.py`, `rogers/src/middleware/` |
| Overview-04-Prompt系统.md | System prompt 组装、动态上下文构建、模板管理 | `rogers/src/agent/prompts.py`, `rogers/src/agent/context.py` |
| Services-01-工具系统.md | Agent Tool 定义、工具注册、参数 schema、调用流程 | `rogers/src/agent/tools/`, `rogers/src/agent/tool_registry.py` |
| Services-02-Memory系统.md | 记忆检索、语义向量存储、短期/长期记忆管理 | `rogers/src/agent/memory/`, `rogers/src/agent/vector_store.py` |

##### auth/ — 用户管理与认证

| 文档 | 功能 | 对应源码 |
|------|------|----------|
| Overview-01-认证与授权.md | 注册/登录流程、JWT 签发与校验、Token 刷新机制、权限模型 | `rogers/src/auth/router.py`, `rogers/src/auth/jwt.py`, `rogers/src/auth/dependencies.py` (deprecated → `rogers/app/routers/auth.py`, `rogers/utils/security.py`, `rogers/app/dependencies.py`) |
| Database-01-用户表.md | User 表字段设计、索引策略、扩展字段说明 | `rogers/src/fitme/models/user.py`, `rogers/src/auth/models.py` |
| Services-01-用户服务.md | AuthService、UserService 方法说明、业务规则、集成关系 | `rogers/src/fitme/services/auth_service.py`, `rogers/src/fitme/services/user_service.py` |

##### fitme/ — FitMe 健身业务

| 文档 | 功能 | 对应源码 |
|------|------|----------|
| Overview-01-Router与认证.md | API 路由总览、端点清单、响应格式、认证依赖 | `rogers/app/routers/`, `rogers/src/fitme/schemas/` |
| Database-01-训练计划数据表.md | 用户/成就/训练计划/动作库/打卡/对话数据表设计、设计原则 | `rogers/src/fitme/models/user.py`, `rogers/src/fitme/models/plan.py`, `rogers/src/fitme/models/exercise.py`, `rogers/src/fitme/models/checkin.py`, `rogers/src/fitme/models/conversation.py`, `rogers/src/fitme/models/thread_*.py` |
| Database-02-饮食计划数据表.md | 饮食计划/饮食日/餐食数据表设计、生成逻辑 | `rogers/src/fitme/models/diet_plan.py` |
| Services-01-Service层.md | 6 个 Service 类方法说明、业务逻辑、服务间依赖关系 | `rogers/src/fitme/services/` |

##### knowledgebase/ — 知识库

| 文档 | 功能 | 对应源码 |
|------|------|----------|
| Overview-01-Agent集成与MCP.md | MCP 协议集成、知识库与 Agent 的协作流程、触发条件 | `rogers/src/knowledgebase/agent.py`, `rogers/src/knowledgebase/mcp/` |
| Database-01-数据表.md | 知识库表设计 | `rogers/src/knowledgebase/models/` |
| Services-01-文档处理管道.md | 文档上传 → 解析 → 分块 → 向量化管道 | `rogers/src/knowledgebase/pipeline/`, `rogers/src/knowledgebase/parser.py` |
| Services-02-搜索系统.md | 混合搜索（向量 + 关键词）、重排序、过滤 | `rogers/src/knowledgebase/search.py`, `rogers/src/knowledgebase/reranker.py` |

#### routers/ — API 接口文档

| 文档 | 功能 | 对应源码 |
|------|------|----------|
| Overview-01-路由总览.md | 路由注册方式、ResponseModel 信封、ErrorCode 枚举、认证依赖链、全局异常处理器 | `rogers/app/routers/__init__.py`, `rogers/app/main.py`, `rogers/app/dependencies.py`, `rogers/utils/exceptions.py`, `rogers/app/config.py` |
| Endpoints-01-认证与用户.md | 注册/登录/刷新 Token、用户资料获取/更新 | `rogers/app/routers/auth.py`, `rogers/app/routers/users.py`, `rogers/src/fitme/schemas/user.py` |
| Endpoints-02-聊天.md | 流式对话、停止生成、图片上传、线程 CRUD、历史清空 | `rogers/app/routers/chat.py`, `rogers/src/fitme/schemas/chat.py` |
| Endpoints-03-训练计划.md | 训练计划 CRUD、训练日/动作管理、动作库搜索 | `rogers/app/routers/plans.py`, `rogers/app/routers/exercises.py`, `rogers/src/fitme/schemas/plan.py` |
| Endpoints-04-饮食计划.md | 饮食计划 CRUD、饮食日/餐食管理 | `rogers/app/routers/diet_plans.py`, `rogers/src/fitme/schemas/diet_plan.py` |
| Endpoints-05-打卡与统计.md | 打卡 CRUD、连续天数、周/月/身体/概览统计、成就系统 | `rogers/app/routers/checkins.py`, `rogers/app/routers/stats.py`, `rogers/app/routers/achievements.py`, `rogers/src/fitme/schemas/checkin.py` |
| Endpoints-06-知识库.md | 知识库 CRUD、文档 CRUD（上传/分块/索引）、搜索、图谱、Token 管理、MCP 集成 | `rogers/app/routers/knowledge_bases.py`, `rogers/src/knowledgebase/` |

#### frontend/ — 前端

| 文档 | 功能 | 对应源码 |
|------|------|----------|
| Overview-01-架构.md | 技术栈（React 19 + Vite 8 + Tailwind 4 + TS 6）、项目目录结构、构建配置、样式系统 | `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/index.css`, `frontend/tsconfig*.json` |
| Overview-02-路由与状态.md | 10 条路由定义、路由守卫、zustand 状态管理、认证流程 | `frontend/src/App.tsx`, `frontend/src/stores/auth-store.ts`, `frontend/src/stores/chat-store.ts` |
| Pages-01-页面.md | 10 个页面描述（路径/守卫/子组件/API 依赖/Hook 依赖） | `frontend/src/pages/` |
| Components-01-组件.md | 组件层级：App 级组件、shadcn UI 基件、ai-elements UI Kit、分页子组件 | `frontend/src/components/` |
| Services-01-服务层.md | 通用 API 客户端（api.ts）、知识库 API 封装（kb-api.ts, 27 方法）、SSE 流式客户端、Hooks | `frontend/src/lib/api.ts`, `frontend/src/lib/kb-api.ts`, `frontend/src/lib/sse-client.ts`, `frontend/src/hooks/` |

---

### 更新需求目录

每个模块的 `update/` 目录存放该模块的更新计划，命名规则为 `{状态}-需求-{简述}.md`：

| 状态前缀 | 含义 |
|----------|------|
| `undo` | 待执行 |
| `doing` | 执行中 |
| `done` | 已完成 |

需求文档内容结构：

```
# {模块名} {简述}

**日期**：YYYY-MM-DD
**来源**：代码审查 / Bug 反馈 / 需求变更 等
**详情**：需求背景描述

## 待办

- [ ] 任务描述 1
- [ ] 任务描述 2
```

状态变更时修改文件名前缀即可（`undo` → `doing` → `done`），无需移动文件。

**不将需求写入本文件**。本文件的 `## 四、已完成变更记录` 区块仅记录**历史日志摘要**。

---

## 一、更新流程

### 步骤 1：编写需求

在对应模块的 `docs/{module}/update/` 目录下创建需求文档，文件名格式 `undo-需求-{简述}.md`，包含日期、来源、详情和待办。

### 步骤 2：逐条执行

开始执行时将文件名前缀改为 `doing`。按需求文档中的 todo 逐条更新对应文档。每完成一项，将该条标记 `- [x]`。

### 步骤 3：记录完成

需求文档中所有 todo 标记完成后，将文件名改为 `done-需求-{简述}.md`，并在本文件 `## 四、已完成变更记录` 追加一条摘要。

---

## 二、文档编写格式

### 文档命名规则

每个模块目录下的文档按 `{Category}-{Number}-{Title}.md` 规则命名。

**类别前缀（按模块类型）：**

| 模块类型 | 类别 | 用途 | 示例 |
|----------|------|------|------|
| rogers/（后端） | Overview | 架构总览、模型层、中间件、Prompt、Router 等顶层设计 | Overview-01-架构.md |
| rogers/（后端） | Database | 数据库表设计 | Database-01-数据表.md |
| rogers/（后端） | Services | 工具系统、Service 层、文档管道、Memory、搜索等业务服务 | Services-01-工具系统.md |
| routers/（接口） | Overview | 路由总览、响应规范、错误体系、全局配置 | Overview-01-路由总览.md |
| routers/（接口） | Endpoints | 端点契约（方法/路径/认证/请求体/响应体/参数/逻辑） | Endpoints-01-认证与用户.md |
| frontend/（前端） | Overview | 架构总览、技术栈、路由与状态设计 | Overview-01-架构.md |
| frontend/（前端） | Pages | 页面描述（路由/功能/子组件/API 依赖） | Pages-01-页面.md |
| frontend/（前端） | Components | 组件层级与功能说明 | Components-01-组件.md |
| frontend/（前端） | Services | API 客户端、Hooks、工具库 | Services-01-服务层.md |

编号在同一类别内独立排序，表示阅读顺序。

### 内容要求

- **不含代码**：逻辑设计、数据表字段、API 端点契约、服务集成关系，不贴代码实现
- **不含对话/聊天式的说明**：不出现"我给你分析一下"、"我们来整理"等拟人化表达
- **Markdown 表格**：结构化信息用表格呈现

### Markdown 规范

```
# 一级标题（文档标题）

## 二级标题（大节）

### 三级标题（小节）

| 字段 | 类型 | 说明 |  （表格）
|------|------|------|
|      |      |      |

- 无序列表
- 条目

1. 有序列表
2. 条目
```

### 字段表格格式

数据库表字段统一用三列：

| 字段 | 类型 | 说明 |
|------|------|------|

字段名用反引号包裹，类型用标准 SQL 类型名（如 VARCHAR(200) 而不是 String 或字符串）。

### API 端点表格格式

| 方法 | 路径 | 用途 |
|------|------|------|

方法统一用大写（GET / POST / PUT / PATCH / DELETE）。

### 接口文档端点表格格式

接口文档中每个端点的结构描述使用：

| 项目 | 值 |
|------|-----|

请求体字段和响应体字段使用标准的字段表格。

### 保留内容类型

- 逻辑设计（架构、流程、设计决策）
- 数据库字段（表名、字段名、类型、约束、关系）
- 服务集成关系（哪个 Service 调用了哪个 Service）
- 配置参数（默认值、环境变量）
- API 端点（方法、路径、用途、请求体、响应体、认证方式）
- 业务规则（触发条件、计算公式、约束校验）
- 组件层级（组件名、文件、用途、props、依赖关系）
- 页面结构（路由、守卫、子组件、API 依赖）
- 状态管理（store 名、状态字段、方法、持久化策略）

### 禁止内容类型

- 源码片段（任何 .py / .ts / .tsx / .css 代码）
- 拟人化叙述（"我们来"、"请考虑"、"你需要注意的是"）
- 对话式追问（"你想要什么样的文档？"、"我是不是应该..."）
- 情绪化表达（使用啦、哦、哈等语气词）

---

## 三、示例：数据库字段表格

```
### conversations — 对话消息表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| user_id | UUID | FK→users.id CASCADE, 索引 | 所属用户 |
| thread_id | VARCHAR(100) | 索引 | 线程标识 |
| role | VARCHAR(20) | NOT NULL | user/assistant/tool |
| content | TEXT | nullable | 消息内容 |
| metadata_json | JSONB | nullable | 元数据 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |
```

---

## 四、已完成变更记录

### 2026-07-28 — 新增 routers/ 和 frontend/ 文档目录，优化 agent.md

- [x] 创建 `docs/routers/` 目录，编写 Overview-01-路由总览.md + 6 个 Endpoints 文档
- [x] 创建 `docs/frontend/` 目录，编写 Overview-01-架构.md + Overview-02-路由与状态.md + Pages-01-页面.md + Components-01-组件.md + Services-01-服务层.md
- [x] 修正 agent.md 中 router 源码路径（`rogers/src/fitme/routers/` → `rogers/app/routers/`）
- [x] agent.md 新增 routers/ 和 frontend/ 目录结构、源码映射、类别前缀
- [x] fitme Overview-01-Router与认证.md 转为引用 routers/ 接口文档

### 2026-07-28 — 文件重命名为 {Category}-{Number}-{Title}.md 格式

- [x] agent/ 6 个文件重命名
- [x] fitme/ 3 个文件重命名
- [x] knowledgebase/ 4 个文件重命名
- [x] agent.md 更新结构清单和命名规则

### 2026-07-28 — 新增 auth/ 目录，拆分用户管理文档

- [x] 创建 docs/rogers/auth/ 目录
- [x] 撰写认证流程、JWT、密码安全文档
- [x] 撰写 User 表完整字段设计文档
- [x] 撰写 AuthService、UserService、Agent 集成文档
- [x] 更新 fitme Router 文档：移除认证细节，改为引用 auth/
- [x] agent.md 新增 auth/ 目录清单

### 2026-07-28 - 拆分 fitme 数据库设计文档

- [x] 创建 Database-01-训练计划数据表.md（用户/成就/训练计划/动作库/打卡/对话 + 设计原则）
- [x] 创建 Database-02-饮食计划数据表.md（饮食计划/饮食日/餐食 + 生成逻辑）
- [x] 删除旧的 Database-01-数据表.md
- [x] 同步更新字段定义：achievement 新增 name/description/icon，exercise 新增 equipment/difficulty 索引，conversation 新增 GIN 索引，thread 表标注 ThreadBase 混入，checkin 移除冗余索引
- [x] agent.md 更新文件结构和源码映射表
