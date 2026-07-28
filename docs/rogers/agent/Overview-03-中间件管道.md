# 中间件管道

中间件在 `create_fitcream_agent()` 编译时注入 LangGraph Graph，以下是按执行顺序排列的完整中间件管道。

## 执行顺序

| 序号 | 中间件 | 作用域 | 核心功能 |
|------|--------|--------|----------|
| 1 | IntentMiddleware | before_model | 检测用户意图，注入意图专用提示词 |
| 2 | AgentLoggingMiddleware | 全生命周期 | 记录 Agent / LLM / Tool 调用日志 |
| 3 | ModelCallLimitMiddleware | before_model | LLM 调用次数限制（默认 15 次/轮） |
| 4 | ToolCallLimitMiddleware | wrap_tool_call | 工具调用次数限制（默认 10 次/轮） |
| 5 | SameToolLimitMiddleware | wrap_tool_call | 同一工具重复调用限制（默认 5 次） |
| 6 | TokenUsageMiddleware | after_model | 追踪 Token 用量，超限警告 |
| 7 | MemoryUpdateMiddleware | after_model | 达到阈值时触发记忆提取 |
| 8 | SummarizationMiddleware | after_model | Token 超量时压缩对话历史 |
| 9 | ConversationPersistenceMiddleware | after_agent | 异步持久化对话消息到数据库 |

## 各中间件详情

### IntentMiddleware

意图检测中间件。在每次 LLM 调用前检测用户输入意图，注入对应意图的 `SystemMessage`。

检测逻辑：
1. 检查最后一条消息是否为 HumanMessage（跳过 ToolMessage/AIMessage 场景）
2. 多模态消息（包含 `image_url`）→ 返回 `image_analysis` 意图
3. 关键词匹配 → 返回匹配的意图
4. 无匹配 → 返回 `general_chat`

| 意图 | 触发关键词 | 行为 |
|------|-----------|------|
| plan_creation | 计划、制定、创建、调整、减脂计划、增肌计划 | 注入计划创建指南 |
| checkin | 打卡、训练了、今天练了、练了 | 注入打卡引导 |
| stats_analysis | 统计、数据、进度、趋势、分析 | 注入数据分析方法 |
| exercise_query | 动作、推荐动作、怎么练、正确姿势 | 注入动作推荐逻辑 |
| image_analysis | （多模态消息自动检测） | 注入图片分析要求 |
| memory_operation | 记得、上次、之前、偏好、习惯 | 注入记忆检索引导 |
| profile_update | 更新、修改、身高、体重、目标 | 注入信息更新步骤 |
| knowledge_query | 什么是、原理、为什么、知识、解释 | 注入知识库搜索要求 |
| general_chat | （默认 fallback） | 注入通用对话指南 |

### AgentLoggingMiddleware

全生命周期日志中间件。记录以下关键节点：

| 钩子 | 记录内容 |
|------|----------|
| before_agent | Agent 启动、user_id、thread_id |
| before_model | LLM 调用次数、输入消息数量 |
| after_model | 响应摘要、累积 Token 用量 |
| wrap_tool_call | 工具名称、输入参数、执行耗时、输出预览 |
| after_agent | 总耗时、LLM 调用次数、Tool 调用次数、总 Token |

日志级别为 INFO，Logger 名称为 `fitcream.agent`。

### RateLimit 三层限流

三层递进式限流策略：

1. **ModelCallLimitMiddleware**: LLM 调用次数上限，触发后结束本轮对话
2. **ToolCallLimitMiddleware**: 工具调用总次数上限，触发后不再执行新工具但允许 LLM 继续
3. **SameToolLimitMiddleware**: 同一工具的重复调用上限，触发后返回错误状态 ToolMessage，提示 LLM 更换方案

SameToolLimitMiddleware 内部维护每次运行的 `_tool_history` 字典，按工具名累加调用次数。

### TokenUsageMiddleware

Token 用量追踪中间件。无状态，每次 after_model 钩子中从最后一条 AI 消息的 `usage_metadata` 中累加：

| 计数器 | 来源字段 |
|--------|----------|
| prompt_tokens | usage_metadata.input_tokens |
| completion_tokens | usage_metadata.output_tokens |
| total_tokens | usage_metadata.total_tokens |

超限时记录 WARNING 日志，不中断 Agent。Token 限流阈值与 SummarizationMiddleware 的压缩阈值一致（100,000）。

### MemoryUpdateMiddleware

记忆提取触发器。在 after_model 钩子中累积 token 用量，达到阈值（20,000）时异步触发记忆提取：

1. 通过全局 `MemoryPipeline` 实例调用 `process_conversation()`
2. 传入当前用户的所有对话消息
3. 提取结果分类存储到 episodic / semantic / procedural 三张表
4. 内部 `_is_processing` 标记防止并发提取

### SummarizationMiddleware

使用 LangChain 内置中间件，在 token 总量超过 100,000 时触发对话压缩：
- 使用独立的 DashScope 实例（低温 `0.3` + 非流式 + 禁用思考）生成摘要
- 摘要替换旧消息的位置
- 保留最近 10 条原始消息以维持对话连贯性

### ConversationPersistenceMiddleware

对话消息持久化中间件。在 after_agent 钩子中异步将本轮对话消息写入 `conversations` 表：

- 保存机制：`loop.create_task()` 非阻塞写入
- 使用 `app.database.async_session_factory` 创建独立数据库会话
- 记录字段：id (UUID4)、user_id、thread_id、role、content、metadata_json（含 tool_calls 列表）
- 写入失败仅记录错误，不中断主流程
