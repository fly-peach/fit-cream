"""
Agent 回调中间件

- TokenUsageMiddleware: 追踪 Token 使用量
- ConversationPersistenceMiddleware: 将对话消息持久化到 Conversation 表
- create_agent_middleware: 工厂函数，创建所有中间件

每轮计数/待存消息存入 AgentState（UntrackedValue，随 run 重置），
而非实例属性--避免共享 graph 下并发请求互相覆盖（根因 R2）。
"""

import asyncio
import logging
from typing import Annotated, Any, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import PrivateStateAttr
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

logger = logging.getLogger("fitcream.agent")

# 持有 fire-and-forget 持久化任务引用，防止被 GC 回收
_persistence_tasks: set = set()


class TokenUsageState(AgentState):
    """TokenUsageMiddleware 的每轮状态（不持久化到 checkpoint）。"""

    token_prompt: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    token_completion: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    token_total: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    token_llm_calls: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]


class TokenUsageMiddleware(AgentMiddleware):
    """
    Token 使用量追踪中间件

    通过 after_model hook 追踪每次 LLM 调用的 Token 消耗。
    计数存入 AgentState，随每次 run 重置（UntrackedValue），并发安全。
    """

    state_schema = TokenUsageState  # type: ignore[assignment]

    def __init__(
        self,
        max_tokens_per_conversation: int = 50000,
        user_id: Optional[str] = None,
    ):
        super().__init__()
        self.max_tokens = max_tokens_per_conversation
        self.user_id = user_id

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        # 计数由 UntrackedValue 保证随 run 重置，此处仅日志
        logger.info(
            f"[TokenTracker] Started | max_tokens={self.max_tokens} | user={self.user_id}"
        )
        return None

    def after_model(self, state: TokenUsageState, runtime: Runtime) -> dict[str, Any] | None:
        # 从最近一条 AI 消息的 usage_metadata 中累积 token 用量
        usage: dict = {}
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            usage = getattr(last, "usage_metadata", None) or {}

        prompt = usage.get("input_tokens", 0)
        completion = usage.get("output_tokens", 0)
        total = usage.get("total_tokens", 0)

        llm_calls = state.get("token_llm_calls", 0) + 1
        new_prompt = state.get("token_prompt", 0) + prompt
        new_completion = state.get("token_completion", 0) + completion
        new_total = state.get("token_total", 0) + total

        pct = round(new_total / self.max_tokens * 100, 1) if self.max_tokens > 0 else 0
        logger.info(
            f"[TokenTracker] LLM #{llm_calls} tokens | "
            f"input={prompt} output={completion} "
            f"total={new_total}/{self.max_tokens} ({pct}%)"
        )

        # 超限时记录警告（不中断，由 SummarizationMiddleware 处理压缩）
        if new_total > self.max_tokens:
            logger.warning(
                f"[TokenTracker] Token limit exceeded: "
                f"{new_total}/{self.max_tokens} | user={self.user_id}"
            )

        return {
            "token_prompt": new_prompt,
            "token_completion": new_completion,
            "token_total": new_total,
            "token_llm_calls": llm_calls,
        }


class ConversationPersistenceState(AgentState):
    """ConversationPersistenceMiddleware 的每轮状态（不持久化到 checkpoint）。"""

    persistence_pending: NotRequired[Annotated[list[dict], UntrackedValue, PrivateStateAttr]]
    persistence_tool_calls: NotRequired[Annotated[list[str], UntrackedValue, PrivateStateAttr]]


class ConversationPersistenceMiddleware(AgentMiddleware):
    """
    对话持久化中间件

    通过 before_agent / after_agent hooks 捕获用户输入和 AI 回复，
    在 Agent 执行结束后批量保存到 Conversation 表。

    待存消息与 tool 调用记录存入 AgentState，避免实例属性在并发下跨用户混存。
    """

    state_schema = ConversationPersistenceState  # type: ignore[assignment]

    def __init__(
        self,
        user_id: str,
        thread_id: str,
        save_tool_calls: bool = True,
    ):
        super().__init__()
        self.user_id = user_id
        self.thread_id = thread_id
        self.save_tool_calls = save_tool_calls

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        logger.info(
            f"[Persistence] Started | user={self.user_id[:8]} | thread={self.thread_id[:8]} | "
            f"save_tool_calls={self.save_tool_calls}"
        )

        pending: list[dict[str, Any]] = []
        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if getattr(last_msg, "type", "") == "human":
                pending.append({
                    "role": "user",
                    "content": str(getattr(last_msg, "content", "")),
                })
        return {"persistence_pending": pending, "persistence_tool_calls": []}

    def after_model(
        self, state: ConversationPersistenceState, runtime: Runtime
    ) -> dict[str, Any] | None:
        # 累计本轮 tool 调用名称（从最新 AIMessage 的 tool_calls 读取，无需实例属性）
        if not self.save_tool_calls:
            return None
        messages = state.get("messages", [])
        if not messages:
            return None
        last = messages[-1]
        tool_calls = getattr(last, "tool_calls", None) or []
        if not tool_calls:
            return None
        names = [tc["name"] for tc in tool_calls if tc.get("name")]
        if not names:
            return None
        accumulated = list(state.get("persistence_tool_calls", [])) + names
        for name in names:
            logger.info(f"[Persistence] Tracking tool call | tool={name}")
        return {"persistence_tool_calls": accumulated}

    def after_agent(
        self, state: ConversationPersistenceState, runtime: Runtime
    ) -> dict[str, Any] | None:
        pending = list(state.get("persistence_pending", []))
        tool_calls = list(state.get("persistence_tool_calls", []))

        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            if getattr(last, "type", "") == "ai":
                content = str(getattr(last, "content", ""))
                if content:
                    pending.append({
                        "role": "assistant",
                        "content": content,
                        "metadata": {"tool_calls": tool_calls} if tool_calls else None,
                    })

        logger.info(
            f"[Persistence] Agent ended | pending={len(pending)} | "
            f"tool_calls_tracked={len(tool_calls)}"
        )

        if pending:
            # 异步保存（fire-and-forget）：持有 task 引用防 GC，done_callback 清理
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(self._save_messages(pending))
                _persistence_tasks.add(task)
                task.add_done_callback(_persistence_tasks.discard)
            except RuntimeError:
                # agent 始终在事件循环内执行，正常不会走到这里；
                # 不再使用 asyncio.run（会抛 RuntimeError），仅记录告警
                logger.warning("[Persistence] No running event loop; skipping async save")
        return None

    async def _save_messages(self, messages: list[dict[str, Any]]) -> None:
        try:
            from app.database import async_session_factory
            from src.agents.harness.runtime.conversation_service import ConversationService

            async with async_session_factory() as db:
                saved = await ConversationService.save_messages(
                    db, self.user_id, self.thread_id, messages
                )
                logger.info(
                    f"[Persistence] Saved {saved} messages | "
                    f"user={self.user_id[:8]} | thread={self.thread_id[:8]}"
                )

        except Exception as e:
            logger.error(f"[Persistence] Failed to save messages: {e}")


def create_agent_middleware(
    user_id: str,
    thread_id: str,
    verbose: bool = False,
    max_tool_calls: int = 10,
    max_llm_calls: int = 15,
    max_tokens: int = 100_000,
    save_conversation: bool = True,
    enable_summarization: bool = True,
    enable_memory_update: bool = True,
    memory_trigger_tokens: int = 100_000,
) -> list:
    """
    创建 Agent 中间件列表（编译时注入）。

    Args:
        user_id: 用户 ID
        thread_id: 对话线程 ID
        verbose: 是否输出详细日志
        max_tool_calls: 最大 Tool 调用次数
        max_llm_calls: 最大 LLM 调用次数
        max_tokens: 最大 Token 使用量（同时也是 Summarization 触发阈值，默认 100K）
        save_conversation: 是否保存对话到数据库
        enable_summarization: 是否启用会话压缩（默认 True）
        enable_memory_update: 是否启用记忆自动更新（默认 True）
        memory_trigger_tokens: 记忆更新触发的 token 阈值（默认 100K）

    Returns:
        中间件列表，传给 create_agent(middleware=[...])

    中间件执行顺序：
    1. Logging -> 2. RateLimit -> 3. TokenTracking -> 4. MemoryUpdate
    -> 5. Summarization -> 6. Persistence

    会话压缩策略：
    - 当对话 token 数超过 max_tokens (默认 100K) 时触发
    - 使用 LLM 将历史消息压缩为结构化摘要
    - 保留最近 10 条消息确保对话连贯性

    记忆更新策略：
    - 当累计 token 超过 memory_trigger_tokens (默认 100K) 时触发
    - 异步提取分层记忆（情景/语义/程序性）
    - 不阻塞主对话流
    """
    from langchain.agents.middleware import SummarizationMiddleware
    from src.agents.harness.runtime.middleware.logging_middleware import AgentLoggingMiddleware
    from src.agents.harness.runtime.middleware.rate_limit import create_rate_limit_middleware
    from src.agents.harness.runtime.middleware.memory_update import MemoryUpdateMiddleware

    middleware: list = [
        # 1. 日志：记录 LLM / Tool 调用详情
        AgentLoggingMiddleware(
            user_id=user_id,
            thread_id=thread_id,
            verbose=verbose,
        ),
        # 2. 限流：三层策略防止 Agent 陷入循环
        *create_rate_limit_middleware(
            max_tool_calls=max_tool_calls,
            max_llm_calls=max_llm_calls,
        ),
        # 3. Token 追踪：累积用量，超限告警
        TokenUsageMiddleware(
            max_tokens_per_conversation=max_tokens,
            user_id=user_id,
        ),
    ]

    # 4. 记忆更新：token 达到阈值时自动提取分层记忆（异步，不阻塞对话）
    if enable_memory_update:
        middleware.append(
            MemoryUpdateMiddleware(
                user_id=user_id,
                thread_id=thread_id,
                trigger_tokens=memory_trigger_tokens,
            )
        )

    # 5. 会话压缩：token 超限时自动摘要压缩历史消息
    if enable_summarization:
        from src.agents.harness.orchestration.model_factory import create_chat_dashscope

        summary_model = create_chat_dashscope(
            temperature=0.3,
            streaming=False,
            enable_thinking=False,
        )
        middleware.append(
            SummarizationMiddleware(
                model=summary_model,
                trigger=("tokens", max_tokens),
                keep=("messages", 10),
            )
        )

    # 6. 对话持久化：将用户输入和 AI 回复保存到 Conversation 表
    if save_conversation:
        middleware.append(
            ConversationPersistenceMiddleware(
                user_id=user_id,
                thread_id=thread_id,
            )
        )

    return middleware
