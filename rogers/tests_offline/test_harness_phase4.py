"""
阶段四：编排状态视图裁剪不变量单测（不依赖真实 LLM、不 import 生产 DB）。

覆盖：
- 4.1 ContextMessageGateMiddleware：_redact_messages / _redact_queue_args 纯函数、
  wrap_model_call 视图级裁剪且不改动原消息
- 4.2 PlanQueueMiddleware：_reconstruct_queue 后向扫描只取最新快照
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.harness.runtime.middleware.context_message_gate import (
    ContextMessageGateMiddleware,
    _redact_messages,
    _redact_queue_args,
)
from src.agents.harness.runtime.middleware.plan_queue_middleware import _reconstruct_queue


def _queue_ai(tool_name: str, title: str, todos: list | str) -> AIMessage:
    args = {"title": title, "todos": todos}
    if tool_name == "update_plan_queue_item_tool":
        args = {"item_id": "i1", "status": "completed", "queue": args}
    return AIMessage(
        content="",
        tool_calls=[
            {"name": tool_name, "args": args, "id": "c1", "type": "tool_call"}
        ],
    )


FULL_TODOS = [{"id": "a", "title": "收集数据", "status": "pending"}]


class TestRedactQueueArgs:
    def test_present_plan_queue_tool(self):
        redacted = _redact_queue_args({"title": "4周计划", "todos": FULL_TODOS}, "present_plan_queue_tool")
        assert redacted["title"] == "4周计划"
        assert isinstance(redacted["todos"], str)
        assert "省略" in redacted["todos"]

    def test_update_plan_queue_item_tool(self):
        redacted = _redact_queue_args(
            {"item_id": "i1", "status": "completed", "queue": {"title": "4周计划", "todos": FULL_TODOS}},
            "update_plan_queue_item_tool",
        )
        assert redacted["item_id"] == "i1"
        assert redacted["status"] == "completed"
        assert redacted["queue"]["title"] == "4周计划"
        assert isinstance(redacted["queue"]["todos"], str)


class TestRedactMessages:
    def test_redacts_queue_tool_calls(self):
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai("present_plan_queue_tool", "4周计划", FULL_TODOS),
            _queue_ai("update_plan_queue_item_tool", "4周计划", FULL_TODOS),
        ]
        redacted = _redact_messages(msgs)
        assert redacted is not msgs
        # 原始消息不被改动
        assert msgs[1].tool_calls[0]["args"]["todos"] == FULL_TODOS
        assert msgs[2].tool_calls[0]["args"]["queue"]["todos"] == FULL_TODOS
        # 更早的队列工具被裁剪（token 精简）
        assert isinstance(redacted[1].tool_calls[0]["args"]["todos"], str)
        # 最新一份队列快照保留完整：模型必须据此构造下一次 update 的完整入参
        # （否则模型会把裁剪占位符原文当 todos 传回 -> 校验失败 -> 死循环）
        assert redacted[2].tool_calls[0]["args"]["queue"]["todos"] == FULL_TODOS
        # 非队列消息原样保留
        assert redacted[0] is msgs[0]

    def test_single_queue_call_kept_full(self):
        # 只有一份队列快照时完全不裁剪（它既是"最新"也是模型推进的依据）
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai("present_plan_queue_tool", "4周计划", FULL_TODOS),
        ]
        redacted = _redact_messages(msgs)
        assert redacted is msgs
        assert redacted[1].tool_calls[0]["args"]["todos"] == FULL_TODOS

    def test_no_queue_calls_returns_same_list(self):
        msgs = [HumanMessage(content="你好"), AIMessage(content="嗨")]
        assert _redact_messages(msgs) is msgs

    def test_non_queue_tool_calls_untouched(self):
        ai = AIMessage(
            content="",
            tool_calls=[
                {"name": "checkin_tool", "args": {"x": 1}, "id": "c1", "type": "tool_call"}
            ],
        )
        msgs = [ai]
        redacted = _redact_messages(msgs)
        assert redacted is msgs


class TestContextMessageGateMiddleware:
    def test_wrap_model_call_redacts(self):
        mw = ContextMessageGateMiddleware()
        messages = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai("present_plan_queue_tool", "4周计划", FULL_TODOS),
            _queue_ai("update_plan_queue_item_tool", "4周计划", FULL_TODOS),
        ]
        request = ModelRequest(model=None, messages=messages)

        captured = {}

        def handler(req):
            captured["req"] = req
            return "ok"

        result = mw.wrap_model_call(request, handler)
        assert result == "ok"
        assert captured["req"] is not request
        # 更早的队列快照被裁剪
        assert isinstance(captured["req"].messages[1].tool_calls[0]["args"]["todos"], str)
        # 最新一份保留完整（模型据此推进，防占位符被回传 -> 死循环）
        assert captured["req"].messages[2].tool_calls[0]["args"]["queue"]["todos"] == FULL_TODOS

    async def test_awrap_model_call_redacts(self):
        mw = ContextMessageGateMiddleware()
        messages = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai("present_plan_queue_tool", "4周计划", FULL_TODOS),
            _queue_ai("update_plan_queue_item_tool", "4周计划", FULL_TODOS),
        ]
        request = ModelRequest(model=None, messages=messages)

        captured = {}

        async def handler(req):
            captured["req"] = req
            return "ok"

        result = await mw.awrap_model_call(request, handler)
        assert result == "ok"
        assert captured["req"] is not request
        # 最新一份保留完整
        assert captured["req"].messages[2].tool_calls[0]["args"]["queue"]["todos"] == FULL_TODOS

    def test_no_queue_calls_passthrough(self):
        mw = ContextMessageGateMiddleware()
        request = ModelRequest(model=None, messages=[HumanMessage(content="你好")])

        def handler(req):
            return "ok"

        assert mw.wrap_model_call(request, handler) == "ok"

    def test_fallback_on_exception(self, monkeypatch):
        from src.agents.harness.runtime.middleware import context_message_gate as cmg

        def boom(messages):
            raise RuntimeError("boom")

        monkeypatch.setattr(cmg, "_redact_messages", boom)
        mw = ContextMessageGateMiddleware()
        request = ModelRequest(model=None, messages=[HumanMessage(content="你好")])

        def handler(req):
            return "fallback-ok"

        assert mw.wrap_model_call(request, handler) == "fallback-ok"


class TestReconstructQueueBackwardScan:
    def test_returns_latest_snapshot(self):
        msgs = [
            _queue_ai("present_plan_queue_tool", "第一版", FULL_TODOS),
            HumanMessage(content="继续"),
            _queue_ai("update_plan_queue_item_tool", "第二版", FULL_TODOS),
        ]
        snapshot = _reconstruct_queue(msgs)
        assert snapshot["title"] == "第二版"

    def test_no_queue_returns_none(self):
        msgs = [HumanMessage(content="你好"), AIMessage(content="嗨")]
        assert _reconstruct_queue(msgs) is None

    def test_redacted_queue_still_reconstructed(self):
        # 即使入参被模型视图裁剪（todos 为占位串），后向扫描仍能拿到快照结构
        msgs = [_queue_ai("present_plan_queue_tool", "4周计划", "…(省略)")]
        snapshot = _reconstruct_queue(msgs)
        assert snapshot["title"] == "4周计划"
