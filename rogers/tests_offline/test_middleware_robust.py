"""
中间件健壮性加固测试（robust.py：异常围栏 fail-open + msg_tool_calls 安全提取）。

覆盖计划 P3：
1. 畸形历史矩阵：构造畸形 AIMessage.tool_calls（模拟 checkpoint 反序列化读回的
   不可信数据），喂各中间件 wrap_model_call / after_model，断言不抛异常——
   含今日事故现场占位串、args 缺失、tc 非 dict、缺 name，以及合法与畸形快照
   混排时回退到更早有效快照
2. 畸形 usage：usage_metadata={"input_tokens": "abc"} 喂 Summarization
   _real_input_tokens / _should_summarize，断言不抛、回退近似估算
3. 围栏 fail-open：PlanQueueMiddleware._prompt 抛异常时 wrap_model_call
   仍返回 handler 结果；state hook（TokenUsage.after_model）内部抛异常返回 None
4. 语义护栏：handler 自身异常（模型/工具错误）不被围栏吞掉（防二次调用/二次计费）
5. hook_config 元数据经 fail-open 包装后保留（TerminalTool 的 can_jump_to）
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

import pytest
from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.harness.runtime.middleware.callbacks import TokenUsageMiddleware
from src.agents.harness.runtime.middleware.content_validation_middleware import (
    ContentValidationMiddleware,
)
from src.agents.harness.runtime.middleware.plan_queue_middleware import (
    PlanQueueMiddleware,
    _reconstruct_queue,
)
from src.agents.harness.runtime.middleware.rate_limit import SameToolLimitMiddleware
from src.agents.harness.runtime.middleware.robust import msg_tool_calls
from src.agents.harness.runtime.middleware.fitcream_summarization import (
    FitCreamSummarizationMiddleware,
)
from src.agents.harness.runtime.middleware.terminal_tool import TerminalToolMiddleware


def _malformed_tool_calls_ai() -> AIMessage:
    """构造含今日事故现场 + 各类畸形条目的 AIMessage（直接改写 tool_calls，
    模拟 checkpoint 读回后不经过 pydantic 校验的不可信数据）。"""
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "present_plan_queue_tool", "args": {"title": "t", "todos": []}, "id": "c0", "type": "tool_call"}
        ],
    )
    ai.tool_calls = [
        # 今日事故现场：模型把裁剪占位符「…(省略)」原文当 todos 回传
        {"name": "present_plan_queue_tool", "args": {"todos": "…(省略)"}, "id": "c1", "type": "tool_call"},
        # args 缺失（None）
        {"name": "...", "args": None},
        # tc 非 dict
        ["not-a-dict"],
        # 缺 name（旧实现此处下标访问 -> KeyError 炸 run）
        {"args": {"x": 1}},
        # name 非 str
        {"name": 123, "args": {}},
    ]
    return ai


class TestMsgToolCalls:
    def test_extracts_valid_entries(self):
        ai = AIMessage(
            content="",
            tool_calls=[
                {"name": "present_plan_queue_tool", "args": {"todos": []}, "id": "c1", "type": "tool_call"},
                {"name": "checkin_tool", "args": {"x": 1}, "id": "c2", "type": "tool_call"},
            ],
        )
        out = msg_tool_calls(ai)
        assert out == [
            ("present_plan_queue_tool", {"todos": []}, "c1"),
            ("checkin_tool", {"x": 1}, "c2"),
        ]

    def test_skips_malformed_entries(self):
        ai = _malformed_tool_calls_ai()
        names = [name for name, _, _ in msg_tool_calls(ai)]
        # 畸形条目（tc 非 dict / 缺 name / name 非 str）被跳过
        assert "..." in names
        assert "not-a-dict" not in names
        assert all(name == "..." or name == "present_plan_queue_tool" for name in names)

    def test_args_none_becomes_empty_dict(self):
        ai = _malformed_tool_calls_ai()
        for name, args, _ in msg_tool_calls(ai):
            assert isinstance(args, dict)

    def test_no_tool_calls(self):
        assert msg_tool_calls(HumanMessage(content="你好")) == []


class TestMalformedHistoryMatrix:
    def _request_with_malformed(self) -> ModelRequest:
        return ModelRequest(
            model=None,
            messages=[HumanMessage(content="帮我设计计划"), _malformed_tool_calls_ai()],
        )

    def test_plan_queue_wrap_model_call_no_crash(self):
        mw = PlanQueueMiddleware()
        request = self._request_with_malformed()
        called = []

        def handler(req):
            called.append(req)
            return "ok"

        assert mw.wrap_model_call(request, handler) == "ok"
        # 畸形快照被跳过 -> 无提示词注入 -> handler 收到原始 request
        assert called == [request]

    async def test_plan_queue_awrap_model_call_no_crash(self):
        mw = PlanQueueMiddleware()
        request = self._request_with_malformed()
        called = []

        async def handler(req):
            called.append(req)
            return "ok"

        assert await mw.awrap_model_call(request, handler) == "ok"
        assert called == [request]

    def test_content_validation_wrap_model_call_no_crash(self):
        mw = ContentValidationMiddleware()
        request = self._request_with_malformed()
        called = []

        def handler(req):
            called.append(req)
            return "ok"

        assert mw.wrap_model_call(request, handler) == "ok"
        assert called == [request]

    def test_same_tool_limit_after_model_skips_malformed(self):
        ai = AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "c0", "type": "tool_call"}])
        # 全部条目畸形（无合法 name）-> 跳过不计数，不抛 KeyError
        ai.tool_calls = [["not-a-dict"], {"args": {"x": 1}}, {"name": 123, "args": {}}]
        mw = SameToolLimitMiddleware()
        state = {"messages": [HumanMessage(content="你好"), ai]}
        result = mw.after_model(state, None)
        assert result is not None
        assert result["same_tool_counts"] == {}

    def test_same_tool_limit_after_model_counts_valid_only(self):
        mw = SameToolLimitMiddleware()
        state = {"messages": [HumanMessage(content="你好"), _malformed_tool_calls_ai()]}
        result = mw.after_model(state, None)
        assert result is not None
        counts = result["same_tool_counts"]
        # 合法 name 的条目被计数，畸形条目跳过
        assert counts.get("present_plan_queue_tool") == 1
        assert counts.get("...") == 1

    def test_reconstruct_queue_malformed_latest_skipped(self):
        ai = _malformed_tool_calls_ai()
        assert _reconstruct_queue([HumanMessage(content="你好"), ai]) is None

    def test_reconstruct_queue_mixed_falls_back_to_older_valid(self):
        valid = AIMessage(
            content="",
            tool_calls=[
                {"name": "present_plan_queue_tool", "args": {"title": "第一版", "todos": [{"id": "a", "title": "大纲", "status": "pending"}]}, "id": "c0", "type": "tool_call"}
            ],
        )
        latest = _malformed_tool_calls_ai()
        snapshot = _reconstruct_queue([valid, HumanMessage(content="继续"), latest])
        assert snapshot is not None
        assert snapshot["title"] == "第一版"


class TestMalformedUsage:
    @staticmethod
    def _ai_with_malformed_usage(content: str = "") -> AIMessage:
        # usage_metadata 同样 pydantic 校验，先构造合法消息再改写为畸形值，
        # 模拟 checkpoint 读回后不经过校验的不可信数据
        ai = AIMessage(
            content=content,
            usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        )
        ai.usage_metadata = {"input_tokens": "abc", "total_tokens": "xyz"}
        return ai

    def test_real_input_tokens_malformed_usage_falls_back_to_approx(self):
        # 畸形 usage -> 回退近似估算（count_tokens_approximately），不抛异常
        tokens = FitCreamSummarizationMiddleware._real_input_tokens(
            [self._ai_with_malformed_usage("some context line for token estimation " * 20)]
        )
        assert tokens > 0

    def test_real_input_tokens_numeric_ok(self):
        ai = AIMessage(
            content="",
            usage_metadata={"input_tokens": 12345, "output_tokens": 1, "total_tokens": 12346},
        )
        assert FitCreamSummarizationMiddleware._real_input_tokens([ai]) == 12345

    def test_should_summarize_malformed_usage_falls_back_to_approx(self):
        messages = []
        for _ in range(12):
            messages.append(
                self._ai_with_malformed_usage(
                    "some context line for token estimation " * 20
                )
            )
        mw = FitCreamSummarizationMiddleware(None, keep_messages=5)
        total = mw._real_input_tokens(messages)
        # usage 畸形 -> 回退近似估算（count_tokens_approximately），仍 > 0 可参与触发判定
        assert total > 0
        mw._threshold = lambda: 1  # 小阈值验证回退估算仍可触发压缩
        assert mw._should_summarize(messages, total) is True


class TestFailOpen:
    def test_plan_queue_wrap_model_call_fail_open(self, monkeypatch):
        mw = PlanQueueMiddleware()

        def boom(messages):
            raise RuntimeError("snapshot boom")

        monkeypatch.setattr(PlanQueueMiddleware, "_prompt", boom)
        request = ModelRequest(model=None, messages=[HumanMessage(content="你好")])

        def handler(req):
            return "handler-ok"

        assert mw.wrap_model_call(request, handler) == "handler-ok"

    async def test_plan_queue_awrap_model_call_fail_open(self, monkeypatch):
        mw = PlanQueueMiddleware()

        def boom(messages):
            raise RuntimeError("snapshot boom")

        monkeypatch.setattr(PlanQueueMiddleware, "_prompt", boom)
        request = ModelRequest(model=None, messages=[HumanMessage(content="你好")])

        async def handler(req):
            return "handler-ok"

        assert await mw.awrap_model_call(request, handler) == "handler-ok"

    def test_token_usage_after_model_fail_open_returns_none(self):
        mw = TokenUsageMiddleware()

        class _BoomState:
            def get(self, key, default=None):
                raise RuntimeError("state boom")

        assert mw.after_model(_BoomState(), None) is None

    def test_handler_exception_not_swallowed(self):
        mw = PlanQueueMiddleware()
        request = ModelRequest(model=None, messages=[HumanMessage(content="你好")])

        def bad_handler(req):
            raise ValueError("model-error")

        with pytest.raises(ValueError):
            mw.wrap_model_call(request, bad_handler)

    async def test_async_handler_exception_not_swallowed(self):
        mw = PlanQueueMiddleware()
        request = ModelRequest(model=None, messages=[HumanMessage(content="你好")])

        async def bad_handler(req):
            raise ValueError("model-error")

        with pytest.raises(ValueError):
            await mw.awrap_model_call(request, bad_handler)


class TestTerminalToolHookConfig:
    def test_can_jump_to_preserved_through_fail_open(self):
        # hook_config 的元数据必须经 state_hook_fail_open 的 functools.wraps 保留，
        # 否则 LangChain 工厂读不到 can_jump_to，before_model 的 jump_to 会失效
        assert getattr(TerminalToolMiddleware.before_model, "__can_jump_to__", None) == ["end"]
        assert getattr(TerminalToolMiddleware.abefore_model, "__can_jump_to__", None) == ["end"]
