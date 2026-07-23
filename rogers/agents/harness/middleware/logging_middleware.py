"""
Agent 日志中间件

使用 LangChain AgentMiddleware hooks 记录：
- LLM 调用开始/结束
- Tool 调用开始/结束
- 错误和异常
- Token 使用量
"""

import logging
import time
from typing import Any, Callable, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command

# 异步 handler 类型
AsyncToolHandler = Callable[[ToolCallRequest], Any]  # Awaitable[ToolMessage | Command]

logger = logging.getLogger("fitcream.agent")


class AgentLoggingMiddleware(AgentMiddleware):
    """
    Agent 日志中间件

    通过 before_model / after_model / wrap_tool_call hooks
    记录所有 LLM 和 Tool 调用的详细日志。
    """

    def __init__(
        self,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        verbose: bool = False,
    ):
        super().__init__()
        self.user_id = user_id
        self.thread_id = thread_id
        self.verbose = verbose
        self._llm_calls: int = 0
        self._tool_calls: int = 0
        self._total_tokens: int = 0
        self._start_time: float = 0.0

    def _log_prefix(self) -> str:
        parts = ["[Agent]"]
        if self.user_id:
            parts.append(f"user={self.user_id[:8]}")
        if self.thread_id:
            parts.append(f"thread={self.thread_id[:8]}")
        return " ".join(parts)

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        self._start_time = time.time()
        self._llm_calls = 0
        self._tool_calls = 0
        self._total_tokens = 0
        logger.info(f"{self._log_prefix()} Agent started")
        return None

    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        self._llm_calls += 1
        msg_count = len(state.get("messages", []))
        logger.info(
            f"{self._log_prefix()} LLM call #{self._llm_calls} | messages={msg_count}"
        )
        if self.verbose and state.get("messages"):
            last_msg = state["messages"][-1]
            content_preview = str(getattr(last_msg, "content", ""))[:100]
            logger.debug(f"  last_message: {content_preview}...")
        return None

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            content_preview = str(getattr(last, "content", ""))[:100]
            usage = getattr(last, "usage_metadata", None) or {}
            tokens = usage.get("total_tokens", "N/A")
            logger.info(
                f"{self._log_prefix()} LLM responded | "
                f"tokens={tokens} | response='{content_preview}...'"
            )
        return None

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        self._tool_calls += 1
        tool_name = request.tool_call["name"]
        args_preview = str(request.tool_call.get("args", {}))[:200]

        logger.info(
            f"{self._log_prefix()} Tool started | tool={tool_name} | args='{args_preview}'"
        )

        start = time.time()
        try:
            result = handler(request)
            duration = (time.time() - start) * 1000
            output_preview = str(getattr(result, "content", result))[:200]
            logger.info(
                f"{self._log_prefix()} Tool ended ✓ | "
                f"tool={tool_name} | duration={duration:.1f}ms | "
                f"output='{output_preview}...'"
            )
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(
                f"{self._log_prefix()} Tool error ✗ | "
                f"tool={tool_name} | duration={duration:.1f}ms | "
                f"error={type(e).__name__}: {str(e)[:200]}"
            )
            raise

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: AsyncToolHandler,
    ) -> ToolMessage | Command:
        self._tool_calls += 1
        tool_name = request.tool_call["name"]
        args_preview = str(request.tool_call.get("args", {}))[:200]

        logger.info(
            f"{self._log_prefix()} Tool started | tool={tool_name} | args='{args_preview}'"
        )

        start = time.time()
        try:
            result = await handler(request)
            duration = (time.time() - start) * 1000
            output_preview = str(getattr(result, "content", result))[:200]
            logger.info(
                f"{self._log_prefix()} Tool ended ✓ | "
                f"tool={tool_name} | duration={duration:.1f}ms | "
                f"output='{output_preview}...'"
            )
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(
                f"{self._log_prefix()} Tool error ✗ | "
                f"tool={tool_name} | duration={duration:.1f}ms | "
                f"error={type(e).__name__}: {str(e)[:200]}"
            )
            raise

    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        duration = (time.time() - self._start_time) * 1000
        logger.info(
            f"{self._log_prefix()} Agent ended | "
            f"duration={duration:.1f}ms | "
            f"llm_calls={self._llm_calls} | "
            f"tool_calls={self._tool_calls}"
        )
        return None

    def get_summary(self) -> dict[str, Any]:
        return {
            "llm_calls": self._llm_calls,
            "tool_calls": self._tool_calls,
            "total_tokens": self._total_tokens,
        }
