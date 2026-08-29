"""
FitCream Agent Factory

构建 React Agent（基于 LangChain create_agent + Middleware）。

架构设计：
- 使用 langchain.agents.create_agent 创建 ReAct 模式的 Agent
- 模型层使用 ChatQwen（DashScope 官方集成），运行时经 ModelRoutingMiddleware
  按请求切换用户自备 DeepSeek key（BYOK）
- Tools 直接调用 Service 层（同进程融合，不走 HTTP）
- Middleware 在编译时注入（日志、限流、Token 追踪、重试）
- 支持 checkpointer 实现对话持久化

用法：
    from src.agents.harness.orchestration.agent_factory import create_fitcream_agent

    agent = create_fitcream_agent()
    # 或在 FastAPI lifespan 中：
    agent = await create_fitcream_agent(with_checkpointer=True)
"""

from typing import Optional, Sequence

from langchain.agents.middleware import ModelRetryMiddleware, ToolErrorMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from src.agents.harness.orchestration.model_factory import create_qwen, resolve_chat_model
from src.agents.harness.orchestration.prompts.system import SYSTEM_PROMPT, build_system_prompt

import logging

logger = logging.getLogger("fitcream.agent")


def get_default_model(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    streaming: bool = True,
    enable_thinking: bool = True,
) -> BaseChatModel:
    """
    获取默认的 LLM 模型实例（qwen3.8-flash，ChatQwen 官方集成）。

    温度不再硬编码覆盖 .env，缺省走 DASHSCOPE_TEMPERATURE（ModelSpec + 配置驱动）。

    Args:
        model: 模型名称，默认使用 model_factory 中的 DEFAULT_MODEL
        temperature: 温度参数，默认从 DASHSCOPE_TEMPERATURE 读取
        streaming: 是否启用流式输出（SSE 需要）
        enable_thinking: 是否启用思考模式

    Returns:
        ChatQwen 实例
    """
    kwargs = {}
    if model:
        kwargs["model"] = model
    if temperature is not None:
        kwargs["temperature"] = temperature

    return create_qwen(
        streaming=streaming,
        enable_thinking=enable_thinking,
        **kwargs,
    )


def create_fitcream_agent(
    model: Optional[BaseChatModel] = None,
    tools: Optional[Sequence[BaseTool]] = None,
    system_prompt: Optional[str] = None,
    checkpointer=None,
    enable_thinking: bool = True,
    middleware: Optional[list] = None,
) -> CompiledStateGraph:
    """
    创建 FitCream React Agent。

    使用 LangChain create_agent 构建 ReAct 模式的 Agent，
    中间件在编译时注入，无需运行时传递 callbacks。

    Args:
        model: LLM 模型实例。默认使用 ChatQwen (qwen3.8-flash)
        tools: 工具列表。默认使用 FitCream 全部工具
        system_prompt: 系统提示词。默认使用 SYSTEM_PROMPT
        checkpointer: 对话持久化 checkpointer（AsyncPostgresSaver 等）
        enable_thinking: 是否启用模型思考模式
        middleware: 中间件列表。默认使用日志+限流+Token追踪

    Returns:
        CompiledStateGraph: 编译后的 LangGraph Agent，可直接 astream_events

    Example:
        # 基础用法
        agent = create_fitcream_agent()

        # 带 checkpointer（生产环境）
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        checkpointer = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
        agent = create_fitcream_agent(checkpointer=checkpointer)

        # 调用
        config = {"configurable": {"thread_id": "user-123"}}
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": "我想减脂"}]},
            config=config,
            version="v2",
        ):
            ...
    """
    # 1. 模型（默认使用 ChatQwen + qwen3.8-flash，开启思考模式）
    if model is None:
        model = get_default_model(
            streaming=True,
            enable_thinking=enable_thinking,
        )

    # 2. 工具（默认加载全部业务工具 + 记忆工具，同进程直接调用 Service 层）
    if tools is None:
        tools = _get_default_tools()

    # 3. 系统提示词（默认使用 system.py 中的完整 SYSTEM_PROMPT + skills catalog）
    if system_prompt is None:
        from src.agents.harness.skills.skills_loader import (
            get_catalog_prompt,
            get_skill_diagnostics,
        )

        for diag in get_skill_diagnostics():
            if diag.get("level") == "error":
                logger.error("[Skills] %s: %s", diag.get("skill"), diag.get("message"))
            else:
                logger.warning("[Skills] %s: %s", diag.get("skill"), diag.get("message"))

        catalog = get_catalog_prompt()
        system_prompt = SYSTEM_PROMPT + (f"\n\n{catalog}" if catalog else "")

    # 4. 中间件（默认：日志 + 限流 + Token追踪 + 会话压缩，编译时注入）
    if middleware is None:
        # HITL 仅在存在 checkpointer 时启用（中断状态需 checkpoint 持久化）；
        # 无 checkpointer 的 dev_graph / graph 会跳过 HITL，副作用工具自动放行。
        middleware = _get_default_middleware(include_hitl=checkpointer is not None)

    # 5. 构建 ReAct Agent（middleware 在编译时注入，运行时无需 callbacks）
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        middleware=middleware,
    )

    return agent


def create_fitcream_agent_with_context(
    user_name: Optional[str] = None,
    user_goal: Optional[str] = None,
    user_stats: Optional[dict] = None,
    model: Optional[BaseChatModel] = None,
    tools: Optional[Sequence[BaseTool]] = None,
    checkpointer=None,
    middleware: Optional[list] = None,
) -> CompiledStateGraph:
    """
    创建带用户上下文的 Agent（动态注入用户信息到 system prompt）。

    适用于每次对话开始时已知用户信息的场景。
    会将用户名、目标、统计数据等注入到系统提示词中。

    Args:
        user_name: 用户名称
        user_goal: 用户健身目标
        user_stats: 用户统计 {"current_streak": 7, "total_workouts": 50}
        model: LLM 模型
        tools: 工具列表
        checkpointer: 对话持久化
        middleware: 中间件列表

    Returns:
        CompiledStateGraph
    """
    dynamic_prompt = build_system_prompt(
        user_name=user_name,
        user_goal=user_goal,
        user_stats=user_stats,
    )

    return create_fitcream_agent(
        model=model,
        tools=tools,
        system_prompt=dynamic_prompt,
        checkpointer=checkpointer,
        middleware=middleware,
    )


# ============================================================
# Summarization 配置常量
# ============================================================

# 触发会话压缩的 token 阈值：检查同一 thread 累积消息的 token 数
# （checkpointer 跨 run 累积，非单次 run）。qwen3.8-flash 上下文窗口 ~128K，
# 在 100K 时压缩以防溢出。注意：这是"防上下文溢出"的会话压缩，与
# MemoryUpdateMiddleware（100K 触发的记忆提取/整合）是独立子系统。
SUMMARIZE_TRIGGER_TOKENS = 100_000

# 触发记忆更新的 token 阈值（每 100K token 触发一次记忆提取）
MEMORY_UPDATE_TRIGGER_TOKENS = 100_000

# 压缩后保留的最近消息数（保留足够上下文让对话连贯）
SUMMARIZE_KEEP_MESSAGES = 10


def _tool_error_message(exc: BaseException, request) -> str:
    """工具异常兜底文案：只透异常类型名，不泄内部细节（模型据 error 状态自纠）。"""
    return (
        f"工具调用失败（{type(exc).__name__}）。"
        "请检查参数后重试，或换一种方式完成该请求。"
    )


def _get_default_middleware(include_hitl: bool = False) -> list:
    """
    获取默认中间件列表（共享 graph 默认版本）。

    包含：意图识别、技能占位、日志、限流、Token 追踪、会话压缩、记忆更新。
    不含对话持久化--对话消息由 SSE 流（chat.py _run_agent_sse）同步落库。

    Args:
        include_hitl: 是否启用 HumanInTheLoopMiddleware。仅在存在 checkpointer
            （生产 graph）时启用——中断状态依赖 checkpoint 持久化，dev_graph /
            graph（无 checkpointer）下应保持 False，副作用工具自动放行。

    记忆更新中间件以共享实例接入，user_id 在运行时从
    RunnableConfig.configurable 解析（chat.py 已传 user_id/thread_id），
    以 user_id 为键防重入，并发用户互不干扰。

    中间件顺序（wrap_model_call 嵌套，先注册者最外层）：
    1. IntentMiddleware：检测用户意图，临时注入专项提示词（渐进式披露，F1）
    2. SkillsMiddleware：纯占位（catalog 已烘焙进 system_prompt）
    3. PlanQueueMiddleware：计划设计队列进度快照临时注入（仅 plan_design 流程有队列时生效）
    4. ContentValidationMiddleware：大纲/当日设计/提案的确定性兜底提示（复用队列快照）
    5. KBGateMiddleware：知识库回答开关（关闭时过滤 KB 工具 / 开启时临时注入 KB 优先提示词）
    6. ContextMessageGateMiddleware：队列入参视图级裁剪（只动 request.messages，
       不影响经 system_message 注入的提示词）
    7. ModelRoutingMiddleware：按请求切换 qwen / 用户 DeepSeek key（401/403 回退）
    8. ModelRetryMiddleware：瞬态异常指数退避重试（retry_on 过滤，认证类不回退重试）
    9. ToolErrorMiddleware：工具异常转 error ToolMessage 供模型自纠
    10. HumanInTheLoopMiddleware（可选）：对副作用工具中断等待审批
    11. AgentLoggingMiddleware：记录 LLM/Tool 调用日志
    12. RateLimit：限流（ModelCallLimit / ToolCallLimit / SameToolLimit）
    13. TokenUsageMiddleware：Token 用量追踪
    14. SummarizationMiddleware：会话压缩
    15. MemoryUpdateMiddleware：分层记忆自动提取（每 100K token / 对话结束触发）

    会话压缩策略：
    - 当对话 token 数超过 SUMMARIZE_TRIGGER_TOKENS 时触发
    - 使用 LLM 将历史消息压缩为摘要
    - 保留最近 SUMMARIZE_KEEP_MESSAGES 条消息

    记忆更新策略：
    - 累计 token 超过 MEMORY_UPDATE_TRIGGER_TOKENS 时触发
    - 对话结束（after_agent）兜底触发一次
    - 异步提取分层记忆（情景/语义/程序性），不阻塞对话
    """
    from src.agents.harness.runtime.middleware.logging_middleware import AgentLoggingMiddleware
    from src.agents.harness.runtime.middleware.rate_limit import create_rate_limit_middleware
    from src.agents.harness.runtime.middleware.callbacks import TokenUsageMiddleware
    from src.agents.harness.runtime.middleware.intent_middleware import IntentMiddleware
    from src.agents.harness.runtime.middleware.memory_update import MemoryUpdateMiddleware
    from src.agents.harness.runtime.middleware.skills_middleware import SkillsMiddleware
    from src.agents.harness.runtime.middleware.plan_queue_middleware import PlanQueueMiddleware
    from src.agents.harness.runtime.middleware.content_validation_middleware import (
        ContentValidationMiddleware,
    )
    from src.agents.harness.runtime.middleware.kb_gate_middleware import KBGateMiddleware
    from src.agents.harness.runtime.middleware.context_message_gate import (
        ContextMessageGateMiddleware,
    )
    from src.agents.harness.runtime.middleware.terminal_tool import (
        TERMINAL_TOOLS,
        TerminalToolMiddleware,
    )
    from src.agents.harness.runtime.middleware.structured_summarization import (
        StructuredSummarizationMiddleware,
    )
    from src.agents.harness.runtime.middleware.model_routing import (
        ModelRoutingMiddleware,
        is_transient_error,
    )

    # 用于压缩摘要的模型（低温度确保摘要稳定，不开启思考）
    summary_model = create_qwen(
        temperature=0.3,
        streaming=False,
        enable_thinking=False,
    )

    # 会话压缩的模型解析器：带用户 DS key 时用 deepseek（决策 Q2：压缩走用户
    # deepseek），无 key 时回退 summary_model（qwen）。模型实例按 key 缓存。
    def resolve_summary_model(*, user_ds_key=None):
        return resolve_chat_model(user_ds_key=user_ds_key)

    middleware = [
        IntentMiddleware(),
        SkillsMiddleware(),
        PlanQueueMiddleware(),
        # AI 信息校验：计划设计流程中，对大纲/当日设计/计划提案做确定性兜底——
        # 确认前必须已调用对应展示工具、结构化内容禁止写成正文（依赖队列快照判定阶段）。
        # 放在 PlanQueue 注入之后，可叠加其快照提示；HITL 之前（不涉及中断）。
        ContentValidationMiddleware(),
        # 知识库回答开关：kb_enabled falsy 时过滤 KB 工具，truthy 时注入 KB 优先提示词；
        # 注册在意图之后（KB 提示词可叠加意图规则），HITL 之前（不涉及中断）
        KBGateMiddleware(),
        # 模型视图级裁剪：把历史中队列工具的完整快照入参替换为轻量占位（仅影响
        # 模型请求，不落 checkpoint / 不改前端契约）。放在 PlanQueue 注入之后、
        # 日志 / 限流之前。
        ContextMessageGateMiddleware(),
        # 模型路由：按请求切换 qwen / 用户自备 DeepSeek key（读 configurable 的
        # deepseek_api_key；401/403 自动回退 qwen + 一次性警示）。
        ModelRoutingMiddleware(),
        # 模型可靠性（P1）：瞬态异常（网络/限流 429/5xx）指数退避重试；401/403 已由
        # ModelRoutingMiddleware 负缓存回退，不在此重试（retry_on=is_transient_error
        # 过滤）。注册在 ModelRouting 之后（wrap 链内层，紧贴模型调用）。重试仅由
        # after_model 计次，不放大 ModelCallLimit 的 run_limit 计数。
        ModelRetryMiddleware(
            max_retries=2,
            retry_on=is_transient_error,
            on_failure="error",
            backoff_factor=2.0,
            initial_delay=0.5,
            jitter=True,
        ),
        # 工具错误兜底（P1）：工具抛异常转 ToolMessage(status="error") 供模型自纠；
        # on_error 只透出异常类型名（不泄内部细节，隐私安全风格）。
        ToolErrorMiddleware(on_error=_tool_error_message),
    ]

    # HITL：仅在有 checkpointer 时启用。对副作用工具（创建/编辑/删除计划）中断等待用户审批。
    if include_hitl:
        from langchain.agents.middleware import HumanInTheLoopMiddleware

        middleware.append(
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "create_plan_tool": {"allowed_decisions": ["approve", "reject"]},
                    "create_diet_plan_tool": {"allowed_decisions": ["approve", "reject"]},
                    "delete_plan_tool": {"allowed_decisions": ["approve", "reject"]},
                    "remove_plan_day_tool": {"allowed_decisions": ["approve", "reject"]},
                    "remove_exercise_tool": {"allowed_decisions": ["approve", "reject"]},
                    "sync_plan_day_tool": {"allowed_decisions": ["approve", "reject"]},
                    "create_roadmap_tool": {"allowed_decisions": ["approve", "reject"]},
                },
                description_prefix="即将执行计划操作，需要你确认",
            )
        )

    middleware.extend([
        AgentLoggingMiddleware(),
        # 展示类工具严格限制（初始建清单 + 大纲后重组各 1 次，共 2 次内），防止模型
        # 反复重 present 同一队列/大纲陷入死循环；其余工具默认 5 次（get_exercises_tool
        # 逐日检索合法需多次，不受影响）。
        # present_form_tool 限 1：每次用户消息（一个 run）只允许发送一个表单，用户
        # 提交（[表单提交: ...]）后再发下一个——配合提示词约束，拦截同轮连续弹多张表单卡。
        *create_rate_limit_middleware(
            tool_limits={
                "present_plan_queue_tool": 2,
                "present_outline_tool": 2,
                "present_form_tool": 1,
                "present_roadmap_tool": 2,
            },
        ),
        TokenUsageMiddleware(max_tokens_per_conversation=SUMMARIZE_TRIGGER_TOKENS),
        # 终结工具：白名单工具批全部成功后结束 run，跳过后续自动 LLM 总结。
        # 默认白名单为空（保守起步），按 3.3 与产品对齐后逐工具灰度启用。
        TerminalToolMiddleware(terminal_tools=TERMINAL_TOOLS, enabled=bool(TERMINAL_TOOLS)),
        # 结构化增量压缩（替换内置 SummarizationMiddleware）：健身域结构化 markdown
        # 摘要 + 跨 run 增量更新（conversation_summary 持久化通道），防上下文溢出。
        StructuredSummarizationMiddleware(
            model=summary_model,
            model_resolver=resolve_summary_model,
            trigger_tokens=SUMMARIZE_TRIGGER_TOKENS,
            keep_messages=SUMMARIZE_KEEP_MESSAGES,
        ),
        # 记忆更新：共享实例，user_id 运行时从 configurable 解析（见 memory_update.py）
        MemoryUpdateMiddleware(trigger_tokens=MEMORY_UPDATE_TRIGGER_TOKENS),
    ])
    return middleware


def _get_default_tools() -> list:
    """
    获取 FitCream 默认工具列表。

    工具直接调用 Service 层函数（同进程融合）。
    当 tools 模块尚未实现时返回空列表，避免导入错误。

    Returns:
        工具列表
    """
    tools = []

    # 1. 业务工具
    try:
        from src.agents.harness.tools import (
            create_plan_tool,
            create_diet_plan_tool,
            list_plans_tool,
            get_plan_detail_tool,
            update_plan_tool,
            delete_plan_tool,
            add_plan_day_tool,
            remove_plan_day_tool,
            sync_plan_day_tool,
            add_exercise_tool,
            update_exercise_tool,
            remove_exercise_tool,
            checkin_tool,
            get_streak_tool,
            query_stats_tool,
            get_exercises_tool,
            get_user_profile_tool,
            update_user_profile_tool,
            update_fitness_profile_tool,
            record_meal_tool,
            query_diet_summary_tool,
            manage_meal_tool,
            set_nutrition_goals_tool,
        )

        tools.extend([
            create_plan_tool,
            create_diet_plan_tool,
            list_plans_tool,
            get_plan_detail_tool,
            update_plan_tool,
            delete_plan_tool,
            add_plan_day_tool,
            remove_plan_day_tool,
            sync_plan_day_tool,
            add_exercise_tool,
            update_exercise_tool,
            remove_exercise_tool,
            checkin_tool,
            get_streak_tool,
            query_stats_tool,
            get_exercises_tool,
            get_user_profile_tool,
            update_user_profile_tool,
            update_fitness_profile_tool,
            record_meal_tool,
            query_diet_summary_tool,
            manage_meal_tool,
            set_nutrition_goals_tool,
        ])
    except ImportError:
        pass

    # 2. 记忆工具（分层认知记忆架构）
    try:
        from src.agents.harness.tools.memory.memory_tools import create_memory_tools

        memory_tools = create_memory_tools()
        tools.extend(memory_tools)
    except ImportError:
        pass

    # 3. 知识库工具
    try:
        from src.agents.harness.tools.knowledge.knowledge_tools import (
            list_my_knowledge_bases,
            read_kb_document,
            search_knowledge_base,
        )

        tools.extend([search_knowledge_base, read_kb_document, list_my_knowledge_bases])
    except ImportError:
        pass

    # 4. Skill 加载工具 + 用户画像摘要工具 + 计划提案展示工具 + 信息采集表单工具 + 计划设计待办队列工具
    try:
        from src.agents.harness.tools.skill.skill_load_tool import skill_load_tool
        from src.agents.harness.tools.user.summary_tools import get_user_summary_tool
        from src.agents.harness.tools.plan.present_plan_tool import present_plan_tool
        from src.agents.harness.tools.plan.present_form_tool import present_form_tool
        from src.agents.harness.tools.plan.plan_queue_tools import (
            present_plan_queue_tool,
            present_outline_tool,
            present_day_design_tool,
            update_plan_queue_item_tool,
        )
        from src.agents.harness.tools.goal.goal_knowledge_tools import (
            get_goal_knowledge_tool,
        )
        from src.agents.harness.tools.goal.roadmap_tools import (
            check_milestone_tool,
            create_roadmap_tool,
            get_roadmap_tool,
            present_roadmap_tool,
            record_baseline_tool,
        )

        tools.extend([
            skill_load_tool,
            get_user_summary_tool,
            present_plan_tool,
            present_form_tool,
            present_plan_queue_tool,
            present_outline_tool,
            present_day_design_tool,
            update_plan_queue_item_tool,
            get_goal_knowledge_tool,
            present_roadmap_tool,
            create_roadmap_tool,
            get_roadmap_tool,
            record_baseline_tool,
            check_milestone_tool,
        ])
    except ImportError:
        pass

    return tools
