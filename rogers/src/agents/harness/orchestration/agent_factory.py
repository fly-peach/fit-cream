"""
FitCream Agent Factory

构建 React Agent（基于 LangChain create_agent + Middleware）。

架构设计：
- 使用 langchain.agents.create_agent 创建 ReAct 模式的 Agent
- 模型层使用 ChatDashScope（兼容 OpenAI 协议的通义千问）
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

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from src.agents.harness.orchestration.model_factory import create_chat_dashscope, ChatDashScope
from src.agents.harness.orchestration.prompts.system import SYSTEM_PROMPT, build_system_prompt


def get_default_model(
    model: Optional[str] = None,
    temperature: float = 0.7,
    streaming: bool = True,
    enable_thinking: bool = True,
) -> ChatDashScope:
    """
    获取默认的 LLM 模型实例。

    Args:
        model: 模型名称，默认使用 mdoel_factory 中的 DEFAULT_MODEL
        temperature: 温度参数
        streaming: 是否启用流式输出（SSE 需要）
        enable_thinking: 是否启用思考模式

    Returns:
        ChatDashScope 实例
    """
    kwargs = {}
    if model:
        kwargs["model"] = model

    return create_chat_dashscope(
        temperature=temperature,
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
        model: LLM 模型实例。默认使用 ChatDashScope (qwen3.5-flash)
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
    # 1. 模型（默认使用 ChatDashScope + qwen3.5-flash，开启思考模式）
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
        from src.agents.harness.skills.skills_loader import get_catalog_prompt

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
# （checkpointer 跨 run 累积，非单次 run）。qwen3.5-flash 上下文窗口 ~128K，
# 在 100K 时压缩以防溢出。注意：这是"防上下文溢出"的会话压缩，与
# MemoryUpdateMiddleware（100K 触发的记忆提取/整合）是独立子系统。
SUMMARIZE_TRIGGER_TOKENS = 100_000

# 触发记忆更新的 token 阈值（每 100K token 触发一次记忆提取）
MEMORY_UPDATE_TRIGGER_TOKENS = 100_000

# 压缩后保留的最近消息数（保留足够上下文让对话连贯）
SUMMARIZE_KEEP_MESSAGES = 10


def _get_default_middleware(include_hitl: bool = False) -> list:
    """
    获取默认中间件列表（共享 graph 默认版本）。

    包含：意图识别、技能占位、日志、限流、Token 追踪、会话压缩、记忆更新。
    不含对话持久化（仍由 per-user 的 create_agent_with_middleware 提供）。

    Args:
        include_hitl: 是否启用 HumanInTheLoopMiddleware。仅在存在 checkpointer
            （生产 graph）时启用——中断状态依赖 checkpoint 持久化，dev_graph /
            graph（无 checkpointer）下应保持 False，副作用工具自动放行。

    记忆更新中间件以共享实例接入，user_id 在运行时从
    RunnableConfig.configurable 解析（chat.py 已传 user_id/thread_id），
    以 user_id 为键防重入，并发用户互不干扰。

    中间件顺序（before_model 执行顺序）：
    1. IntentMiddleware：检测用户意图，注入专项提示词（渐进式披露）
    2. SkillsMiddleware：纯占位（catalog 已烘焙进 system_prompt）
    3. HumanInTheLoopMiddleware（可选）：对副作用工具中断等待审批
    4. AgentLoggingMiddleware：记录 LLM/Tool 调用日志
    5. RateLimit：限流（ModelCallLimit / ToolCallLimit / SameToolLimit）
    6. TokenUsageMiddleware：Token 用量追踪
    7. SummarizationMiddleware：会话压缩
    8. MemoryUpdateMiddleware：分层记忆自动提取（每 100K token / 对话结束触发）

    会话压缩策略：
    - 当对话 token 数超过 SUMMARIZE_TRIGGER_TOKENS 时触发
    - 使用 LLM 将历史消息压缩为摘要
    - 保留最近 SUMMARIZE_KEEP_MESSAGES 条消息

    记忆更新策略：
    - 累计 token 超过 MEMORY_UPDATE_TRIGGER_TOKENS 时触发
    - 对话结束（after_agent）兜底触发一次
    - 异步提取分层记忆（情景/语义/程序性），不阻塞对话
    """
    from langchain.agents.middleware import SummarizationMiddleware
    from src.agents.harness.runtime.middleware.logging_middleware import AgentLoggingMiddleware
    from src.agents.harness.runtime.middleware.rate_limit import create_rate_limit_middleware
    from src.agents.harness.runtime.middleware.callbacks import TokenUsageMiddleware
    from src.agents.harness.runtime.middleware.intent_middleware import IntentMiddleware
    from src.agents.harness.runtime.middleware.memory_update import MemoryUpdateMiddleware
    from src.agents.harness.runtime.middleware.skills_middleware import SkillsMiddleware

    # 用于压缩摘要的模型（使用同一模型，低温度确保摘要稳定）
    summary_model = create_chat_dashscope(
        temperature=0.3,
        streaming=False,
        enable_thinking=False,
    )

    middleware = [
        IntentMiddleware(),
        SkillsMiddleware(),
    ]

    # HITL：仅在有 checkpointer 时启用。对副作用工具（创建/调整计划）中断等待用户审批。
    if include_hitl:
        from langchain.agents.middleware import HumanInTheLoopMiddleware

        middleware.append(
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "create_plan_tool": {"allowed_decisions": ["approve", "reject"]},
                    "create_diet_plan_tool": {"allowed_decisions": ["approve", "reject"]},
                    "adjust_plan_tool": {"allowed_decisions": ["approve", "reject"]},
                },
                description_prefix="即将执行计划操作，需要你确认",
            )
        )

    middleware.extend([
        AgentLoggingMiddleware(),
        *create_rate_limit_middleware(),
        TokenUsageMiddleware(max_tokens_per_conversation=SUMMARIZE_TRIGGER_TOKENS),
        SummarizationMiddleware(
            model=summary_model,
            trigger=("tokens", SUMMARIZE_TRIGGER_TOKENS),
            keep=("messages", SUMMARIZE_KEEP_MESSAGES),
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
            adjust_plan_tool,
            list_plans_tool,
            checkin_tool,
            get_streak_tool,
            query_stats_tool,
            get_exercises_tool,
            get_user_profile_tool,
            update_user_profile_tool,
            record_meal_tool,
            query_diet_summary_tool,
            manage_meal_tool,
            set_nutrition_goals_tool,
        )

        tools.extend([
            create_plan_tool,
            create_diet_plan_tool,
            adjust_plan_tool,
            list_plans_tool,
            checkin_tool,
            get_streak_tool,
            query_stats_tool,
            get_exercises_tool,
            get_user_profile_tool,
            update_user_profile_tool,
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
            read_kb_document,
            search_knowledge_base,
        )

        tools.extend([search_knowledge_base, read_kb_document])
    except ImportError:
        pass

    # 4. Skill 加载工具 + 用户画像摘要工具 + 计划提案展示工具
    try:
        from src.agents.harness.tools.skill.skill_load_tool import skill_load_tool
        from src.agents.harness.tools.user.summary_tools import get_user_summary_tool
        from src.agents.harness.tools.plan.present_plan_tool import present_plan_tool

        tools.extend([skill_load_tool, get_user_summary_tool, present_plan_tool])
    except ImportError:
        pass

    return tools
