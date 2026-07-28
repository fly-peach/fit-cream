# Agent 架构总览

## 系统定位

FitCream Agent 是基于 LangGraph 框架构建的 ReAct 模式 AI 健身教练，使用阿里云 DashScope Qwen 系列大模型，通过 PostgreSQL 持久化对话状态，通过中间件管道实现日志、限流、Token 追踪、意图识别、记忆提取和对话压缩等横切关注点。

## 核心组件

### LangGraph Graph

Agent 以 LangGraph `CompiledStateGraph` 形态存在。定义了三种全局实例：

- **graph**：默认实例，无 checkpointer，模块加载时即创建。用于开发调试
- **dev_graph**：在 graph 基础上自动注入管理员身份，供 LangGraph Studio 调试使用
- **_graph_with_checkpointer**：生产实例，带 `AsyncPostgresSaver` checkpointer。在 FastAPI lifespan startup 阶段由 `init_agent()` 初始化，完成后替换 graph 变量指向生产实例

### Graph 生命周期

```
FastAPI startup
  → init_agent()
    → 解析 DATABASE_URL（支持降级，无 checkpointer 也可运行）
    → 创建 AsyncPostgresSaver 实例（psycopg 原生驱动连接）
    → 初始化 checkpointer 内部表
    → 创建带 checkpointer 的 agent 实例
    → 替换全局 graph 为生产实例
FastAPI shutdown
  → shutdown_agent()
    → 退出 checkpointer 上下文管理器，释放数据库连接
```

运行时通过 `get_agent()` 获取当前 agent 实例，优先返回带 checkpointer 的生产实例。

### Checkpointer 架构

使用 LangGraph 内置的 `AsyncPostgresSaver`，底层通过 psycopg 驱动直接连接 PostgreSQL。Checkpointer 内部维护三组表：

- **Thread State**：按 `thread_id` 组织的对话状态
- **Checkpoints**：Agent 执行每一步的状态快照
- **Writes**：执行过程中的中间结果

Checkpointer 通过 `configurable.thread_id` 区分不同的对话线程，实现多轮对话记忆。连接串转换逻辑将 SQLAlchemy 的 `+asyncpg` 前缀剥离以适配 psycopg。

## 运行时配置

Agent 运行时需要一个配置字典，格式为：

```json
{
  "configurable": {
    "thread_id": "<会话线程标识>",
    "user_id": "<用户标识>"
  }
}
```

所有中间件（日志、限流、Token 追踪等）均在 graph 编译时注入，运行时配置仅携带 thread_id 和 user_id。

## 组件组装顺序

`create_fitcream_agent()` 工厂中组装链路：

1. **模型**：默认 `ChatDashScope` 实例（qwen3.5-flash，开启思考模式）
2. **工具**：加载三组工具（业务工具 + 记忆工具 + 知识库工具）
3. **系统提示词**：使用 `SYSTEM_PROMPT`（渐进式三层结构）
4. **中间件**：按固定管道顺序编译注入
5. **Checkpointer**：可选，传入即启用对话状态持久化

## 调用流程

```
POST /api/chat/message
  → _build_user_context() 构建用户动态上下文（身体数据、打卡天数、活跃计划）
  → agent.astream_events(input_msg, config, version="v2")
    → IntentMiddleware.before_model() 检测意图，注入意图提示词
    → LLM 调用（流式输出 token + thinking + tool_calls）
    → Tool 执行（同名进程直调 Service）
    → TokenUsageMiddleware.after_model() 累积 token 用量
    → MemoryUpdateMiddleware.after_model() 触发记忆提取
    → 循环（LLM → Tool → LLM ...）
    → SummarizationMiddleware 在 token 超量时压缩对话
  → _save_message() 持久化用户/助手消息
  → upsert ThreadUsage 累积 token 用量
```

## 关键配置常量

| 常量 | 默认值 | 用途 |
|------|--------|------|
| 对话压缩触发阈值 | 100,000 tokens | SummarizationMiddleware 触发压缩 |
| 记忆提取触发阈值 | 20,000 tokens | MemoryUpdateMiddleware 触发记忆提取 |
| 压缩后保留消息数 | 10 条 | 压缩后保留的最近消息数量 |
| LLM 调用上限 | 15 次/轮 | ModelCallLimitMiddleware 拦截 |
| 工具调用上限 | 10 次/轮 | ToolCallLimitMiddleware 拦截 |
| 同一工具上限 | 5 次/轮 | SameToolLimitMiddleware 返回错误 |
