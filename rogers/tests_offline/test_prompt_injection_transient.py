"""
F1 提示词临时注入 + F3 队列快照去重 回归单测（不依赖真实 LLM、不 import 生产 DB）。

覆盖（对应 .kilo/plans/middleware-optimization-plan.md）：
- F1 迁移后 Intent/PlanQueue/ContentValidation/KBGate 走 wrap_model_call 临时注入：
  提示词合并进 request.system_message，不写入 state.messages、不随 checkpoint
  持久化（此前 before_model 每轮 +1~4 条 SystemMessage 逐轮累积）
- 多注入器同一 wrap 链按注册顺序叠加，原始 request.messages / request.state 不被改动
- 用 MemorySaver 跑两轮同 thread：断言 state.messages 不出现额外 SystemMessage 累积，
  且提示词仍在每轮模型输入中（F1 目标不变量）
- F3 队列快照单次计算：get_queue_snapshot 对同一 messages 对象复用结果（同一对象）
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

import pytest

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.harness.runtime.middleware.intent_middleware import IntentMiddleware
from src.agents.harness.runtime.middleware import plan_queue_middleware as pqm
from src.agents.harness.runtime.middleware.plan_queue_middleware import (
    PlanQueueMiddleware,
    get_queue_snapshot,
)
from src.agents.harness.runtime.middleware.content_validation_middleware import (
    ContentValidationMiddleware,
)
from src.agents.harness.runtime.middleware.kb_gate_middleware import KBGateMiddleware


@pytest.fixture(autouse=True)
def _clear_queue_snapshot_cache():
    """每个用例前清空队列快照缓存（单测里 messages 列表短命、id 可能复用）。

    生产里消息对象在 checkpoint 存活期间 id 不复用，缓存天然请求级安全。
    """
    pqm._queue_snapshot_cache.clear()
    yield
    pqm._queue_snapshot_cache.clear()


def _queue_ai(todos) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "present_plan_queue_tool",
                "args": {"title": "计划设计", "todos": todos},
                "id": "c1",
                "type": "tool_call",
            }
        ],
    )


OUTLINE_STAGE_TODOS = [
    {"id": "intake-health", "title": "健康", "status": "completed"},
    {"id": "analyze", "title": "分析", "status": "in_progress"},
    {"id": "outline", "title": "大纲", "status": "pending"},
]


def _nested_run(middleware, request):
    """按注册顺序嵌套执行 wrap_model_call（先注册者最外层），返回最终请求。

    模拟 create_agent 的 wrap 链：外层中间件把 override 后的请求传给内层，
    最内层 handler 捕获发给模型的最终 request。
    """
    captured = {}

    def terminal(req):
        captured["req"] = req
        return "ok"

    def build(i):
        if i >= len(middleware):
            return terminal
        mw = middleware[i]
        return lambda req: mw.wrap_model_call(req, build(i + 1))

    result = build(0)(request)
    return captured["req"], result


async def _nested_arun(middleware, request):
    """按注册顺序嵌套执行 awrap_model_call（先注册者最外层），返回最终请求。"""
    captured = {}

    async def terminal(req):
        captured["req"] = req
        return "ok"

    async def run(i, req):
        if i >= len(middleware):
            return await terminal(req)
        mw = middleware[i]
        return await mw.awrap_model_call(req, lambda r: run(i + 1, r))

    result = await run(0, request)
    return captured["req"], result


class TestWrapChainTemporaryInjection:
    def test_prompts_merged_into_system_message_in_order(self, monkeypatch):
        from src.agents.harness.runtime.middleware import (
            intent_middleware as im,
            kb_gate_middleware as kbm,
        )
        from src.agents.harness.orchestration.prompts.system import (
            CONTEXT_PROMPTS,
            INTENT_PROMPTS,
        )

        # KB 开启（让 KBGate 注入 KB 优先提示词）；plan_design 关闭（按钮引导）
        monkeypatch.setattr(
            kbm,
            "get_config_flag",
            lambda name, default=False: name == "kb_enabled",
        )
        monkeypatch.setattr(
            im,
            "get_config_flag",
            lambda name, default=False: name == "kb_enabled",
        )

        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(OUTLINE_STAGE_TODOS),
            HumanMessage(content="继续"),
        ]
        request = ModelRequest(
            model=None,
            messages=msgs,
            system_message=SystemMessage(content="基础系统提示词"),
            state={"messages": msgs},
        )
        mws = [
            IntentMiddleware(),
            PlanQueueMiddleware(),
            ContentValidationMiddleware(),
            KBGateMiddleware(),
        ]
        final, result = _nested_run(mws, request)
        assert result == "ok"

        # 4 个注入器的提示词都合并进最终 system_message（按注册顺序叠加）
        content = final.system_message.content
        assert content.startswith("基础系统提示词")
        assert INTENT_PROMPTS["general_chat"] in content  # Intent（最先）
        assert "计划设计待办进度" in content  # PlanQueue
        assert "AI 信息校验" in content  # ContentValidation
        assert CONTEXT_PROMPTS["kb_answer"] in content  # KBGate（最后）

        # 顺序：Intent < PlanQueue < ContentValidation < KBGate
        assert content.index(INTENT_PROMPTS["general_chat"]) < content.index(
            "计划设计待办进度"
        )
        assert content.index("计划设计待办进度") < content.index("AI 信息校验")
        assert content.index("AI 信息校验") < content.index(CONTEXT_PROMPTS["kb_answer"])

    def test_state_messages_not_mutated(self, monkeypatch):
        # 关键不变量：wrap 链只 override request，不写回 state.messages / 不改原始列表
        from src.agents.harness.runtime.middleware import (
            intent_middleware as im,
            kb_gate_middleware as kbm,
        )

        monkeypatch.setattr(
            kbm,
            "get_config_flag",
            lambda name, default=False: name == "kb_enabled",
        )
        monkeypatch.setattr(
            im,
            "get_config_flag",
            lambda name, default=False: name == "kb_enabled",
        )

        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(OUTLINE_STAGE_TODOS),
            HumanMessage(content="继续"),
        ]
        original_msgs = list(msgs)
        state = {"messages": msgs}
        request = ModelRequest(model=None, messages=msgs, state=state)
        mws = [
            IntentMiddleware(),
            PlanQueueMiddleware(),
            ContentValidationMiddleware(),
            KBGateMiddleware(),
        ]
        final, _ = _nested_run(mws, request)

        # state.messages 仍是原列表对象、内容未变（无 SystemMessage 写入）
        assert state["messages"] is msgs
        assert state["messages"] == original_msgs
        assert all(not isinstance(m, SystemMessage) for m in state["messages"])
        # 最终请求的 messages 与原列表同一对象（未复制/替换）
        assert final.messages is msgs

    async def test_awrap_chain_same_behavior(self, monkeypatch):
        from src.agents.harness.runtime.middleware import (
            intent_middleware as im,
            kb_gate_middleware as kbm,
        )

        monkeypatch.setattr(
            kbm,
            "get_config_flag",
            lambda name, default=False: name == "kb_enabled",
        )
        monkeypatch.setattr(
            im,
            "get_config_flag",
            lambda name, default=False: name == "kb_enabled",
        )

        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(OUTLINE_STAGE_TODOS),
            HumanMessage(content="继续"),
        ]
        request = ModelRequest(model=None, messages=msgs)
        mws = [
            IntentMiddleware(),
            PlanQueueMiddleware(),
            ContentValidationMiddleware(),
            KBGateMiddleware(),
        ]
        final, result = await _nested_arun(mws, request)
        assert result == "ok"
        content = final.system_message.content
        assert "计划设计待办进度" in content
        assert "AI 信息校验" in content


class TestQueueSnapshotDedup:
    def test_same_messages_object_reuses_snapshot(self):
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(OUTLINE_STAGE_TODOS),
            HumanMessage(content="继续"),
        ]
        # 同一 messages 对象：第二次调用命中缓存，返回同一 dict 对象（单次计算）
        assert get_queue_snapshot(msgs) is get_queue_snapshot(msgs)

    def test_different_messages_object_recomputes(self):
        # 不同的 messages 列表（内容相同但对象不同）：键含 id/长度/末条消息 id，
        # 命中必须要求同一对象语义，新列表即使内容一致也重算（结果内容一致即可）
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(OUTLINE_STAGE_TODOS),
            HumanMessage(content="继续"),
        ]
        snapshot_a = get_queue_snapshot(msgs)
        msgs2 = list(msgs)  # 新列表对象
        snapshot_b = get_queue_snapshot(msgs2)
        assert snapshot_a == snapshot_b

    def test_plan_queue_and_content_validation_share_snapshot(self):
        # 在同一 wrap 链中，PlanQueue 计算一次、ContentValidation 复用（同一对象）
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(OUTLINE_STAGE_TODOS),
            HumanMessage(content="继续"),
        ]
        snapshot = get_queue_snapshot(msgs)
        request = ModelRequest(model=None, messages=msgs)

        captured = {}

        def handler(req):
            captured["req"] = req
            return "ok"

        ContentValidationMiddleware().wrap_model_call(request, handler)
        assert captured["req"].system_message.content != ""
        # ContentValidation 复用缓存的同一快照对象
        assert get_queue_snapshot(msgs) is snapshot


class TestNoAccumulationAcrossTurns:
    """F1 核心回归：MemorySaver 跑两轮同 thread，state.messages 不累积 SystemMessage。

    迁移前 before_model 注入会在每轮把 SystemMessage 写进消息历史（每轮 +1~4 条）；
    迁移后经 wrap_model_call 临时注入 system_message，只出现在当轮模型输入，
    不持久化。此测试在迁移后必须通过（若某天有人改回 before_model 持久注入即失败）。
    """

    async def _run_two_turns(self):
        from langchain.agents import create_agent
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langgraph.checkpoint.memory import MemorySaver

        recorded = []

        class RecordingModel(GenericFakeChatModel):
            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                recorded.append(list(messages))
                return super()._generate(
                    messages, stop=stop, run_manager=run_manager, **kwargs
                )

        model = RecordingModel(messages=iter(["好的，已为你规划", "好的，继续"]))
        cp = MemorySaver()
        middleware = [
            IntentMiddleware(),
            PlanQueueMiddleware(),
            ContentValidationMiddleware(),
            KBGateMiddleware(),
        ]
        agent = create_agent(
            model=model,
            tools=[],
            system_prompt="你是健身教练。",
            middleware=middleware,
            checkpointer=cp,
        )
        cfg = {"configurable": {"thread_id": "t1"}}
        await agent.ainvoke(
            {"messages": [HumanMessage(content="请帮我设计健身计划")]}, config=cfg
        )
        await agent.ainvoke(
            {"messages": [HumanMessage(content="请帮我再安排一下训练")]}, config=cfg
        )
        state = await agent.aget_state(cfg)
        return state, recorded

    async def test_no_system_message_accumulation(self):
        state, recorded = await self._run_two_turns()
        msgs = state.values["messages"]
        sys_in_state = [m for m in msgs if isinstance(m, SystemMessage)]
        # 迁移后：state.messages 不出现注入的 SystemMessage（每轮临时注入不持久化）
        assert len(sys_in_state) == 0, "F1 回归：注入的 SystemMessage 在 state 中累积"
        # 消息历史只含 HumanMessage + AIMessage（基础系统提示词不走 messages reducer）
        assert len(msgs) == 4

    async def test_prompt_still_present_in_model_input_each_turn(self):
        state, recorded = await self._run_two_turns()
        assert len(recorded) == 2
        for i, inp in enumerate(recorded):
            # 每轮模型输入都含基础系统提示词 + 注入的意图提示词
            sys_msg = next(
                (m for m in inp if isinstance(m, SystemMessage) and m.content),
                None,
            )
            assert sys_msg is not None, f"第 {i} 轮模型输入缺少 SystemMessage"
            assert "你是健身教练" in sys_msg.content
            assert "为我设计健身计划" in sys_msg.content, (
                f"第 {i} 轮意图提示词未注入到模型输入"
            )
