"""
Agent 回调中间件

- TokenUsageMiddleware: 追踪 Token 使用量
- ConversationPersistenceMiddleware: 将对话消息持久化到 Conversation 表
- create_agent_middleware: 工厂函数，创建所有中间件
"""

import logging
from typing import Any, Callable, Optional, Awaitable
from uuid import uuid4

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command

AsyncToolHandler = Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]]

logger = logging.getLogger("fitcream.agent")


class TokenUsageMiddleware(AgentMiddleware):
    """
    Token 使用量追踪中间件

    通过 after_model hook 追踪每次 LLM 调用的 Token 消耗。
    """

    def __init__(
        self,
        max_tokens_per_conversation: int = 50000,
        user_id: Optional[str] = None,
    ):
        super().__init__()
        self.max_tokens = max_tokens_per_conversation
        self.user_id = user_id
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0
        self._total_tokens: int = 0
        self._llm_calls: int = 0

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        # 每次对话开始时重置 token 计数器
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_tokens = 0
        self._llm_calls = 0
        logger.info(
            f"[TokenTracker] Started | max_tokens={self.max_tokens} | user={self.user_id}"
        )
        return None

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        # 从最近一条 AI 消息的 usage_metadata 中累积 token 用量
        self._llm_calls += 1
        usage: dict = {}
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            usage = getattr(last, "usage_metadata", None) or {}
            self._prompt_tokens += usage.get("input_tokens", 0)
            self._completion_tokens += usage.get("output_tokens", 0)
            self._total_tokens += usage.get("total_tokens", 0)

        logger.info(
            f"[TokenTracker] LLM #{self._llm_calls} tokens | "
            f"input={usage.get('input_tokens', 0)} output={usage.get('output_tokens', 0)} "
            f"total={self._total_tokens}/{self.max_tokens} "
            f"({round(self._total_tokens / self.max_tokens * 100, 1) if self.max_tokens > 0 else 0}%)"
        )

        # 超限时记录警告（不中断，由 SummarizationMiddleware 处理压缩）
        if self._total_tokens > self.max_tokens:
            logger.warning(
                f"[TokenTracker] Token limit exceeded: "
                f"{self._total_tokens}/{self.max_tokens} | "
                f"user={self.user_id}"
            )
        return None

    def get_usage(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "total_tokens": self._total_tokens,
            "llm_calls": self._llm_calls,
            "max_tokens": self.max_tokens,
            "usage_percent": round(
                self._total_tokens / self.max_tokens * 100, 2
            )
            if self.max_tokens > 0
            else 0,
        }

    def is_limit_exceeded(self) -> bool:
        return self._total_tokens > self.max_tokens


class ConversationPersistenceMiddleware(AgentMiddleware):
    """
    对话持久化中间件

    通过 before_agent / after_agent hooks 捕获用户输入和 AI 回复，
    在 Agent 执行结束后批量保存到 Conversation 表。
    """

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
        self._pending_messages: list[dict[str, Any]] = []
        self._tool_calls: list[str] = []

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        self._pending_messages = []
        self._tool_calls = []

        logger.info(
            f"[Persistence] Started | user={self.user_id[:8]} | thread={self.thread_id[:8]} | "
            f"save_tool_calls={self.save_tool_calls}"
        )

        messages = state.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if getattr(last_msg, "type", "") == "human":
                self._pending_messages.append({
                    "role": "user",
                    "content": str(getattr(last_msg, "content", "")),
                })
        return None

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        if self.save_tool_calls:
            tool_name = request.tool_call["name"]
            self._tool_calls.append(tool_name)
            logger.info(f"[Persistence] Tracking tool call | tool={tool_name}")
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: AsyncToolHandler,
    ) -> ToolMessage | Command:
        if self.save_tool_calls:
            tool_name = request.tool_call["name"]
            self._tool_calls.append(tool_name)
            logger.info(f"[Persistence] Tracking tool call | tool={tool_name}")
        return await handler(request)

    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            if getattr(last, "type", "") == "ai":
                content = str(getattr(last, "content", ""))
                if content:
                    self._pending_messages.append({
                        "role": "assistant",
                        "content": content,
                        "metadata": {"tool_calls": self._tool_calls},
                    })

        logger.info(
            f"[Persistence] Agent ended | pending={len(self._pending_messages)} | "
            f"tool_calls_tracked={len(self._tool_calls)}"
        )

        if self._pending_messages:
            # 异步保存（fire-and-forget）：不阻塞 Agent 返回，避免对话延迟
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._save_messages())
            except RuntimeError:
                asyncio.run(self._save_messages())
        return None

    async def _save_messages(self) -> None:
        try:
            from app.database import async_session_factory
            from src.fitme.models.conversation import Conversation

            async with async_session_factory() as db:
                for msg in self._pending_messages:
                    conversation = Conversation(
                        id=uuid4(),
                        user_id=self.user_id,
                        thread_id=self.thread_id,
                        role=msg["role"],
                        content=msg["content"],
                        metadata_json=msg.get("metadata"),
                    )
                    db.add(conversation)

                await db.commit()
                logger.info(
                    f"[Persistence] Saved {len(self._pending_messages)} messages | "
                    f"user={self.user_id[:8]} | thread={self.thread_id[:8]}"
                )
                self._pending_messages = []
                self._tool_calls = []

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
    memory_trigger_tokens: int = 20_000,
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
        memory_trigger_tokens: 记忆更新触发的 token 阈值（默认 20K）

    Returns:
        中间件列表，传给 create_agent(middleware=[...])

    中间件执行顺序：
    1. Logging → 2. RateLimit → 3. TokenTracking → 4. MemoryUpdate → 5. Summarization → 6. Persistence

    会话压缩策略：
    - 当对话 token 数超过 max_tokens (默认 100K) 时触发
    - 使用 LLM 将历史消息压缩为结构化摘要
    - 保留最近 10 条消息确保对话连贯性

    记忆更新策略：
    - 当累计 token 超过 memory_trigger_tokens (默认 20K) 时触发
    - 异步提取分层记忆（情景/语义/程序性）
    - 不阻塞主对话流
    """
    from langchain.agents.middleware import SummarizationMiddleware
    from src.agents.harness.middleware.logging_middleware import AgentLoggingMiddleware
    from src.agents.harness.middleware.rate_limit import create_rate_limit_middleware
    from src.agents.harness.middleware.memory_update import MemoryUpdateMiddleware

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
        from src.agents.agent.model_factory import create_chat_dashscope

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
