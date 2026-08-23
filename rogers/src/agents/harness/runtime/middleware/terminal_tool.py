"""
终结工具中间件（terminate 语义，对齐 pi 的「批内全部 terminate 才 terminate」）

背景：当前 agent 在工具执行后总会再触发一轮自动 LLM 总结。对于结果自明、
工具返回体已自带最终展示文案（message 字段即用户所见）的纯结果型工具，
这一轮 LLM 是多余开销，还会让模型赘述「已创建/已设置」。

机制：
- 白名单集合 TERMINAL_TOOLS（保守起步默认空，按 3.3 逐工具灰度填入）。
- 在 before_model / abefore_model 中检测：当「上一批工具」全部为白名单终结
  工具且全部成功（无 error ToolMessage、无悬挂调用）时，返回 {"jump_to": "end"}
  结束 run，跳过后续自动 LLM 调用。
- 检测放在工具执行**之后**（下一轮 before_model），天然规避并行工具批下
  wrap_tool_call 无法知晓兄弟工具结果的问题；也只在「批内全部终结」时触发，
  避免混合批（终结 + 非终结）误终止。

边界：
- 最新消息不是 ToolMessage（刚收到用户新消息 / 模型已直接作答）时不触发。
- 任一工具失败（status=error）或存在未得到结果的 tool_call 时不触发，
  让模型继续处理。
- 非白名单工具（checkin_tool / create_plan_tool / record_meal_tool 等
  high-touch 工具）保持现状多一轮 LLM 个性化总结。

白名单候选（3.3，与产品对齐后启用，默认空）：
- 适合：set_nutrition_goals_tool（纯参数设定、结果自明）等纯结果型工具。
- 明确排除：checkin_tool / create_plan_tool / record_meal_tool 等需要
  个性化鼓励 / 总结的 high-touch 工具。
- HITL 断点工具（create_plan_tool 等）是否在 approve 落库后纳入终结为
  产品决策，默认不纳入（保持「已创建」个性化总结）。
"""

import logging
from collections.abc import Collection
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import hook_config
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime

logger = logging.getLogger("fitcream.agent")

# 终结工具白名单（默认空；实施时按 3.3 与产品确认后逐工具填充）
TERMINAL_TOOLS: set[str] = set()


class TerminalToolMiddleware(AgentMiddleware):
    """
    终结工具中间件：白名单工具批全部成功执行后跳过后续自动 LLM 调用。

    无实例级可变状态（白名单为构造时不可变集合），编译进共享 graph，
    并发 run 互不影响。
    """

    def __init__(
        self,
        terminal_tools: Collection[str] | None = None,
        *,
        enabled: bool = True,
    ) -> None:
        super().__init__()
        self.terminal_tools = frozenset(terminal_tools) if terminal_tools is not None else frozenset(TERMINAL_TOOLS)
        self.enabled = enabled

    def _batch_all_terminal_and_succeeded(self, state: AgentState) -> bool:
        """判断「上一批工具」是否全部为白名单终结工具且全部成功。

        仅当最新消息为 ToolMessage（刚执行完工具批、尚未进入新一轮用户消息）
        且其前置 AIMessage 的所有 tool_calls 均为白名单工具、每个都有对应
        成功 ToolMessage 时返回 True。
        """
        if not self.enabled or not self.terminal_tools:
            return False

        messages = (state or {}).get("messages", [])
        if not messages or not isinstance(messages[-1], ToolMessage):
            return False

        # 收集末尾连续的 ToolMessage（本批工具结果）
        idx = len(messages) - 1
        trailing: list[ToolMessage] = []
        while idx >= 0 and isinstance(messages[idx], ToolMessage):
            trailing.append(messages[idx])
            idx -= 1

        if idx < 0 or not isinstance(messages[idx], AIMessage):
            return False

        last_ai: AIMessage = messages[idx]
        if not last_ai.tool_calls:
            return False

        names = {tc.get("name") for tc in last_ai.tool_calls}
        if not names or not names.issubset(self.terminal_tools):
            return False

        # 每个 tool_call 都必须有对应结果（无悬挂），且全部成功
        call_ids = {tc.get("id") for tc in last_ai.tool_calls}
        result_ids = {m.tool_call_id for m in trailing}
        if call_ids != result_ids:
            return False
        if any(m.status == "error" for m in trailing):
            return False

        return True

    @hook_config(can_jump_to=["end"])
    def before_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """同步路径：终结工具批全部成功后结束 run，跳过后续自动 LLM。"""
        if not self._batch_all_terminal_and_succeeded(state):
            return None
        logger.info("[TerminalTool] 白名单终结工具批全部成功，结束 run")
        return {"jump_to": "end"}

    @hook_config(can_jump_to=["end"])
    async def abefore_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """异步路径（生产 SSE 走这里）：同 before_model。"""
        if not self._batch_all_terminal_and_succeeded(state):
            return None
        logger.info("[TerminalTool] 白名单终结工具批全部成功，结束 run")
        return {"jump_to": "end"}
