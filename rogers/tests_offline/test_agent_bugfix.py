"""
计划设计流程 Bug 修复离线单测（不依赖 LLM、不 import 生产 DB）。

覆盖（对应 .kilo/plan-agent-bugfix.md）：
- P0-1 意图关键词补齐：detect_intents 对「健身计划/训练计划/增肌计划」类说法命中
  plan_creation，负向关键词仍否决「查看我的计划」
- P1-4 SameToolLimit 按工具精细限额：tool_limits 覆盖（展示类工具限 2 次）
- P1-5 _repair_dangling_tool_calls：悬空 tool_calls 补合成 ToolMessage，幂等
- P1-6 ModelRouting 断路器：同 run 连续 DS 失败达阈值后剩余调用直接走 qwen
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402

from app.routers.chat import _repair_dangling_tool_calls  # noqa: E402
from src.agents.harness.orchestration.prompts.system import (  # noqa: E402
    INTENT_KEYWORDS,
    INTENT_PROMPTS,
)
from src.agents.harness.runtime.middleware.request_gate_middleware import (  # noqa: E402
    RequestGateMiddleware,
    detect_intents,
)
from src.agents.harness.runtime.middleware.model_routing import (  # noqa: E402
    ModelRoutingMiddleware,
    _ds_fail_counts,
    reset_ds_key_fallback,
)
from src.agents.harness.runtime.middleware.rate_limit import (  # noqa: E402
    SameToolLimitMiddleware,
)


# ============================================================
# P0-1 意图关键词补齐（Bug A1）
# ============================================================


class TestIntentKeywordSupplement:
    def test_new_keywords_present(self):
        kws = INTENT_KEYWORDS["plan_creation"]
        for kw in ("健身计划", "做个计划", "出一份计划", "出个计划", "弄个计划", "帮我规划", "安排一下训练"):
            assert kw in kws, f"缺少关键词: {kw}"

    def test_wo_plan_design(self):
        # Bug A1 根因复现：旧代码「设计计划」连续子串匹配被「健身」隔断 -> 零命中
        assert "plan_creation" in detect_intents(HumanMessage(content="请帮我设计健身计划"))

    def test_plan_variants_hit(self):
        for text in ("帮我弄个训练计划", "帮我出一份增肌计划", "帮我做个健身计划", "帮我规划一下训练"):
            assert "plan_creation" in detect_intents(HumanMessage(content=text)), text

    def test_view_my_plan_negative(self):
        # 负向关键词仍否决：查看/我的计划不触发 plan_creation
        intents = detect_intents(HumanMessage(content="查看我的计划"))
        assert "plan_creation" not in intents


# ============================================================
# plan_design 门控：完整 plan-execute 仅限按钮会话
# ============================================================


class TestPlanDesignGating:
    def test_button_guide_prompt_loaded(self):
        assert "plan_creation_button" in INTENT_PROMPTS
        assert "为我设计健身计划" in INTENT_PROMPTS["plan_creation_button"]

    def _mw(self, monkeypatch, plan_design: bool):
        monkeypatch.setattr(
            "src.agents.harness.runtime.middleware.request_gate_middleware.get_config_flag",
            lambda name, default=False: (
                plan_design if name == "plan_design" else False
            ),
        )
        return RequestGateMiddleware()

    def _run(self, mw: RequestGateMiddleware, text: str) -> str:
        """跑一轮 wrap_model_call，返回合并进 system_message 的提示词文本。

        F1 迁移后 RequestGateMiddleware 走 wrap_model_call 临时注入（不落 checkpoint）。
        """
        from langchain.agents.middleware.types import ModelRequest
        from langchain_core.messages import HumanMessage

        request = ModelRequest(model=None, messages=[HumanMessage(content=text)])
        captured = {}

        def handler(req):
            captured["req"] = req
            return "ok"

        mw.wrap_model_call(request, handler)
        sys_msg = captured["req"].system_message
        return sys_msg.content if sys_msg else ""

    def test_non_plan_design_injects_button_guide(self, monkeypatch):
        mw = self._mw(monkeypatch, plan_design=False)
        content = self._run(mw, "请帮我设计健身计划")
        # 注入按钮引导，而不是完整 plan-execute 流程（闭环待办只在完整流程提示词里）
        assert content != ""
        assert "按钮" in content
        assert "闭环待办" not in content

    def test_plan_design_injects_full_flow(self, monkeypatch):
        mw = self._mw(monkeypatch, plan_design=True)
        content = self._run(mw, "请帮我设计健身计划")
        # 按钮进入的 plan_design 会话：注入完整队列流程
        assert content != ""
        assert "闭环待办" in content

    def test_plan_design_does_not_leak_button_guide(self, monkeypatch):
        mw = self._mw(monkeypatch, plan_design=True)
        content = self._run(mw, "请帮我设计健身计划")
        assert "按钮" not in content

    def test_non_plan_design_other_intents_kept(self, monkeypatch):
        # 非 plan_design 时 plan_creation 替换为按钮引导，其他意图提示词保留
        mw = self._mw(monkeypatch, plan_design=False)
        content = self._run(mw, "请帮我设计健身计划，练完了")
        assert content != ""
        assert "按钮" in content
        assert "训练打卡" in content  # checkin 意图提示词仍在


# ============================================================
# P1-4 SameToolLimit 按工具精细限额（Bug A3）
# ============================================================


def _make_request(state: dict, tool_name: str = "some_tool") -> "object":
    from langchain.agents.middleware.types import ToolCallRequest

    return ToolCallRequest(
        tool_call={"name": tool_name, "args": {}, "id": "call-1", "type": "tool_call"},
        tool=None,
        state=state,
        runtime=None,
    )


class TestSameToolLimitPerTool:
    def test_default_limit_unchanged(self):
        mw = SameToolLimitMiddleware(max_same_tool_calls=5)
        assert mw._limit_for("get_exercises_tool") == 5

    def test_tool_limits_override(self):
        mw = SameToolLimitMiddleware(
            max_same_tool_calls=5,
            tool_limits={"present_plan_queue_tool": 2},
        )
        assert mw._limit_for("present_plan_queue_tool") == 2
        assert mw._limit_for("present_outline_tool") == 5

    def test_present_plan_queue_blocked_at_3rd(self):
        mw = SameToolLimitMiddleware(
            max_same_tool_calls=5,
            tool_limits={"present_plan_queue_tool": 2},
        )
        # 第 2 次（count=2）仍放行
        state_ok = {"same_tool_counts": {"present_plan_queue_tool": 2}}
        executed = []

        def handler(request):
            executed.append(True)
            return "ok"

        assert mw.wrap_tool_call(_make_request(state_ok, "present_plan_queue_tool"), handler) == "ok"

        # 第 3 次（count=3）被拦截，返回错误 ToolMessage 且工具不执行
        state_block = {"same_tool_counts": {"present_plan_queue_tool": 3}}
        result = mw.wrap_tool_call(
            _make_request(state_block, "present_plan_queue_tool"), handler
        )
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert executed == [True]  # 仅第 1 次真正执行

    def test_present_form_tool_limit_1(self):
        # 表单限 1：同一 run 内第 2 次 present_form_tool 被拦截（每轮只发一个表单）
        mw = SameToolLimitMiddleware(
            max_same_tool_calls=5,
            tool_limits={"present_form_tool": 1},
        )
        assert mw._limit_for("present_form_tool") == 1
        executed = []

        def handler(request):
            executed.append(True)
            return "ok"

        # 第 1 次（count=1）放行
        assert mw.wrap_tool_call(
            _make_request({"same_tool_counts": {"present_form_tool": 1}}, "present_form_tool"),
            handler,
        ) == "ok"
        # 第 2 次（count=2）拦截，带中文收口引导
        result = mw.wrap_tool_call(
            _make_request({"same_tool_counts": {"present_form_tool": 2}}, "present_form_tool"),
            handler,
        )
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert "每次只能向用户发送一个表单" in result.content
        assert "表单提交" in result.content
        assert executed == [True]


# ============================================================
# P1-5 悬空 tool_calls 修复（Bug B1）
# ============================================================


class FakeTuple:
    def __init__(self, config, checkpoint, metadata):
        self.config = config
        self.checkpoint = checkpoint
        self.metadata = metadata


class FakeCheckpointer:
    def __init__(self, messages):
        self.messages = messages
        self.put_calls = 0
        self.saved_messages = None

    async def aget_tuple(self, config):
        return FakeTuple(
            config=config,
            checkpoint={
                "channel_values": {"messages": self.messages},
                "channel_versions": {},
            },
            metadata={},
        )

    async def aput(self, config, checkpoint, metadata, new_versions):
        self.put_calls += 1
        self.saved_messages = checkpoint["channel_values"]["messages"]
        self.saved_versions = new_versions


class TestRepairDanglingToolCalls:
    async def test_repairs_dangling_tool_call(self):
        cp = FakeCheckpointer([
            AIMessage(
                content="",
                tool_calls=[{
                    "name": "present_plan_queue_tool",
                    "args": {},
                    "id": "c1",
                    "type": "tool_call",
                }],
            ),
            HumanMessage(content="继续"),
        ])
        await _repair_dangling_tool_calls(cp, "thread-x")
        assert cp.put_calls == 1
        replied = [m for m in cp.saved_messages if isinstance(m, ToolMessage)]
        assert len(replied) == 1
        assert replied[0].tool_call_id == "c1"
        assert "未执行完成" in replied[0].content
        # 必须 bump messages 的 channel_versions，否则 AsyncPostgresSaver 不持久化
        assert cp.saved_versions is not None
        assert str(cp.saved_versions.get("messages", "")).endswith(".repair.1")

    async def test_idempotent(self):
        cp = FakeCheckpointer([
            AIMessage(
                content="",
                tool_calls=[{"name": "t", "args": {}, "id": "c1", "type": "tool_call"}],
            ),
        ])
        await _repair_dangling_tool_calls(cp, "thread-x")
        await _repair_dangling_tool_calls(cp, "thread-x")
        assert cp.put_calls == 1

    async def test_clean_history_no_write(self):
        cp = FakeCheckpointer([
            AIMessage(
                content="",
                tool_calls=[{"name": "t", "args": {}, "id": "c1", "type": "tool_call"}],
            ),
            ToolMessage(content="ok", tool_call_id="c1", name="t"),
        ])
        await _repair_dangling_tool_calls(cp, "thread-x")
        assert cp.put_calls == 0


# ============================================================
# P1-6 ModelRouting 断路器（Bug B2）
# ============================================================


class FakeModelRequest:
    """模拟 wrap_model_call 的 request：track 最终 override 的 model。"""

    def __init__(self, model=None):
        self._model = model

    def override(self, model=None, **kwargs):
        return FakeModelRequest(model=model)

    @property
    def model(self):
        return self._model


def _fake_config(monkeypatch):
    """monkeypatch get_config_value 返回固定 deepseek key + thread_id。"""

    def fake_get(name, default=None):
        return {"deepseek_api_key": "sk-test", "thread_id": "thread-1"}.get(name, default)

    monkeypatch.setattr(
        "src.agents.harness.runtime.middleware.model_routing.get_config_value",
        fake_get,
    )


class TestModelRoutingBreaker:
    def test_breaker_opens_after_two_failures(self, monkeypatch):
        _fake_config(monkeypatch)
        reset_ds_key_fallback("thread-1")

        calls = {"resolve": 0, "handler": 0}
        models_seen = []

        def fake_resolve(*, user_ds_key=None, enable_thinking=True):
            calls["resolve"] += 1
            if user_ds_key:
                raise ValueError("deepseek 限流/服务端错误")
            # 无 key 走 qwen（思考开关透传）：短路成功返回
            return f"qwen-{enable_thinking}"

        def handler(request):
            calls["handler"] += 1
            models_seen.append(request.model)
            return "ok"

        monkeypatch.setattr(
            "src.agents.harness.runtime.middleware.model_routing.resolve_chat_model",
            fake_resolve,
        )
        mw = ModelRoutingMiddleware()

        # 第 1、2 次：尝试 DS -> 失败 -> 回退 qwen（思考开关透传 override）
        assert mw.wrap_model_call(FakeModelRequest(), handler) == "ok"
        assert mw.wrap_model_call(FakeModelRequest(), handler) == "ok"
        # 第 3 次：断路器打开，直接走 qwen，不再尝试 DS
        assert mw.wrap_model_call(FakeModelRequest(), handler) == "ok"

        # 第 1、2 次：DS resolve 失败 + qwen 回退 resolve（各 2 次 = 4）；
        # 第 3 次：断路器打开只走 qwen resolve（1 次）——DS 未被第三次尝试
        assert calls["resolve"] == 5, "断路器未生效，DS 被第三次尝试"
        assert calls["handler"] == 3
        assert models_seen == ["qwen-False", "qwen-False", "qwen-False"]
        assert _ds_fail_counts.get("thread-1") == 2

    def test_breaker_reset_per_run(self, monkeypatch):
        _fake_config(monkeypatch)
        reset_ds_key_fallback("thread-1")

        def fake_resolve(*, user_ds_key=None, enable_thinking=True):
            if user_ds_key:
                raise ValueError("boom")
            return f"qwen-{enable_thinking}"

        def handler(request):
            return "ok"

        monkeypatch.setattr(
            "src.agents.harness.runtime.middleware.model_routing.resolve_chat_model",
            fake_resolve,
        )
        mw = ModelRoutingMiddleware()
        mw.wrap_model_call(FakeModelRequest(), handler)
        mw.wrap_model_call(FakeModelRequest(), handler)
        assert _ds_fail_counts.get("thread-1") == 2

        # 新 run 开头 reset -> 计数清零，下一次仍会尝试 DS
        reset_ds_key_fallback("thread-1")
        assert _ds_fail_counts.get("thread-1") is None

    def test_no_key_skips_breaker(self, monkeypatch):
        monkeypatch.setattr(
            "src.agents.harness.runtime.middleware.model_routing.get_config_value",
            lambda name, default=None: None,
        )
        reset_ds_key_fallback("thread-1")
        calls = {"handler": 0}

        def handler(request):
            calls["handler"] += 1
            return "ok"

        mw = ModelRoutingMiddleware()
        mw.wrap_model_call(FakeModelRequest(), handler)
        assert calls["handler"] == 1
