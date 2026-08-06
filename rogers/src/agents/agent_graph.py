"""
FitCream Agent Graph - 主入口

LangGraph Agent 的顶层入口模块。
- 开发模式：langgraph dev 通过 langgraph.json 加载此模块的 graph 变量
- 生产模式：FastAPI 直接 import graph，在 lifespan 中初始化

架构：
    ┌─────────────────────────────────────────────────────────┐
    │              create_agent (middleware)                   │
    │                                                         │
    │  ┌──────────┐    ┌──────────┐    ┌────────────────┐    │
    │  │  LLM     │───▶│  Tools   │───▶│ Output         │    │
    │  │ (Qwen)   │◀───│(Service) │◀───│                │    │
    │  └──────────┘    └──────────┘    └────────────────┘    │
    │       ▲              │                                  │
    │       │         ┌────▼────┐                             │
    │       └─────────│  Loop   │                             │
    │                 └─────────┘                             │
    │                                                         │
    │  Middleware (编译时注入):                                │
    │  - Logging / RateLimit / TokenTracking / Persistence    │
    └─────────────────────────────────────────────────────────┘

用法：
    # 开发调试（LangGraph Studio）
    uv run langgraph dev

    # 生产环境（FastAPI 内嵌）
    from src.agents.agent_graph import graph, init_agent
    await init_agent()  # 在 lifespan 中调用
"""

from typing import Any, Optional

from src.agents.harness.orchestration.agent_factory import create_fitcream_agent
from src.agents.harness.runtime.middleware.dev_auth import _is_dev_env
from src.agents.harness.orchestration.prompts.system import SYSTEM_PROMPT


def create_plan_design_agent(checkpointer=None):
    """构建计划设计专用 Agent（同 tools/skills/middleware/HITL，仅模型不同）。

    模型经 get_plan_design_model() 显式构建（enable_thinking 已按配置决定），
    故 create_fitcream_agent 的 enable_thinking 参数被忽略（仅当 model is None 时才转发）。
    """
    from src.agents.harness.orchestration.model_factory import get_plan_design_model

    plan_model = get_plan_design_model()
    return create_fitcream_agent(
        model=plan_model,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


# ============================================================
# 全局 Agent 实例
# ============================================================

# 默认 Agent（无 checkpointer，用于开发/测试）
# 注意：无 checkpointer 时 _get_default_middleware(include_hitl=False)，
# HumanInTheLoopMiddleware 不启用--副作用工具（create_plan_tool 等）自动放行，
# 不会触发审批中断。HITL 审批流程仅在 init_agent() 构造的带 checkpointer 生产 graph 中可用。
graph = create_fitcream_agent(
    system_prompt=SYSTEM_PROMPT,
    enable_thinking=True,
)

# 计划设计专用 Agent（无 checkpointer，用于开发/测试）
# 与 graph 共享 tools/skills/middleware，仅模型不同（PLAN_DESIGN_MODEL，默认 deepseek-v4-flash）。
# 无 checkpointer 时不启用 HITL（同 graph），生产 HITL 由 init_agent 构造的带 checkpointer 实例提供。
plan_design_graph = create_plan_design_agent()

# Dev Agent（与 graph 配置一致 + 自动注入管理员身份，用于 LangGraph Studio 调试）
def _get_dev_middleware() -> list:
    """获取 dev 中间件：默认中间件 + 管理员自动注入"""
    from src.agents.harness.orchestration.agent_factory import _get_default_middleware
    from src.agents.harness.runtime.middleware.dev_auth import DevAuthMiddleware
    return [DevAuthMiddleware(), *_get_default_middleware()]


# langgraph.json 通过 agent_graph:dev_graph 引用。
# 仅在开发环境（DEBUG 或 LANGGRAPH_DEV）构造，生产环境保持 None，
# 避免无谓的 graph 编译与 DevAuthMiddleware 实例化（DevAuth 内部亦通过环境守卫）。
if _is_dev_env():
    dev_graph = create_fitcream_agent(
        system_prompt=SYSTEM_PROMPT,
        enable_thinking=True,
        middleware=_get_dev_middleware(),
    )
else:
    dev_graph = None

# 带 checkpointer 的 Agent（生产环境，在 init_agent 中初始化）
_graph_with_checkpointer = None
# 计划设计专用 Agent（带 checkpointer，生产环境，在 init_agent 中初始化）
_plan_design_graph_with_checkpointer = None


def _to_psycopg_dsn(url: str) -> str:
    """
    将 SQLAlchemy 异步连接串转换为 psycopg 格式。

    postgresql+asyncpg://user:pass@host:port/db -> postgresql://user:pass@host:port/db
    """
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "")
    return url


# 全局 checkpointer 引用（用于 lifespan shutdown 时关闭连接）
_checkpointer: Any = None
_checkpointer_cm: Any = None  # context manager 引用


async def init_agent(database_url: Optional[str] = None):
    """
    初始化 Agent（在 FastAPI lifespan startup 中调用）。

    创建带 PostgreSQL checkpointer 的 Agent 实例，
    实现对话状态持久化（支持多轮对话记忆）。

    Args:
        database_url: PostgreSQL 连接字符串。
                     默认从 app.config.settings 读取。

    Example:
        # FastAPI main.py
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await init_agent()
            yield
    """
    global _graph_with_checkpointer, graph, _checkpointer, _checkpointer_cm, _plan_design_graph_with_checkpointer

    import logging
    logger = logging.getLogger("fitcream")

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        if database_url is None:
            try:
                from app.config import settings
                database_url = settings.DATABASE_URL
            except ImportError:
                import os
                database_url = os.getenv(
                    "DATABASE_URL",
                    "postgresql+asyncpg://fitcream:fitcream@localhost:5432/fitcream",
                )

        # 转换为 psycopg 格式连接串
        psycopg_dsn = _to_psycopg_dsn(database_url)

        # AsyncPostgresSaver.from_conn_string 返回 async context manager
        # 需要进入上下文获取 checkpointer 实例
        cm = AsyncPostgresSaver.from_conn_string(psycopg_dsn)
        checkpointer = await cm.__aenter__()
        try:
            await checkpointer.setup()

            # 保存引用以便 shutdown 时关闭
            _checkpointer = checkpointer
            _checkpointer_cm = cm  # 保存 context manager 用于退出

            _graph_with_checkpointer = create_fitcream_agent(
                system_prompt=SYSTEM_PROMPT,
                checkpointer=checkpointer,
                enable_thinking=True,
            )

            # 计划设计专用 graph：共享同一 checkpointer（按 thread_id 键），
            # 相同 graph 结构（同 tools/middleware/HITL），仅模型不同，
            # 故 plan_design 线程上的 HITL resume 可安全路由到此 graph。
            _plan_design_graph_with_checkpointer = create_plan_design_agent(checkpointer=checkpointer)

            graph = _graph_with_checkpointer
            logger.info("Agent 初始化完成（对话持久化已启用）")

            # 初始化记忆流水线：注入记忆存储 + LLM 提取器。
            # 失败仅告警，不影响 Agent 启动（记忆提取为 best-effort）。
            try:
                from src.agents.harness.runtime.memory.store import init_memory_store
                from src.agents.harness.runtime.memory.pipeline import init_memory_pipeline
                from src.agents.harness.orchestration.model_factory import create_chat_dashscope

                memory_store = await init_memory_store(database_url)
                extractor_llm = create_chat_dashscope(
                    temperature=0.3,
                    streaming=False,
                    enable_thinking=False,
                )
                init_memory_pipeline(store=memory_store, llm=extractor_llm)
                logger.info("记忆流水线已初始化（extractor 已注入）")
            except Exception as me:
                logger.warning(f"记忆流水线初始化失败（记忆提取将跳过）: {me}")
        except Exception:
            # setup() 或 agent 构造失败：必须退出 context manager，避免连接池泄漏
            await cm.__aexit__(None, None, None)
            raise

    except ImportError as e:
        logger.warning(f"Checkpointer 不可用（{e}），Agent 将不支持对话持久化")
    except Exception as e:
        logger.error(f"Agent 初始化失败: {e}，使用无状态模式")


async def shutdown_agent():
    """
    关闭 Agent（在 FastAPI lifespan shutdown 中调用）。

    释放 checkpointer 的数据库连接。
    """
    global _checkpointer, _checkpointer_cm

    if _checkpointer_cm is not None:
        try:
            await _checkpointer_cm.__aexit__(None, None, None)
        except Exception:
            pass
        _checkpointer_cm = None
        _checkpointer = None

    # 关闭记忆存储引擎（与 checkpointer 对称释放）
    try:
        from src.agents.harness.runtime.memory.store import shutdown_memory_store
        await shutdown_memory_store()
    except Exception:
        pass


def get_agent():
    """
    获取当前 Agent 实例。

    优先返回带 checkpointer 的实例，否则返回默认实例。

    Returns:
        CompiledStateGraph
    """
    if _graph_with_checkpointer is not None:
        return _graph_with_checkpointer
    return graph


def get_agent_by_mode(mode: Optional[str]):
    """按线程 agent_mode 路由到对应 Agent 实例。

    - "plan_design" -> 计划设计专用 graph（优先带 checkpointer 的生产实例）
    - 其余 / None -> 默认 graph（get_agent）

    Args:
        mode: ThreadMeta.agent_mode，缺失（None）时走默认 graph

    Returns:
        CompiledStateGraph
    """
    if mode == "plan_design":
        if _plan_design_graph_with_checkpointer is not None:
            return _plan_design_graph_with_checkpointer
        return plan_design_graph
    return get_agent()


def create_agent_config(
    user_id: str,
    thread_id: Optional[str] = None,
    verbose: bool = False,
    max_tool_calls: int = 10,
    max_llm_calls: int = 15,
    max_tokens: int = 50000,
    save_conversation: bool = True,
) -> dict:
    """
    创建 Agent 运行配置。

    注意：中间件已在 create_agent 编译时注入，
    此函数仅生成 configurable（thread_id / user_id）。

    如需 per-request 中间件（如特定用户的限流策略），
    应使用 create_fitcream_agent(middleware=[...]) 创建专用实例。

    Args:
        user_id: 用户 ID
        thread_id: 对话线程 ID（默认使用 user_id）
        verbose: （保留参数，中间件已编译时注入）
        max_tool_calls: （保留参数）
        max_llm_calls: （保留参数）
        max_tokens: （保留参数）
        save_conversation: （保留参数）

    Returns:
        LangGraph config dict
    """
    if thread_id is None:
        thread_id = user_id

    return {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
        },
    }


def create_agent_with_middleware(
    user_id: str,
    thread_id: Optional[str] = None,
    verbose: bool = False,
    max_tool_calls: int = 10,
    max_llm_calls: int = 15,
    max_tokens: int = 50000,
    save_conversation: bool = True,
    checkpointer=None,
):
    """
    创建带用户级中间件的 Agent 实例。

    当需要 per-user 中间件配置时使用（如特定用户的限流、持久化）。
    中间件在编译时注入，无需运行时 callbacks。

    Args:
        user_id: 用户 ID
        thread_id: 对话线程 ID
        verbose: 是否输出详细日志
        max_tool_calls: 最大 Tool 调用次数
        max_llm_calls: 最大 LLM 调用次数
        max_tokens: 最大 Token 使用量
        save_conversation: 是否保存对话到数据库
        checkpointer: 对话持久化

    Returns:
        CompiledStateGraph
    """
    from src.agents.harness.runtime.middleware import create_agent_middleware

    if thread_id is None:
        thread_id = user_id

    middleware = create_agent_middleware(
        user_id=user_id,
        thread_id=thread_id,
        verbose=verbose,
        max_tool_calls=max_tool_calls,
        max_llm_calls=max_llm_calls,
        max_tokens=max_tokens,
        save_conversation=save_conversation,
    )

    return create_fitcream_agent(
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        enable_thinking=True,
        middleware=middleware,
    )
