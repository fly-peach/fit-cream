# 文档维护规范

## 更新需求目录

每个顶层模块目录（`rogers/`、`routers/`、`frontend/`）下设置一个 `update/` 目录，统一存放该模块所有子功能的更新计划。不在子功能目录内单独配置 `update/`。

命名规则为 `{状态}-需求-{子模块}-{简述}.md`：

| 状态前缀 | 含义 |
|----------|------|
| undo | 待执行 |
| doing | 执行中 |
| done | 已完成 |

需求文档内容结构：

```
# {子模块} {简述}

日期：YYYY-MM-DD
来源：代码审查 / Bug 反馈 / 需求变更 等
详情：需求背景描述

## 待办

- [ ] 任务描述 1
- [ ] 任务描述 2
```

状态变更时修改文件名前缀即可，无需移动文件。

---

## 一、更新流程

### 步骤 1：编写需求

在对应顶层模块的 `docs/{module}/update/` 目录下创建需求文档，文件名格式 `undo-需求-{子模块}-{简述}.md`，包含日期、来源、详情和待办。

### 步骤 2：逐条执行

开始执行时将文件名前缀改为 `doing`。按需求文档中的 todo 逐条更新对应文档。每完成一项，将该条标记 `- [x]`。

### 步骤 3：记录完成

需求文档中所有 todo 标记完成后，将文件名改为 `done-需求-{简述}.md`，并在本文件「四、已完成变更记录」追加一条摘要。

---

## 二、文档编写格式

### 文档命名规则

每个模块目录下的文档按 `{Category}-{Number}-{Title}.md` 规则命名。

类别前缀（按模块类型）：

| 模块类型 | 类别 | 用途 | 示例 |
|----------|------|------|------|
| rogers/（后端） | Overview | 架构总览、模型层、中间件、Prompt、Router 等顶层设计 | Overview-01-架构.md |
| rogers/（后端） | Database | 数据库表设计 | Database-01-数据表.md |
| rogers/（后端） | Services | 工具系统、Service 层、文档管道、Memory、搜索等业务服务 | Services-01-工具系统.md |
| routers/（接口） | Overview | 路由总览、响应规范、错误体系、全局配置 | Overview-01-路由总览.md |
| routers/（接口） | Endpoints | 端点契约（方法/路径/认证/请求体/响应体/参数/逻辑） | Endpoints-01-认证与用户.md |
| frontend/（前端） | Overview | 架构总览、技术栈、路由与状态设计 | Overview-01-架构.md |
| frontend/（前端） | Pages | 页面描述（路径/守卫/API 依赖） | Pages-01-页面.md |
| frontend/（前端） | Components | 组件层级与功能说明 | Components-01-组件.md |
| frontend/（前端） | Services | API 客户端、Hooks、工具库 | Services-01-服务层.md |

编号在同一类别内独立排序，表示阅读顺序。

### 内容要求

- 不含代码实现：逻辑设计、数据表字段、API 端点契约、服务集成关系
- 不含对话式说明
- 使用 Markdown 表格呈现结构化信息

### Markdown 规范

```
# 一级标题（文档标题）

## 二级标题（大节）

### 三级标题（小节）

| 字段 | 类型 | 说明 |
|------|------|------|

- 无序列表
- 条目

1. 有序列表
2. 条目
```

### 字段表格格式

数据库表字段统一用三列：

| 字段 | 类型 | 说明 |

字段名用反引号包裹，类型用标准 SQL 类型名。

### API 端点表格格式

| 方法 | 路径 | 用途 |

方法统一用大写。

### 接口文档端点表格格式

接口文档中每个端点的结构描述使用：

| 项目 | 值 |

请求体字段和响应体字段使用标准字段表格。

### 保留内容类型

- 逻辑设计（架构、流程、设计决策）
- 数据库字段（表名、字段名、类型、约束、关系）
- 服务集成关系
- 配置参数（默认值、环境变量）
- API 端点（方法、路径、用途、请求体、响应体、认证方式）
- 业务规则（触发条件、计算公式、约束校验）
- 组件层级
- 页面结构
- 状态管理

### 禁止内容类型

- 源码片段（任何 .py / .ts / .tsx / .css 代码）
- 拟人化叙述
- 对话式追问
- 情绪化表达

---

## 三、示例：数据库字段表格

```
### conversations — 对话消息表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| user_id | UUID | FK->users.id CASCADE, 索引 | 所属用户 |
| thread_id | String(100) | 索引 | 对话线程标识 |
| role | String(20) | NOT NULL | user/assistant/tool |
| content | Text | nullable | 消息内容 |
| metadata_json | JSONB | nullable, GIN | 元数据 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |
```

---

## 四、已完成变更记录

### 2026-08-07 - 计划设计队列 + 训练日同步 + 请求日志上下文文档同步

- [x] 新建 docs/rogers/update/done-需求-agent-计划设计队列与训练日同步与日志上下文文档同步.md
- [x] agent 工具系统：补 sync_plan_day_tool、计划设计待办队列工具组（present_plan_queue_tool / present_day_design_tool / update_plan_queue_item_tool）、create_plan_tool 的 days 直落库路径
- [x] 中间件管道：中间件顺序表补 SkillsMiddleware / PlanQueueMiddleware，补 PlanQueue 详情与 AgentLogging 上下文注入
- [x] fitme Service 层：PlanService 补 copy_plan_day
- [x] routers：Endpoints-03 补 copy-day 端点、Endpoints-02 SSE step 补 reply + token 汇总日志、Overview 补 SLOW_REQUEST_MS 与日志体系
- [x] frontend：Components 补 PlanQueuePanel / DayDesignCard / SyncPlanDialog；Pages 补同步计划与队列面板、分页 8 条；Services/Overview 同步

### 2026-07-28 — fitme 模块代码优化（25项）+ 文档体系重构 + 前端改进

- [x] 优化 StatsService N+1 查询问题（批量 IN 查询）
- [x] 优化 DietPlanService 批量操作（客户端 uuid，合并 flush）
- [x] 优化 PlanService 生成空计划问题（按肌群查询动作填充）
- [x] 优化 CheckinService update 不处理 exercises 问题（增加替换逻辑）
- [x] 优化 StatsService 全表加载问题（使用 func.count/func.sum）
- [x] 优化 CheckinService get_streak 全量日期加载问题（SQL 窗口函数计算）
- [x] 优化 Exercise 表增加 equipment/difficulty 索引
- [x] 提取所有权校验 helper（Plan/Diet/Checkin 通用）
- [x] CheckinService 部分更新统一使用 model_dump(exclude_unset=True)
- [x] 增加 CheckinExerciseOut 自动填充 exercise 信息
- [x] 移除 StatsService 延迟导入（移到模块顶部）
- [x] Plan 删除策略改为软删除（与 Diet 统一）
- [x] CheckinService 使用 ErrorCode 常量（替换硬编码）
- [x] StatsService 返回类型改为 TypedDict
- [x] StatsService 周分组改为 SQL func.floor(extract) + GROUP BY
- [x] StatsService get_body_trend 抛出 NotFoundException（替代返回 {success:False}）
- [x] Conversation.metadata_json 增加 GIN 索引
- [x] ThreadUsage/ThreadMeta 提取 ThreadBase 混入（去重 user_id/thread_id）
- [x] DietPlanService 生成方法天数参数化
- [x] Checkin 表移除 user_id 冗余单列索引（由复合唯一索引覆盖）
- [x] PlanDay 移除隐式 eager load（get_plan_detail 显式 selectinload）
- [x] ExerciseService 增加分页（offset 参数 + 路由层暴露）
- [x] PlanService get_plan_detail 显式 selectinload
- [x] CheckinService create_checkin 预校验 exercise_id 存在性
- [x] 创建 docs/routers/ 和 docs/frontend/ 文档目录结构

### 2026-07-28 — 删除成就系统

- [x] 删除 achievement.py 模型
- [x] 更新 models/__init__.py，移除 Achievement 导入和导出
- [x] 更新 user.py 模型，移除 achievements relationship
- [x] 删除 achievements.py 路由
- [x] 更新 routers/__init__.py，移除 achievements_router
- [x] 更新 Database-01-训练计划数据表.md，删除 achievements 表定义
- [x] 更新 auth/Database-01-用户表.md，删除 achievements 关系引用
- [x] 更新 routers/Overview-01-路由总览.md，删除 achievements 路由条目
- [x] 更新 routers/Endpoints-05-打卡与统计.md，删除成就端点文档段
- [x] 更新 agent.md，清理成就相关引用

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

### 2026-07-28 — 拆分 fitme 数据库设计文档

- [x] 创建 Database-01-训练计划数据表.md（用户/训练计划/动作库/打卡/对话 + 设计原则）
- [x] 创建 Database-02-饮食计划数据表.md（饮食计划/饮食日/餐食 + 生成逻辑）
- [x] 删除旧的 Database-01-数据表.md
- [x] 更新字段定义：exercise 新增 equipment/difficulty 索引，conversation 新增 GIN 索引，thread 表标注 ThreadBase 混入，checkin 移除冗余索引
- [x] agent.md 更新文件结构和源码映射表

### 2026-07-30 - 短信验证码登录 + 聊天图片转存阿里云 OSS

- [x] 新增 `POST /auth/sms-login`（未注册手机号自动注册），复用登录失败锁定
- [x] 抽取 `_create_user` / `_finalize_login` / `_record_failed_attempt` 共用逻辑，修复失败 attempt 未持久化导致锁定失效
- [x] 验证码原子消费 + `secrets.randbelow` 均匀生成 + 每 IP 限频（VERIFICATION_CODE_MAX_PER_IP_HOUR）
- [x] VerificationCode 模型新增 ip 字段；RegisterRequest 新增可选 verification_code
- [x] 新增 `utils/oss.py`：聊天图片转存 OSS 私有路径，返回长期签名 URL，未配置回退 base64
- [x] `/chat/upload-image` 响应 url 改为 OSS 签名 URL
- [x] config / .env.example 同步 OSS 与验证码 IP 限频配置
- [x] 前端登录页重构为四模式（验证码/密码/注册/重置）+ 分格验证码 + 品牌面板
- [x] 文档同步：Endpoints-01、auth/Overview、auth/Database、auth/Services、Endpoints-02、routers/Overview、fitme/Services、frontend/Pages

### 2026-08-04 - 情景记忆与程序记忆容量上限

- [x] store.py 新增 `_trim_memories` 裁剪方法（删除前清空 semantic 的 source_episodic_id 引用）
- [x] store_episodic 写入后按 重要性升序→时间升序 裁剪到 MEMORY_EPISODIC_MAX（默认 200）
- [x] store_procedural 写入后按 最久未使用→创建时间升序 裁剪到 MEMORY_PROCEDURAL_MAX（默认 50）
- [x] config.py / .env.example 新增 MEMORY_EPISODIC_MAX / MEMORY_PROCEDURAL_MAX 配置
- [x] Services-02-Memory系统.md 新增「容量上限与淘汰策略」章节；Overview-01-架构.md 配置常量表同步

### 2026-08-04 - 语义记忆路由 + 聊天 SSE step 事件 + OSS 有效期 + 记忆阈值文档同步

- [x] routers/Overview-01-路由总览.md：路由注册表补 memory（第 11 项）；OSS_SIGN_URL_EXPIRES 默认值 3153600000 → 1296000（15 天）；认证依赖链补 Cookie JWT → Header JWT → API Key 多态说明
- [x] 新建 routers/Endpoints-09-记忆.md：GET /api/memory/semantic 端点契约
- [x] routers/Endpoints-02-聊天.md：SSE 事件表补 step（thought/tool/tool_result）；上传图片 OSS URL 改为 15 天 + 过期 image_url 清理；MessageOut metadata 补 steps/images
- [x] rogers/agent/Overview-01-架构.md：记忆提取触发阈值 20,000 → 100,000；调用流程补步骤流 metadata 与过期图片清理
- [x] rogers/agent/Overview-03-中间件管道.md：MemoryUpdateMiddleware 阈值 20,000 → 100,000
- [x] rogers/agent/Services-02-Memory系统.md：consolidate_memories 补 LLM 升华与版本合并说明；新增「语义记忆只读接口」章节
- [x] frontend/Pages-01-页面.md：ChatPage 补「我的记忆」面板、历史分页（首屏 10 条向上滚动）、AgentTrace、历史图片、API 调用与依赖
- [x] frontend/Components-01-组件.md：补 AgentTrace / ToolCallCard / MemoryPanel 组件
- [x] frontend/Services-01-服务层.md：useChatSSE 事件分发补 step；新增 useMemories hook
- [x] frontend/Overview-01-架构.md：项目结构补 memory-panel.tsx、use-memories.ts、types/memory.ts

### 2026-07-30 - 动作库 dataset 文档补全

- [x] 新建 Endpoints-08-动作库.md（exercises 路由 8 端点：列表/分类/肌群/器械统计/详情/创建/更新/删除）
- [x] fitme/Database-01 exercises 表补全 dataset 双语字段（body_part/target/secondary_muscles/instruction_steps/gif_url 等 15 列）+ 粗分类映射说明
- [x] fitme/Services ExerciseService 补 list_equipments 方法 + 更新说明（1324 条中英双语 dataset）
- [x] routers/Overview exercises 描述补器械统计与 dataset 规模
- [x] frontend/Overview 架构补 exercises/exercise-detail 页面、language-context、exercise-labels、types/exercise
- [x] frontend/Pages 补 ExercisesPage / ExerciseDetailPage
