"""
Agent 限流中间件

三层限流策略，防止 Agent 陷入无限循环或过度消耗 Token：
1. ModelCallLimitMiddleware: 限制单次对话中 LLM 调用总次数（默认 30 次）
2. ToolCallLimitMiddleware: 限制单次对话中 Tool 调用总次数（默认 10 次）
3. SameToolLimitMiddleware: 限制同一 Tool 的重复调用次数（默认 5 次）

前两者使用 LangChain 内置中间件，后者为自定义实现。

SameToolLimitMiddleware 的每轮计数存入 AgentState（UntrackedValue，随 run 重置），
避免共享 graph 下并发请求互相覆盖（根因 R2）。
"""

import logging
from typing import Annotated, Any

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain.agents.middleware.types import PrivateStateAttr, hook_config
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

logger = logging.getLogger("fitcream.agent")


class SameToolLimitState(AgentState):
    """SameToolLimitMiddleware 的每轮状态（不持久化到 checkpoint）。"""

    same_tool_counts: NotRequired[Annotated[dict[str, int], UntrackedValue, PrivateStateAttr]]


class SameToolLimitMiddleware(AgentMiddleware):
    """
    限制同一 Tool 在单次 run 中的重复调用次数。

    内置 ToolCallLimitMiddleware 只支持全局或按 tool_name 的 thread/run 限制，
    此类补充"同一 tool 调用次数上限"的检测。

    计数与拦截在 after_model 完成（读取最新 AIMessage 的 tool_calls，与内置
    ToolCallLimitMiddleware 一致），通过注入错误 ToolMessage 阻断超额调用--
    agent 路由会跳过已有 ToolMessage 的 tool_call，不会真正执行。
    """

    state_schema = SameToolLimitState  # type: ignore[assignment]

    def __init__(self, max_same_tool_calls: int = 5):
        super().__init__()
        self.max_same_tool_calls = max_same_tool_calls

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        logger.info(
            f"[RateLimit] SameToolLimit started | max_same_tool_calls={self.max_same_tool_calls}"
        )
        # 计数由 UntrackedValue 保证随 run 重置，无需显式清零
        return None

    @hook_config(can_jump_to=["end"])
    def after_model(self, state: SameToolLimitState, runtime: Runtime) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        # 找最近一条 AIMessage
        last_ai_message: AIMessage | None = None
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                last_ai_message = message
                break

        if not last_ai_message or not last_ai_message.tool_calls:
            return None

        counts = dict(state.get("same_tool_counts", {}))
        blocked: list[ToolMessage] = []

        for tool_call in last_ai_message.tool_calls:
            tool_name = tool_call["name"]
            counts[tool_name] = counts.get(tool_name, 0) + 1
            current = counts[tool_name]

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
                blocked.append(
                    ToolMessage(
                        content=(
                            f"Error: Tool '{tool_name}' has been called "
                            f"{self.max_same_tool_calls} times already. "
                            f"Please try a different approach."
                        ),
                        tool_call_id=tool_call["id"],
                        status="error",
                    )
                )

        if blocked:
            # 注入错误 ToolMessage 阻断超额调用（路由会跳过已有结果的 tool_call）
            return {"same_tool_counts": counts, "messages": blocked}
        return {"same_tool_counts": counts}

    @hook_config(can_jump_to=["end"])
    async def aafter_model(
        self, state: SameToolLimitState, runtime: Runtime
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


def create_rate_limit_middleware(
    max_tool_calls: int = 10,
    max_llm_calls: int = 30,
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
