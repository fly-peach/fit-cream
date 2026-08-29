# 中间件管道

中间件在 `create_fitcream_agent()` 编译时注入 LangGraph Graph，以下是按执行顺序排列的完整中间件管道。

## 核心思想

共享 graph 编译时固化了 model/tools；所有 per-request 差异通过中间件在「请求视图层」做临时变换（`wrap_model_call` 里 `request.override(...)`，不落 checkpoint），生命周期动作走 node-style hook（计数/日志/终结/压缩）。两条铁律贯穿：

- **fail-open**：消费 checkpoint 历史 / 运行时附带数据（tool_calls、usage_metadata）的钩子异常一律降级而非炸请求（`robust.py` 围栏）
- **无实例级可变状态**：并发安全，计数走 `UntrackedValue` 随 run 重置

## 执行顺序

| 序号 | 中间件 | Hook | 核心功能 |
|------|--------|------|----------|
| 1 | RequestGateMiddleware | wrap_model_call | 用户请求门控：意图识别渐进式注入 + plan_design 按钮门控 + 知识库回答开关（关闭时过滤 KB 工具 / 开启时注入 KB 优先提示词） |
| 2 | PlanQueueMiddleware | wrap_model_call | 计划设计队列进度快照注入（仅 plan_design 流程有队列时生效） |
| 3 | ContentValidationMiddleware | wrap_model_call | 大纲/当日设计/提案的确定性校验兜底（复用队列快照） |
| 4 | ContextMessageGateMiddleware | wrap_model_call | 队列入参视图级裁剪（只动 request.messages，不落 checkpoint） |
| 5 | ModelRoutingMiddleware | wrap_model_call | 模型路由（qwen / 用户 DeepSeek key）+ 思考开关（默认不思考，kb/plan_design 开思考） |
| 6 | ModelRetryMiddleware | wrap_model_call | 瞬态异常指数退避重试 |
| 7 | ToolErrorMiddleware | wrap_tool_call | 工具异常转 error ToolMessage 供模型自纠 |
| 8 | HumanInTheLoopMiddleware（可选） | wrap_tool_call | 副作用工具中断等待审批（仅 checkpointer 存在时） |
| 9 | AgentLoggingMiddleware | node + wrap_tool_call | 记录 Agent / LLM / Tool 调用日志 |
| 10 | ModelCallLimit / ToolCallLimit / SameToolLimitMiddleware | node + wrap_tool_call | 三层限流 |
| 11 | TokenUsageMiddleware | after_model | Token 用量追踪（上限按 plan_design 动态 150K/200K） |
| 12 | FitCreamSummarizationMiddleware | before_model | 会话压缩（150K / plan_design 200K）+ 压缩后记忆提炼（D3） |

> 注：对话持久化不在此管道内，由 SSE 流（chat.py `_run_agent_sse`）同步落库到 `conversations` 表。
> Skills 无独立中间件：catalog 在 agent_factory 构建时静态烘焙进 system_prompt（纯占位中间件已删）。

## 共享基类：TransientPromptMiddleware

「按用户最新消息临时注入提示词」一族中间件（RequestGate / PlanQueue / ContentValidation）的 wrap 样板收敛到 `transient_prompt.py` 基类：

- 子类只实现 `_prompt(messages) -> Optional[str]` 纯函数（None = 不注入），可选实现 `_filter_tools(request)`（如 RequestGate 的 KB 工具过滤）
- 基类统一 `wrap_model_call` / `awrap_model_call`（自动 sync/async 桥接 + `@model_hook_fail_open` 围栏 + `merge_system_prompt` 合并，不落 checkpoint）
- 三个子类行为差异收束到各自几十行的纯函数

## 各中间件详情

### RequestGateMiddleware

用户请求门控中间件（合并自 IntentMiddleware + KBGateMiddleware）。基类 wrap 实现中：

1. `_filter_tools`：kb_enabled 关闭时从 request.tools 移除 3 个 KB 工具（模型完全不可见）
2. `_prompt`：检测最新 HumanMessage 的意图（图片检测 + 多意图关键词 + 可选 LLM 兜底），合并所有命中意图的专项提示词 + KB 优先提示词（开启时）

plan_design 门控：完整计划设计流程（plan-execute）只允许「设计计划」按钮进入的会话（configurable.plan_design）触发；普通聊天里用户提及计划设计时，替换为「引导点击按钮」的轻量提示词。

### PlanQueueMiddleware

计划设计待办队列上下文注入中间件（无状态）。`_prompt` 从消息历史扫描 `AIMessage.tool_calls`，取最后一个队列工具调用的快照重建当前进度，渲染成提示词注入，防止多轮对话后失忆或重复设计已完成日。

队列工具调用本身是 AIMessage，故只在用户每轮新消息时刷新一次快照，token 开销可控。

### ContentValidationMiddleware

计划设计流程的确定性兜底（生产实测暴露的失败模式：模型未调用展示工具却把结构化内容写进正文、把用户手打的确认当作已展示）。`_prompt` 按当前阶段与历史生成校验提示：确认类（确认了大纲但从未展示 → 要求先补展示）+ 阶段类（大纲/逐日/路线图/审批阶段的展示工具约束）。

非 plan-design 流程（无队列快照）直接跳过，零开销。队列快照复用 PlanQueueMiddleware 的单次扫描结果（F3）。

### ContextMessageGateMiddleware

模型视图级上下文裁剪：把历史中冗余的完整队列快照入参替换为轻量占位（保留最新一份完整供模型构造下次入参），用 `request.override(messages=...)` 返回。只影响模型请求视图，不落 checkpoint、不改前端契约。裁剪失败 fallback 原消息。

### ModelRoutingMiddleware

按请求切换模型：有用户 DeepSeek key 用 deepseek 视觉模型，否则 qwen；`think = kb_enabled or plan_design`（默认不思考）。**无条件** override（无 key 也按思考开关路由 qwen think/nothink）。401/403 标记负缓存并回退 qwen + 一次性警示；同 run 连续失败断路器短路。

### AgentLoggingMiddleware

全生命周期日志中间件，记录 Agent / LLM / Tool 调用关键节点。每轮计数（LLM/Tool 调用数、开始时间）存 `AgentLoggingState`（UntrackedValue，随 run 重置）。日志级别 INFO，Logger `fitcream.agent`。

### 三层限流

1. **ModelCallLimitMiddleware**（内置）：LLM 调用次数上限（30），触发后结束本轮
2. **ToolCallLimitMiddleware**（内置）：工具调用总次数上限（10），触发后不再执行新工具但允许 LLM 继续
3. **SameToolLimitMiddleware**（自定义）：同一工具重复调用上限（默认 5，展示类工具可覆盖），after_model 计数 + wrap_tool_call 执行前短路返回错误 ToolMessage

### TokenUsageMiddleware

Token 用量追踪中间件（无状态）。after_model 从最后一条 AI 消息的 `usage_metadata` 累加，存入 `TokenUsageState`（UntrackedValue）。上下文上限按 `configurable.plan_design` 动态取 200K/150K（D2），仅日志/告警，压缩由 FitCreamSummarizationMiddleware 处理。

### FitCreamSummarizationMiddleware

会话压缩 + 记忆提炼中间件（内置 SummarizationMiddleware 子类，D1-D9）：

- 触发：真实 `usage_metadata.input_tokens` ≥ 阈值（默认 150K / plan_design 200K），无 usage 回退近似估算
- 摘要：健身域 7 节结构化提示词（用户目标/身体数据/活跃计划/进度/偏好伤病/待办队列/下一步）
- 压缩：RemoveMessage(ALL) + 重注入系统提示词 SystemMessage + 摘要占位 + 保留尾 10 条，清空保留消息陈旧 usage 防 thrash
- 记忆提炼（D3）：摘要生成成功后，用摘要文本后台跑 MemoryPipeline 写回三层（episodic/semantic/procedural）；lifespan shutdown 经 `get_shared_memory_middleware()` 排空后台任务
