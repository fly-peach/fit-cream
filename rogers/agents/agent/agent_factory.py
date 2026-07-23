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
    from agents.agent.agent_factory import create_fitcream_agent

    agent = create_fitcream_agent()
    # 或在 FastAPI lifespan 中：
    agent = await create_fitcream_agent(with_checkpointer=True)
"""

from typing import Optional, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph

from agents.agent.model_factory import create_chat_dashscope, ChatDashScope
from agents.harness.prompts.system import SYSTEM_PROMPT, build_system_prompt


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
    # 1. 模型
    if model is None:
        model = get_default_model(
            streaming=True,
            enable_thinking=enable_thinking,
        )

    # 2. 工具
    if tools is None:
        tools = _get_default_tools()

    # 3. 系统提示词
    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT

    # 4. 中间件
    if middleware is None:
        middleware = _get_default_middleware()

    # 5. 构建 ReAct Agent（middleware 编译时注入）
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


def _get_default_middleware() -> list:
    """
    获取默认中间件列表（无用户上下文版本）。

    包含：日志、限流、Token 追踪。
    不含对话持久化（需要 user_id/thread_id）。
    """
    from agents.harness.middleware.logging_middleware import AgentLoggingMiddleware
    from agents.harness.middleware.rate_limit import create_rate_limit_middleware
    from agents.harness.middleware.callbacks import TokenUsageMiddleware

    return [
        AgentLoggingMiddleware(),
        *create_rate_limit_middleware(),
        TokenUsageMiddleware(),
    ]


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
        from agents.harness.tools import (
            create_plan_tool,
            adjust_plan_tool,
            checkin_tool,
            query_stats_tool,
            get_exercises_tool,
            get_user_profile_tool,
        )

        tools.extend([
            create_plan_tool,
            adjust_plan_tool,
            checkin_tool,
            query_stats_tool,
            get_exercises_tool,
            get_user_profile_tool,
        ])
    except ImportError:
        pass

    # 2. 记忆工具（分层认知记忆架构）
    try:
        from agents.memory.tools import create_memory_tools

        memory_tools = create_memory_tools()
        tools.extend(memory_tools)
    except ImportError:
        pass

    return tools
