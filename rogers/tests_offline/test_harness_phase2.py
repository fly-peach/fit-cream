"""
阶段二：模型上下文质量不变量单测（不依赖真实 LLM、不 import 生产 DB）。

覆盖：
- 2.1 结构化增量压缩中间件：safe cutoff、触发判定、增量摘要、conversation_summary 通道
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

from src.agents.harness.runtime.middleware.intent_middleware import (
    IntentMiddleware,
    detect_intent,
    detect_intents,
)
from src.agents.harness.runtime.middleware.structured_summarization import (
    StructuredSummarizationMiddleware,
    _is_summary_message,
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


class TestIntentMiddleware:
    def test_injects_multiple_intent_prompts(self, monkeypatch):
        from src.agents.harness.runtime.middleware import intent_middleware as im

        # 开启 KB，让 knowledge_query 也能注入（与 exercise_query 叠加）
        monkeypatch.setattr(im, "get_config_flag", lambda name, default=False: name == "kb_enabled")
        mw = IntentMiddleware()
        # 同时命中 knowledge_query 与 exercise_query（两个都有注入提示词文件）
        state = {"messages": [HumanMessage(content="什么是正确姿势")]}
        result = mw.before_model(state, None)
        assert result is not None
        sys_msgs = [m for m in result["messages"] if isinstance(m, SystemMessage)]
        assert len(sys_msgs) == 1
        joined = sys_msgs[0].content
        assert INTENT_PROMPTS["knowledge_query"] in joined
        assert INTENT_PROMPTS["exercise_query"] in joined

    def test_skips_non_human(self):
        mw = IntentMiddleware()
        state = {"messages": [AIMessage(content="ok")]}
        assert mw.before_model(state, None) is None

    def test_kb_disabled_skips_knowledge_query(self, monkeypatch):
        from src.agents.harness.runtime.middleware import intent_middleware as im

        monkeypatch.setattr(im, "get_config_flag", lambda name, default=False: False)
        mw = IntentMiddleware()
        state = {"messages": [HumanMessage(content="什么是肌肥大")]}
        assert mw.before_model(state, None) is None

    def test_kb_enabled_injects_knowledge_query(self, monkeypatch):
        from src.agents.harness.runtime.middleware import intent_middleware as im

        monkeypatch.setattr(im, "get_config_flag", lambda name, default=False: name == "kb_enabled")
        mw = IntentMiddleware()
        state = {"messages": [HumanMessage(content="什么是肌肥大")]}
        result = mw.before_model(state, None)
        assert result is not None
        assert INTENT_PROMPTS["knowledge_query"] in result["messages"][0].content

    def test_llm_fallback_disabled_by_default(self, monkeypatch):
        from src.agents.harness.runtime.middleware import intent_middleware as im

        # 默认：get_config_flag 对 intent_classify_llm 返回 False -> 不调用分类器
        called = []
        monkeypatch.setattr(im, "get_config_flag", lambda name, default=False: False)
        mw = IntentMiddleware(llm_classifier=_StubClassifier("checkin"))
        mw._classify_with_llm = lambda text: called.append(text) or "checkin"
        state = {"messages": [HumanMessage(content="你好呀")]}
        result = mw.before_model(state, None)
        # general_chat 有专项提示词，仍会注入；但分类器不得被调用
        assert result is not None
        assert called == []

    def test_llm_fallback_enabled_uses_classifier(self, monkeypatch):
        from src.agents.harness.runtime.middleware import intent_middleware as im

        monkeypatch.setattr(
            im,
            "get_config_flag",
            lambda name, default=False: name == "intent_classify_llm",
        )
        mw = IntentMiddleware(llm_classifier=_StubClassifier("checkin"))
        state = {"messages": [HumanMessage(content="你好呀")]}
        result = mw.before_model(state, None)
        assert result is not None
        assert INTENT_PROMPTS["checkin"] in result["messages"][0].content

    def test_llm_fallback_ignores_unrecognized_label(self, monkeypatch):
        from src.agents.harness.runtime.middleware import intent_middleware as im

        monkeypatch.setattr(
            im,
            "get_config_flag",
            lambda name, default=False: name == "intent_classify_llm",
        )
        mw = IntentMiddleware(llm_classifier=_StubClassifier("不知道"))
        state = {"messages": [HumanMessage(content="你好呀")]}
        result = mw.before_model(state, None)
        # 兜底标签不可识别 -> 回落 general_chat 提示词，而非 checkin
        assert result is not None
        assert INTENT_PROMPTS["general_chat"] in result["messages"][0].content
        assert INTENT_PROMPTS["checkin"] not in result["messages"][0].content


# ============================================================
# 2.1 结构化增量压缩
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


class TestStructuredSummarization:
    def test_find_safe_cutoff_keeps_ai_tool_pairs(self):
        mw = StructuredSummarizationMiddleware(
            _StubSummaryModel(), trigger_tokens=1, keep_messages=10
        )
        msgs = _build_messages(20)
        cutoff = mw._find_safe_cutoff(msgs)
        # 60 条消息，保留 10 条 -> target 50，落在 r16(ToolMessage) 上，应回退到 a16
        assert cutoff == 49
        assert isinstance(msgs[cutoff], AIMessage)
        preserved = msgs[cutoff:]
        assert len(preserved) >= 10

    def test_no_trigger_below_threshold(self):
        mw = StructuredSummarizationMiddleware(
            _StubSummaryModel(), trigger_tokens=10**9, keep_messages=10
        )
        state = {"messages": _build_messages(5)}
        assert mw._summarize_plan(state) is None

    def test_before_model_returns_summary_and_channel(self):
        mw = StructuredSummarizationMiddleware(
            _StubSummaryModel("## 用户目标\n减脂\n## 下一步\n无"),
            trigger_tokens=1,
            keep_messages=10,
        )
        state = {"messages": _build_messages(20)}
        result = mw.before_model(state, None)
        assert result is not None
        assert result["conversation_summary"] == "## 用户目标\n减脂\n## 下一步\n无"

        # 消息替换：RemoveMessage + 摘要占位 + 保留尾条
        assert any(isinstance(m, RemoveMessage) for m in result["messages"])
        summary_msgs = [
            m for m in result["messages"] if _is_summary_message(m)
        ]
        assert len(summary_msgs) == 1
        assert "减脂" in summary_msgs[0].content
        # 保留尾条仍存在
        assert any(getattr(m, "id", None) == "h19" for m in result["messages"])

    async def test_abefore_model_async(self):
        mw = StructuredSummarizationMiddleware(
            _StubSummaryModel("## 下一步\n继续"),
            trigger_tokens=1,
            keep_messages=10,
        )
        state = {"messages": _build_messages(20)}
        result = await mw.abefore_model(state, None)
        assert result is not None
        assert result["conversation_summary"] == "## 下一步\n继续"

    def test_incremental_uses_prev_summary(self):
        captured = {}

        class CapturingModel(_StubSummaryModel):
            def invoke(self, prompt, **kwargs):
                captured["prompt"] = prompt
                return super().invoke(prompt, **kwargs)

        mw = StructuredSummarizationMiddleware(
            CapturingModel("## 下一步\n继续"), trigger_tokens=1, keep_messages=10
        )
        state = {"messages": _build_messages(20), "conversation_summary": "旧摘要内容"}
        mw.before_model(state, None)
        # 旧摘要被并入提示词（增量更新）
        assert "旧摘要内容" in captured["prompt"]

    def test_prev_summary_message_filtered_from_prompt(self):
        captured = {}

        class CapturingModel(_StubSummaryModel):
            def invoke(self, prompt, **kwargs):
                captured["prompt"] = prompt
                return super().invoke(prompt, **kwargs)

        mw = StructuredSummarizationMiddleware(
            CapturingModel("ok"), trigger_tokens=1, keep_messages=10
        )
        summary_msg = HumanMessage(
            content="以下是截至目前的对话摘要：\n\n旧摘要",
            additional_kwargs={"lc_source": "summarization"},
        )
        msgs = [summary_msg, *(_build_messages(20))]
        mw.before_model({"messages": msgs}, None)
        # 旧的摘要占位消息不应作为「新增对话」再喂入
        assert "以下是截至目前的对话摘要" not in captured["prompt"]
