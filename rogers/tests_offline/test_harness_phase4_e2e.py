"""
阶段四端到端：ContextMessageGateMiddleware 视图级裁剪集成验证（用 Fake 模型，不连 DB）。

验证：agent 运行中，模型实际收到的历史消息里队列工具入参被裁剪为轻量占位；
checkpoint（state["messages"]）里的完整入参保持原样。
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from src.agents.harness.runtime.middleware.context_message_gate import (
    ContextMessageGateMiddleware,
)


@tool
def trivial_tool(value: str) -> str:
    """测试工具。"""
    return f"ok:{value}"


class _CaptureModel(BaseChatModel):
    """记录每次模型调用收到的 messages，并直接返回最终文本（不再调工具）。"""

    seen_messages: list = []
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "capture-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        self.seen_messages = list(messages)
        msg = AIMessage(content="已完成")
        return ChatResult(generations=[ChatGeneration(message=msg)])


def _make_queue_ai(tool_name: str, title: str) -> AIMessage:
    args = {"title": title, "todos": [{"id": "a", "title": "收集数据", "status": "pending"}]}
    if tool_name == "update_plan_queue_item_tool":
        args = {"item_id": "i1", "status": "completed", "queue": args}
    return AIMessage(
        content="",
        tool_calls=[{"name": tool_name, "args": args, "id": "c1", "type": "tool_call"}],
    )


def test_model_sees_redacted_queue_args_but_state_kept():
    from langchain_core.messages import ToolMessage

    model = _CaptureModel()
    agent = create_agent(
        model=model,
        tools=[trivial_tool],
        system_prompt="你是测试助手",
        middleware=[ContextMessageGateMiddleware()],
    )

    history_msgs = [
        HumanMessage(content="帮我设计计划"),
        _make_queue_ai("present_plan_queue_tool", "4周计划"),
        ToolMessage(content='{"ok": true}', tool_call_id="c1"),
        _make_queue_ai("update_plan_queue_item_tool", "4周计划"),
        ToolMessage(content='{"ok": true}', tool_call_id="c1"),
        HumanMessage(content="继续"),
    ]

    result = agent.invoke({"messages": history_msgs})

    # 模型视图：更早的队列快照被裁剪（todos 为占位串），最新一份保留完整
    seen = model.seen_messages
    queue_ais = [m for m in seen if getattr(m, "tool_calls", None)]
    assert len(queue_ais) >= 2
    # 更早的（present_plan_queue_tool）被裁剪
    older_args = queue_ais[0].tool_calls[0]["args"]
    assert isinstance(older_args["todos"], str)
    assert "省略" in older_args["todos"]
    # 最新的（update_plan_queue_item_tool）保留完整——模型据此构造下一次完整入参，
    # 防止占位符被原文回传导致校验失败 -> 死循环
    latest_args = queue_ais[-1].tool_calls[0]["args"]
    assert isinstance(latest_args.get("queue", {}).get("todos"), list)

    # checkpoint/state 中完整入参保持原样
    saved_queue_ai = next(
        m for m in result["messages"] if getattr(m, "tool_calls", None)
    )
    assert isinstance(saved_queue_ai.tool_calls[0]["args"]["todos"], list)
