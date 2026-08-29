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
from langchain.agents.middleware.types import PrivateStateAttr
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

from src.agents.harness.runtime.middleware.robust import (
    model_hook_fail_open,
    msg_tool_calls,
    state_hook_fail_open,
)

logger = logging.getLogger("fitcream.agent")

# 限流拦截时的引导文案（按工具覆盖）：默认走英文通用提示；对交互类工具给出
# 中文收口指引，帮助模型理解被拦原因并正确等待用户输入。
TOOL_LIMIT_HINTS: dict[str, str] = {
    "present_form_tool": (
        "每次只能向用户发送一个表单。请停止继续调用表单工具，用简短文字引导用户"
        "填写当前表单，等待收到「[表单提交: <form_id>]」后再发送下一个表单。"
    ),
}


def _limit_hint(tool_name: str, limit: int) -> str:
    hint = TOOL_LIMIT_HINTS.get(tool_name)
    if hint:
        return f"Error: Tool '{tool_name}' 已达单次会话调用上限（{limit} 次）。{hint}"
    return (
        f"Error: Tool '{tool_name}' has been called "
        f"{limit} times already. Please try a different approach."
    )


class SameToolLimitState(AgentState):
    """SameToolLimitMiddleware 的每轮状态（不持久化到 checkpoint）。"""

    same_tool_counts: NotRequired[Annotated[dict[str, int], UntrackedValue, PrivateStateAttr]]


class SameToolLimitMiddleware(AgentMiddleware):
    """
    限制同一 Tool 在单次 run 中的重复调用次数。

    内置 ToolCallLimitMiddleware 只支持全局或按 tool_name 的 thread/run 限制，
    此类补充"同一 tool 调用次数上限"的检测。

    计数在 after_model 完成（读取最新 AIMessage 的 tool_calls，与内置
    ToolCallLimitMiddleware 一致）；拦截改在 wrap_tool_call / awrap_tool_call：
    工具真正执行前若本轮调用次数已超限，则短路返回错误 ToolMessage——
    不执行工具（无副作用），也不再像旧实现那样在 after_model 注入与工具轮次
    不匹配的伪造 ToolMessage 污染消息历史。
    """

    state_schema = SameToolLimitState  # type: ignore[assignment]

    def __init__(
        self,
        max_same_tool_calls: int = 5,
        tool_limits: dict[str, int] | None = None,
    ):
        super().__init__()
        self.max_same_tool_calls = max_same_tool_calls
        # 按工具覆盖默认上限（如展示类工具严格限制），未列出的工具用默认值
        self.tool_limits: dict[str, int] = tool_limits or {}

    def _limit_for(self, tool_name: str) -> int:
        """该工具的调用上限（未单独配置则用默认值）。"""
        return self.tool_limits.get(tool_name, self.max_same_tool_calls)

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        logger.info(
            f"[RateLimit] SameToolLimit started | max_same_tool_calls={self.max_same_tool_calls}"
        )
        # 计数由 UntrackedValue 保证随 run 重置，无需显式清零
        return None

    @state_hook_fail_open
    def after_model(self, state: SameToolLimitState, runtime: Runtime) -> dict[str, Any] | None:
        """读取最新 AIMessage 的 tool_calls 累加计数（不注入拦截消息）。

        真正拦截由 wrap_tool_call 在工具执行前完成：after_model 只管计数，
        wrap_tool_call 根据计数短路，二者配合使"第 max+1 次调用"不被执行。

        经 msg_tool_calls 统一安全提取：畸形条目（非 dict / 缺 name / args 非
        dict）跳过不计数，避免对不可信 tool_calls 下标访问抛 KeyError 炸 run
        （P2 点修）。
        """
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

        for tool_name, _, _ in msg_tool_calls(last_ai_message):
            counts[tool_name] = counts.get(tool_name, 0) + 1
            limit = self._limit_for(tool_name)

            logger.info(
                f"[RateLimit] Tool call check | tool={tool_name} | "
                f"count={counts[tool_name]}/{limit}"
            )

        return {"same_tool_counts": counts}

    def _is_over_limit(self, state: Any, tool_name: str) -> bool:
        """按 state 中已累计计数判断是否超过同一工具调用上限（按工具精细限额）。"""
        counts = (state or {}).get("same_tool_counts", {}) or {}
        return counts.get(tool_name, 0) > self._limit_for(tool_name)

    @model_hook_fail_open
    def wrap_tool_call(self, request, handler):
        """工具执行前拦截：超限则短路，不执行工具。"""
        tool_name = request.tool_call["name"]
        limit = self._limit_for(tool_name)
        if self._is_over_limit(request.state, tool_name):
            logger.warning(
                f"[RateLimit] Same tool limit exceeded, blocked before execution: "
                f"{tool_name} (max {limit})"
            )
            return ToolMessage(
                content=_limit_hint(tool_name, limit),
                tool_call_id=request.tool_call["id"],
                name=tool_name,
                status="error",
            )
        return handler(request)

    @model_hook_fail_open
    async def awrap_tool_call(self, request, handler):
        """异步工具执行前拦截：超限则短路，不执行工具。"""
        tool_name = request.tool_call["name"]
        limit = self._limit_for(tool_name)
        if self._is_over_limit(request.state, tool_name):
            logger.warning(
                f"[RateLimit] Same tool limit exceeded, blocked before execution: "
                f"{tool_name} (max {limit})"
            )
            return ToolMessage(
                content=_limit_hint(tool_name, limit),
                tool_call_id=request.tool_call["id"],
                name=tool_name,
                status="error",
            )
        return await handler(request)


def create_rate_limit_middleware(
    max_tool_calls: int = 10,
    max_llm_calls: int = 30,
    max_same_tool_calls: int = 5,
    tool_limits: dict[str, int] | None = None,
) -> list:
    """
    创建限流中间件列表。

    Args:
        tool_limits: 按工具覆盖 SameToolLimit 上限（如展示类工具限 2 次）。

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
        SameToolLimitMiddleware(
            max_same_tool_calls=max_same_tool_calls,
            tool_limits=tool_limits,
        ),
    ]
