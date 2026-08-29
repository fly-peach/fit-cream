"""
阶段二：模型上下文质量不变量单测（不依赖真实 LLM、不 import 生产 DB）。

覆盖：
- 2.1 FitCream 会话压缩中间件（内置 SummarizationMiddleware 子类）：safe cutoff、
  动态阈值（150K/200K）、压缩后 system 重注入、摘要占位
- 2.2 意图检测升级：多意图、负向关键词、KB gate 解耦、LLM 兜底（默认关）

同 phase1：导入 src.agents.harness.* 会触发 src.agents.__init__ 构建默认 graph
（无 checkpointer，不连 DB），前置一个占位 DASHSCOPE_API_KEY 保证离线可运行。
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)

from src.agents.harness.runtime.middleware.request_gate_middleware import (
    RequestGateMiddleware,
    detect_intent,
    detect_intents,
)
from src.agents.harness.runtime.middleware.fitcream_summarization import (
    FitCreamSummarizationMiddleware,
    STRUCTURED_SUMMARY_PROMPT,
)
from src.agents.harness.orchestration.prompts.system import INTENT_PROMPTS


# ============================================================
# 2.2 意图检测升级
# ============================================================


class TestDetectIntents:
    def test_single_intent(self):
        assert detect_intents(HumanMessage(content="帮我制定减脂计划")) == ["plan_creation"]

    def test_multi_intent_ambiguity(self):
        # 「饮食计划」同时命中 plan_creation 与 diet_record
        intents = detect_intents(HumanMessage(content="帮我记录饮食计划"))
        assert intents[0] == "plan_creation"
        assert "diet_record" in intents

    def test_checkin(self):
        assert detect_intents(HumanMessage(content="今天打卡了")) == ["checkin"]

    def test_diet_record_not_stats(self):
        # 「记录」已从 stats_analysis 收敛，归 diet_record
        assert detect_intents(HumanMessage(content="帮我记录今天吃了什么")) == ["diet_record"]

    def test_knowledge_query(self):
        assert detect_intents(HumanMessage(content="什么是肌肥大")) == ["knowledge_query"]

    def test_general_chat_default(self):
        assert detect_intents(HumanMessage(content="你好呀")) == ["general_chat"]

    def test_negative_keyword_overrides(self):
        # 「取消我的计划」不应判为 plan_creation
        assert detect_intents(HumanMessage(content="取消我的计划")) == ["general_chat"]

    def test_detect_intent_backward_compat(self):
        assert detect_intent(HumanMessage(content="今天练了")) == "checkin"

    def test_image_meal_intent(self):
        msg = HumanMessage(
            content=[
                {"type": "text", "text": "这餐多少热量"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}},
            ]
        )
        assert detect_intents(msg) == ["meal_image_analysis"]

    def test_image_general_intent(self):
        msg = HumanMessage(
            content=[
                {"type": "text", "text": "帮我看看动作"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}},
            ]
        )
        assert detect_intents(msg) == ["image_analysis"]


class _StubClassifier:
    """可调用的轻量分类器替身。"""

    def __init__(self, label):
        self._label = label

    def invoke(self, prompt):
        return _Resp(self._label)


class _Resp:
    def __init__(self, text):
        self.text = text


def _run_intent(mw, messages) -> str:
    """跑一轮 wrap_model_call，返回最终合并进 system_message 的意图提示词文本。

    F1 迁移后 RequestGateMiddleware 走 wrap_model_call 临时注入（不落 checkpoint）。
    """
    from langchain.agents.middleware.types import ModelRequest

    request = ModelRequest(model=None, messages=messages)
    captured = {}

    def handler(req):
        captured["req"] = req
        return "ok"

    mw.wrap_model_call(request, handler)
    sys_msg = captured["req"].system_message
    return sys_msg.content if sys_msg else ""


class TestRequestGateMiddleware:
    def test_injects_multiple_intent_prompts(self, monkeypatch):
        from src.agents.harness.runtime.middleware import request_gate_middleware as rgm

        # 开启 KB，让 knowledge_query 也能注入（与 exercise_query 叠加）
        monkeypatch.setattr(rgm, "get_config_flag", lambda name, default=False: name == "kb_enabled")
        mw = RequestGateMiddleware()
        # 同时命中 knowledge_query 与 exercise_query（两个都有注入提示词文件）
        joined = _run_intent(mw, [HumanMessage(content="什么是正确姿势")])
        assert joined != ""
        assert INTENT_PROMPTS["knowledge_query"] in joined
        assert INTENT_PROMPTS["exercise_query"] in joined

    def test_skips_non_human(self):
        mw = RequestGateMiddleware()
        assert _run_intent(mw, [AIMessage(content="ok")]) == ""

    def test_kb_disabled_skips_knowledge_query(self, monkeypatch):
        from src.agents.harness.runtime.middleware import request_gate_middleware as rgm

        monkeypatch.setattr(rgm, "get_config_flag", lambda name, default=False: False)
        mw = RequestGateMiddleware()
        assert _run_intent(mw, [HumanMessage(content="什么是肌肥大")]) == ""

    def test_kb_enabled_injects_knowledge_query(self, monkeypatch):
        from src.agents.harness.runtime.middleware import request_gate_middleware as rgm

        monkeypatch.setattr(rgm, "get_config_flag", lambda name, default=False: name == "kb_enabled")
        mw = RequestGateMiddleware()
        joined = _run_intent(mw, [HumanMessage(content="什么是肌肥大")])
        assert joined != ""
        assert INTENT_PROMPTS["knowledge_query"] in joined

    def test_llm_fallback_disabled_by_default(self, monkeypatch):
        from src.agents.harness.runtime.middleware import request_gate_middleware as rgm

        # 默认：get_config_flag 对 intent_classify_llm 返回 False -> 不调用分类器
        called = []
        monkeypatch.setattr(rgm, "get_config_flag", lambda name, default=False: False)
        mw = RequestGateMiddleware(llm_classifier=_StubClassifier("checkin"))
        mw._classify_with_llm = lambda text: called.append(text) or "checkin"
        joined = _run_intent(mw, [HumanMessage(content="你好呀")])
        # general_chat 有专项提示词，仍会注入；但分类器不得被调用
        assert joined != ""
        assert called == []

    def test_llm_fallback_enabled_uses_classifier(self, monkeypatch):
        from src.agents.harness.runtime.middleware import request_gate_middleware as rgm

        monkeypatch.setattr(
            rgm,
            "get_config_flag",
            lambda name, default=False: name == "intent_classify_llm",
        )
        mw = RequestGateMiddleware(llm_classifier=_StubClassifier("checkin"))
        joined = _run_intent(mw, [HumanMessage(content="你好呀")])
        assert joined != ""
        assert INTENT_PROMPTS["checkin"] in joined

    def test_llm_fallback_ignores_unrecognized_label(self, monkeypatch):
        from src.agents.harness.runtime.middleware import request_gate_middleware as rgm

        monkeypatch.setattr(
            rgm,
            "get_config_flag",
            lambda name, default=False: name == "intent_classify_llm",
        )
        mw = RequestGateMiddleware(llm_classifier=_StubClassifier("不知道"))
        joined = _run_intent(mw, [HumanMessage(content="你好呀")])
        # 兜底标签不可识别 -> 回落 general_chat 提示词，而非 checkin
        assert joined != ""
        assert INTENT_PROMPTS["general_chat"] in joined
        assert INTENT_PROMPTS["checkin"] not in joined


# ============================================================
# 2.1 FitCream 会话压缩中间件
# ============================================================


class _StubSummaryModel:
    def __init__(self, text="## 用户目标\n无\n## 下一步\n无"):
        self._text = text

    def invoke(self, prompt, **kwargs):
        return _Resp(self._text)

    async def ainvoke(self, prompt, **kwargs):
        return _Resp(self._text)


def _build_messages(n_pairs: int = 20) -> list[AnyMessage]:
    msgs: list[AnyMessage] = []
    for i in range(n_pairs):
        msgs.append(HumanMessage(content=f"h{i}", id=f"h{i}"))
        msgs.append(
            AIMessage(
                content=f"a{i}",
                id=f"a{i}",
                tool_calls=[
                    {"name": "tool", "args": {}, "id": f"tc{i}", "type": "tool_call"}
                ],
            )
        )
        msgs.append(ToolMessage(content=f"r{i}", tool_call_id=f"tc{i}", id=f"r{i}"))
    return msgs


class TestFitCreamSummarization:
    def test_find_safe_cutoff_keeps_ai_tool_pairs(self):
        mw = FitCreamSummarizationMiddleware(
            _StubSummaryModel(), system_prompt="SYS", keep_messages=10
        )
        msgs = _build_messages(20)
        cutoff = mw._find_safe_cutoff(msgs, 10)
        # 60 条消息，保留 10 条 -> target 50，落在 r16(ToolMessage) 上，应回退到 a16
        assert cutoff == 49
        assert isinstance(msgs[cutoff], AIMessage)
        preserved = msgs[cutoff:]
        assert len(preserved) >= 10

    def test_no_trigger_below_threshold(self):
        mw = FitCreamSummarizationMiddleware(
            _StubSummaryModel(), system_prompt="SYS", keep_messages=10
        )
        state = {"messages": _build_messages(5)}
        assert mw.before_model(state, None) is None

    def test_before_model_reinjects_system_message(self):
        mw = FitCreamSummarizationMiddleware(
            _StubSummaryModel("## 用户目标\n减脂\n## 下一步\n无"),
            system_prompt="SYS-PROMPT",
            keep_messages=10,
        )
        mw._should_summarize = lambda messages, total_tokens: True
        state = {"messages": _build_messages(20)}
        result = mw.before_model(state, None)
        assert result is not None

        # D8：RemoveMessage(ALL) 后重注入系统提示词 SystemMessage
        assert any(isinstance(m, RemoveMessage) for m in result["messages"])
        assert isinstance(result["messages"][1], SystemMessage)
        assert result["messages"][1].content == "SYS-PROMPT"

        # 摘要占位（lc_source=summarization）存在且含摘要
        summary_msgs = [
            m
            for m in result["messages"]
            if getattr(m, "additional_kwargs", {}).get("lc_source") == "summarization"
        ]
        assert len(summary_msgs) == 1
        assert "减脂" in summary_msgs[0].content
        # 保留尾条仍存在
        assert any(getattr(m, "id", None) == "h19" for m in result["messages"])

    async def test_abefore_model_async(self):
        mw = FitCreamSummarizationMiddleware(
            _StubSummaryModel("## 下一步\n继续"),
            system_prompt="SYS",
            keep_messages=10,
        )
        mw._should_summarize = lambda messages, total_tokens: True
        state = {"messages": _build_messages(20)}
        result = await mw.abefore_model(state, None)
        assert result is not None
        assert isinstance(result["messages"][1], SystemMessage)
        summary_msgs = [
            m
            for m in result["messages"]
            if getattr(m, "additional_kwargs", {}).get("lc_source") == "summarization"
        ]
        assert len(summary_msgs) == 1
        assert "继续" in summary_msgs[0].content

    def test_dynamic_threshold(self, monkeypatch):
        import src.agents.harness.runtime.middleware.fitcream_summarization as fsm

        mw = FitCreamSummarizationMiddleware(None)
        # D2：plan_design 200K，其余 150K
        monkeypatch.setattr(
            fsm, "get_config_flag", lambda name, default=False: name == "plan_design"
        )
        assert mw._threshold() == 200_000
        monkeypatch.setattr(fsm, "get_config_flag", lambda name, default=False: False)
        assert mw._threshold() == 150_000

    def test_summary_prompt_uses_fitness_sections(self):
        captured = {}

        class CapturingModel(_StubSummaryModel):
            def invoke(self, prompt, **kwargs):
                captured["prompt"] = prompt
                return super().invoke(prompt, **kwargs)

        mw = FitCreamSummarizationMiddleware(
            CapturingModel("## 下一步\n继续"),
            system_prompt="SYS",
            keep_messages=10,
        )
        mw._should_summarize = lambda messages, total_tokens: True
        mw.before_model({"messages": _build_messages(20)}, None)
        # D4：健身域 7 节摘要提示词被使用
        assert "## 用户目标" in captured["prompt"]
        assert "## 待办队列进度" in captured["prompt"]
        assert STRUCTURED_SUMMARY_PROMPT.startswith("<role>")

    def test_memory_refinement_scheduled_after_summary(self, monkeypatch):
        # D3：压缩摘要生成后触发后台记忆提炼（同一中间件内 _schedule_memory_refinement）
        mw = FitCreamSummarizationMiddleware(
            _StubSummaryModel("## 下一步\n继续"), system_prompt="SYS", keep_messages=10
        )
        captured = {}

        def fake_schedule(summary):
            captured["summary"] = summary

        monkeypatch.setattr(mw, "_schedule_memory_refinement", fake_schedule)
        summary = mw._create_summary(_build_messages(5))
        assert summary == "## 下一步\n继续"
        assert captured["summary"] == "## 下一步\n继续"

    def test_memory_refinement_skipped_without_user_id(self, monkeypatch):
        # 无 user_id 时跳过记忆提炼（best-effort）
        import src.agents.harness.runtime.middleware.fitcream_summarization as fsm

        monkeypatch.setattr(fsm, "get_config_value", lambda name, default=None: None)
        mw = FitCreamSummarizationMiddleware(
            _StubSummaryModel("ok"), system_prompt="SYS", keep_messages=10
        )
        summary = mw._create_summary(_build_messages(5))
        assert summary == "ok"

    def test_memory_refinement_registers_shared_instance(self, monkeypatch):
        # 共享实例注册：shutdown_agent 排空后台记忆任务依赖 get_shared_memory_middleware
        import src.agents.harness.runtime.middleware.fitcream_summarization as fsm

        monkeypatch.setattr(fsm, "get_config_value", lambda name, default=None: None)
        mw = FitCreamSummarizationMiddleware(
            _StubSummaryModel("ok"), system_prompt="SYS", keep_messages=10
        )
        assert fsm.get_shared_memory_middleware() is mw
        assert mw._processing_users == set()
