"""
Agent 限流中间件

三层限流策略，防止 Agent 陷入无限循环或过度消耗 Token：
1. ModelCallLimitMiddleware: 限制单次对话中 LLM 调用总次数（默认 15 次）
2. ToolCallLimitMiddleware: 限制单次对话中 Tool 调用总次数（默认 10 次）
3. SameToolLimitMiddleware: 限制同一 Tool 的重复调用次数（默认 5 次）

前两者使用 LangChain 内置中间件，后者为自定义实现。
"""

import logging
from typing import Any, Callable, Awaitable

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command

AsyncToolHandler = Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]]

logger = logging.getLogger("fitcream.agent")


class SameToolLimitMiddleware(AgentMiddleware):
    """
    限制同一 Tool 在单次 run 中的重复调用次数。

    内置 ToolCallLimitMiddleware 只支持全局或按 tool_name 的 thread/run 限制，
    此类补充"同一 tool 连续重复调用"的检测。
    """

    def __init__(self, max_same_tool_calls: int = 5):
        super().__init__()
        self.max_same_tool_calls = max_same_tool_calls
        self._tool_history: dict[str, int] = {}

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        logger.info(
            f"[RateLimit] SameToolLimit started | max_same_tool_calls={self.max_same_tool_calls}"
        )
        self._tool_history = {}
        return None

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        tool_name = request.tool_call["name"]
        self._tool_history[tool_name] = self._tool_history.get(tool_name, 0) + 1
        current = self._tool_history[tool_name]

        logger.info(
            f"[RateLimit] Tool call check | tool={tool_name} | "
            f"count={current}/{self.max_same_tool_calls}"
        )

        if current > self.max_same_tool_calls:
            logger.warning(
                f"[RateLimit] Same tool limit exceeded: "
                f"{tool_name} called {current} times "
                f"(max {self.max_same_tool_calls})"
            )
            return ToolMessage(
                content=(
                    f"Error: Tool '{tool_name}' has been called "
                    f"{self.max_same_tool_calls} times already. "
                    f"Please try a different approach."
                ),
                tool_call_id=request.tool_call["id"],
                status="error",
            )

        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: AsyncToolHandler,
    ) -> ToolMessage | Command:
        tool_name = request.tool_call["name"]
        self._tool_history[tool_name] = self._tool_history.get(tool_name, 0) + 1
        current = self._tool_history[tool_name]

        logger.info(
            f"[RateLimit] Tool call check | tool={tool_name} | "
            f"count={current}/{self.max_same_tool_calls}"
        )

        if current > self.max_same_tool_calls:
            logger.warning(
                f"[RateLimit] Same tool limit exceeded: "
                f"{tool_name} called {self._tool_history[tool_name]} times "
                f"(max {self.max_same_tool_calls})"
            )
            return ToolMessage(
                content=(
                    f"Error: Tool '{tool_name}' has been called "
                    f"{self.max_same_tool_calls} times already. "
                    f"Please try a different approach."
                ),
                tool_call_id=request.tool_call["id"],
                status="error",
            )

        return await handler(request)


def create_rate_limit_middleware(
    max_tool_calls: int = 10,
    max_llm_calls: int = 15,
    max_same_tool_calls: int = 5,
) -> list:
    """
    创建限流中间件列表。

    Returns:
        [ModelCallLimitMiddleware, ToolCallLimitMiddleware, SameToolLimitMiddleware]
    """
    return [
        ModelCallLimitMiddleware(
            run_limit=max_llm_calls,
            exit_behavior="end",
        ),
        ToolCallLimitMiddleware(
            run_limit=max_tool_calls,
            exit_behavior="continue",
        ),
        SameToolLimitMiddleware(max_same_tool_calls=max_same_tool_calls),
    ]
