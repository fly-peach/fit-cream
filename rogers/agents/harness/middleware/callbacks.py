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
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_tokens = 0
        self._llm_calls = 0
        return None

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        self._llm_calls += 1
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            usage = getattr(last, "usage_metadata", None) or {}
            self._prompt_tokens += usage.get("input_tokens", 0)
            self._completion_tokens += usage.get("output_tokens", 0)
            self._total_tokens += usage.get("total_tokens", 0)

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
            self._tool_calls.append(request.tool_call["name"])
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: AsyncToolHandler,
    ) -> ToolMessage | Command:
        if self.save_tool_calls:
            self._tool_calls.append(request.tool_call["name"])
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

        if self._pending_messages:
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
            from app.models.conversation import Conversation

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
    max_tokens: int = 50000,
    save_conversation: bool = True,
) -> list:
    """
    创建 Agent 中间件列表（编译时注入）。

    Args:
        user_id: 用户 ID
        thread_id: 对话线程 ID
        verbose: 是否输出详细日志
        max_tool_calls: 最大 Tool 调用次数
        max_llm_calls: 最大 LLM 调用次数
        max_tokens: 最大 Token 使用量
        save_conversation: 是否保存对话到数据库

    Returns:
        中间件列表，传给 create_agent(middleware=[...])
    """
    from agents.harness.middleware.logging_middleware import AgentLoggingMiddleware
    from agents.harness.middleware.rate_limit import create_rate_limit_middleware

    middleware: list = [
        AgentLoggingMiddleware(
            user_id=user_id,
            thread_id=thread_id,
            verbose=verbose,
        ),
        *create_rate_limit_middleware(
            max_tool_calls=max_tool_calls,
            max_llm_calls=max_llm_calls,
        ),
        TokenUsageMiddleware(
            max_tokens_per_conversation=max_tokens,
            user_id=user_id,
        ),
    ]

    if save_conversation:
        middleware.append(
            ConversationPersistenceMiddleware(
                user_id=user_id,
                thread_id=thread_id,
            )
        )

    return middleware
