"""
Agent 优化计划离线单测（对应 .kilo/plans/plan-agent-optimize.md）。

不依赖 LLM、不连 PostgreSQL：
- P0-1 语义记忆版本链：store_semantic 先 flush 落 INSERT 再赋 superseded_by；
  _trim_semantic_by_category 删除前先清 superseded_by 引用
- P0-2 思考内容不下发：chat.py SSE 不再发 thinking 事件 / thought step，
  但 token 正常下发
- P1-3 会话压缩：以真实 usage input_tokens 触发（count_tokens_approximately
  低估中文/JSON 导致 198k 不触发），压缩后清空陈旧 usage 防 thrash
- P1-4 已撤销（2026-08-29 用户决策）：plan_design 会话同样开思考，
  无 DS key 时任何会话都不覆盖默认模型
- 「思考中」状态事件在 on_chat_model_start 发出（不依赖 reasoning_content）

记忆模块依赖 llama_index（→torch），个别环境导入失败时用 skip 兜底。
"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage  # noqa: E402

try:
    from src.agents.harness.runtime.memory.store import MemoryStore
    from src.agents.models.memory import SemanticMemory

    _MEMORY_AVAILABLE = True
    _MEMORY_IMPORT_ERR = None
except Exception as _e:  # noqa: BLE001 本地缺 torch/llama_index 依赖时跳过记忆用例
    _MEMORY_AVAILABLE = False
    _MEMORY_IMPORT_ERR = _e

_MEMORY_SKIP = pytest.mark.skipif(
    not _MEMORY_AVAILABLE, reason=f"memory 模块不可导入: {_MEMORY_IMPORT_ERR}"
)


# ============================================================
# P0-1 语义记忆版本链（Bug 7/8）
# ============================================================


class _FakeResult:
    def __init__(self, row):
        self.row = row

    def scalar_one_or_none(self):
        return self.row


class _FakeScalars:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _FakeStoreSession:
    """记录 store_semantic 的操作顺序：advisory_lock → select → add → flush → commit。"""

    def __init__(self, existing):
        self.existing = existing
        self.order = []
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, stmt, params=None):
        if type(stmt).__name__ == "TextClause":
            self.order.append("advisory_lock")
            return _FakeResult(None)
        self.order.append("select_existing")
        return _FakeResult(self.existing)

    def add(self, obj):
        self.order.append("add")
        self.added.append(obj)

    async def flush(self):
        self.order.append("flush")

    async def commit(self):
        self.order.append("commit")


class _FakeTrimSession:
    """记录 _trim_semantic_by_category 的执行语句：先 Update（清引用）再 Delete。"""

    def __init__(self, total, ids):
        self.total = total
        self.ids = ids
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def scalar(self, stmt):
        return self.total

    async def scalars(self, stmt):
        return _FakeScalars(self.ids)

    async def execute(self, stmt):
        from sqlalchemy.sql.dml import Delete, Update

        self.statements.append(
            Update if isinstance(stmt, Update) else Delete if isinstance(stmt, Delete) else None
        )
        return None

    async def commit(self):
        return None


def _bare_store() -> MemoryStore:
    """构造不触发 __init__（不建引擎/不加载 embedding）的 MemoryStore。"""
    store = object.__new__(MemoryStore)
    store.embed_model = None
    store.semantic_cap_each = 0  # 避免 store_semantic 触达 trim（本用例不测 trim）
    store.semantic_capped_categories = ("preference", "fact", "rule", "status")
    return store


class TestSemanticVersionChain:
    @_MEMORY_SKIP
    async def test_flush_before_fk_assignment(self):
        existing = SemanticMemory(
            id=uuid.uuid4(),
            user_id="u",
            subject="用户",
            predicate="偏好",
            object="旧值",
            status="active",
            version=1,
        )
        fs = _FakeStoreSession(existing)
        store = _bare_store()
        store.async_session = lambda: fs

        rid = await store.store_semantic(
            user_id="u",
            subject="用户",
            predicate="偏好",
            object="新值",
            category="insight",  # 非 capped，跳过 trim
        )

        # 关键回归：add 之后必须先 flush 落 INSERT，再赋 existing.superseded_by
        assert "add" in fs.order and "flush" in fs.order
        assert fs.order.index("flush") < fs.order.index("commit"), "flush 必须发生在 commit 前"
        # 版本链建立：旧版 status=superseded，superseded_by 指向新行
        assert existing.status == "superseded"
        assert existing.superseded_by == fs.added[0].id
        assert existing.superseded_by is not None
        assert fs.added[0].version == 2
        assert rid == fs.added[0].id

    @_MEMORY_SKIP
    async def test_first_insert_no_supersede(self):
        fs = _FakeStoreSession(None)  # 无已有 active 三元组
        store = _bare_store()
        store.async_session = lambda: fs

        rid = await store.store_semantic(
            user_id="u", subject="用户", predicate="目标", object="减脂",
            category="insight",
        )
        assert rid == fs.added[0].id
        assert fs.added[0].version == 1
        assert fs.added[0].status == "active"
        assert fs.order.index("flush") < fs.order.index("commit")


class TestSemanticTrim:
    @_MEMORY_SKIP
    async def test_clears_superseded_refs_before_delete(self):
        from sqlalchemy.sql.dml import Delete, Update

        ids = [uuid.uuid4() for _ in range(4)]
        fs = _FakeTrimSession(total=19, ids=ids)  # 上限 15 → 超额 4
        store = _bare_store()
        store.async_session = lambda: fs

        n = await store._trim_semantic_by_category("u", "fact", 15)

        assert n == 4
        assert len(fs.statements) == 2
        assert fs.statements[0] is Update, "删除前必须先清 superseded_by 引用（RESTRICT 外键）"
        assert fs.statements[1] is Delete


# ============================================================
# P0-2 思考内容不下发前端（Bug 9）
# ============================================================


class _FakeAgent:
    def __init__(self, events, approvals_state=None):
        self.events = events
        self.approvals_state = approvals_state or SimpleNamespace(tasks=())
        self.checkpointer = None

    async def astream_events(self, *a, **k):
        for ev in self.events:
            yield ev

    async def aget_state(self, config):
        return self.approvals_state


async def _noop(*a, **k):
    return None


class TestThinkingNotStreamed:
    async def test_no_thinking_or_thought_step_events(self, monkeypatch):
        import app.routers.chat as chat_mod

        events = [
            {
                "event": "on_chat_model_stream",
                "data": {
                    "chunk": AIMessageChunk(
                        content="",
                        additional_kwargs={"reasoning_content": "这是模型内部权衡…落库，但可以作为记忆？"}
                    )
                },
                "run_id": "r1",
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": AIMessageChunk(content="正式回复")},
                "run_id": "r1",
            },
            {
                "event": "on_chat_model_end",
                "data": {"output": None},
                "run_id": "r1",
            },
        ]
        saved = {}

        async def fake_save(db, user_id, thread_id, role, content, metadata=None):
            saved["metadata"] = metadata or {}

        monkeypatch.setattr(chat_mod.ConversationService, "save_message", fake_save)
        monkeypatch.setattr(chat_mod, "_upsert_thread_usage", _noop)
        monkeypatch.setattr(chat_mod, "_upsert_user_token_usage", _noop)

        gen = chat_mod._run_agent_sse(
            _FakeAgent(events),
            {"configurable": {}},
            {},
            thread_id="t1",
            user_id="u1",
            user=SimpleNamespace(id="u1", name="测试"),
            stop_event=asyncio.Event(),
            stream_db=None,
        )
        sse_text = ""
        async for s in gen:
            sse_text += s

        # 思考内容不下发：无 thought step、reasoning 文本不泄漏；
        # 但思考阶段发「思考中」状态事件（无内容，供前端显示提示而非干等）
        assert '"type": "thought"' not in sse_text
        assert "内部权衡" not in sse_text
        assert "event: thinking" in sse_text
        # 正常 token / step(reply) / done 仍下发
        assert "event: token" in sse_text
        assert "正式回复" in sse_text
        assert "event: done" in sse_text
        # 落库 steps 无 thought 节点（验证「steps 无 thought」）
        steps = saved["metadata"].get("steps") or []
        assert all(s.get("type") != "thought" for s in steps)
        assert any(s.get("type") == "reply" for s in steps)
        # full_thinking 仍累积存 metadata（机器调试用）
        assert saved["metadata"].get("thinking")
        assert "内部权衡" in saved["metadata"]["thinking"]

    async def test_thinking_status_on_model_start_without_reasoning(self, monkeypatch):
        """模型调用无 reasoning_content 产出时（如 DeepSeek BYOK / 未来关思考场景），
        on_chat_model_start 仍发「思考中」状态事件，生成期间前端不干等。"""
        import app.routers.chat as chat_mod

        events = [
            {"event": "on_chat_model_start", "data": {}, "run_id": "r1"},
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": AIMessageChunk(content="")},
                "run_id": "r1",
            },
            {"event": "on_chat_model_end", "data": {"output": None}, "run_id": "r1"},
            {"event": "on_tool_start", "name": "present_form_tool", "data": {"input": {}}, "run_id": "t1"},
            {
                "event": "on_tool_end",
                "name": "present_form_tool",
                "data": {"output": "ok"},
                "run_id": "t1",
            },
        ]

        async def fake_save(db, user_id, thread_id, role, content, metadata=None):
            pass

        monkeypatch.setattr(chat_mod.ConversationService, "save_message", fake_save)
        monkeypatch.setattr(chat_mod, "_upsert_thread_usage", _noop)
        monkeypatch.setattr(chat_mod, "_upsert_user_token_usage", _noop)

        gen = chat_mod._run_agent_sse(
            _FakeAgent(events),
            {"configurable": {}},
            {},
            thread_id="t1",
            user_id="u1",
            user=SimpleNamespace(id="u1", name="测试"),
            stop_event=asyncio.Event(),
            stream_db=None,
        )
        sse_text = ""
        async for s in gen:
            sse_text += s

        # 无 reasoning 时 thinking 状态事件仍从 on_chat_model_start 发出
        assert "event: thinking" in sse_text
        # 且事件无内容（仅状态标记）
        assert "event: thinking\ndata: {\"content\": \"\"}" in sse_text


# ============================================================
# P1-3 会话压缩以真实 usage 触发
# ============================================================


def _mw():
    from src.agents.harness.runtime.middleware.structured_summarization import (
        StructuredSummarizationMiddleware,
    )

    return StructuredSummarizationMiddleware(model=None, trigger_tokens=100_000)


def _msgs(usage_input: int | None) -> list:
    msgs = [HumanMessage(content="消息内容" * 8) for _ in range(14)]
    if usage_input is None:
        msgs.append(AIMessage(content="答"))
    else:
        msgs.append(
            AIMessage(
                content="答",
                usage_metadata={
                    "input_tokens": usage_input,
                    "output_tokens": 120,
                    "total_tokens": usage_input + 120,
                },
            )
        )
    return msgs


class TestSummarizationRealUsageTrigger:
    def test_triggers_on_real_input_above_threshold(self):
        # 真实 input_tokens 150k，count_tokens_approximately 对中文严重低估（可能 <100k）
        plan = _mw()._summarize_plan({"messages": _msgs(150_000)})
        assert plan is not None
        assert plan[3] == 150_000

    def test_no_trigger_below_threshold(self):
        assert _mw()._summarize_plan({"messages": _msgs(50_000)}) is None

    def test_fallback_approx_when_no_usage(self):
        # 无 usage_metadata：回退近似估算，短上下文不触发
        assert _mw()._summarize_plan({"messages": _msgs(None)}) is None

    def test_preserved_usage_sanitized_after_compress(self):
        # 压缩后保留消息里的陈旧超大 input_tokens 必须被清空，防每轮重复压缩
        mw = _mw()
        plan = mw._summarize_plan({"messages": _msgs(150_000)})
        assert plan is not None
        for m in plan[1]:
            usage = getattr(m, "usage_metadata", None)
            if isinstance(usage, dict):
                assert "input_tokens" not in usage
        # 压缩后的新列表（保留段）再判定时不再按陈旧 usage 触发
        assert mw._summarize_plan({"messages": list(plan[1])}) is None


# ============================================================
# P1-4 已撤销：plan_design 会话同样开思考（2026-08-29 用户决策）
# 无 DS key 时任何会话都不覆盖默认模型（qwen 默认开思考）
# ============================================================


class _FakeModelRequest:
    def __init__(self, model=None):
        self._model = model

    def override(self, model=None, **kwargs):
        return _FakeModelRequest(model=model)

    @property
    def model(self):
        return self._model


class TestModelRoutingNoKeyPassthrough:
    def test_no_key_never_overrides_model(self, monkeypatch):
        """无 DS key 时直接放行默认模型（不关思考、不路由覆盖）。"""
        import src.agents.harness.runtime.middleware.model_routing as mr

        monkeypatch.setattr(
            mr, "get_config_value",
            lambda name, default=None: None if name == "deepseek_api_key" else default,
        )
        called = {"resolve": False}

        def fake_resolve(*, user_ds_key=None, enable_thinking=True):
            called["resolve"] = True
            return "x"

        monkeypatch.setattr(mr, "resolve_chat_model", fake_resolve)
        handled = []

        def handler(request):
            handled.append(request)
            return "ok"

        assert mr.ModelRoutingMiddleware().wrap_model_call(_FakeModelRequest(), handler) == "ok"
        assert called["resolve"] is False, "无 DS key 时不应覆盖默认模型"
        assert handled[0].model is None
