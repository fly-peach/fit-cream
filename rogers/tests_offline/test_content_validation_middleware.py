"""
ContentValidationMiddleware 单测（不依赖真实 LLM、不 import 生产 DB）。

覆盖 AI 信息校验中间件的确定性兜底逻辑（F1 迁移后经 wrap_model_call 临时注入）：
- 非 plan-design 流程（无队列快照）零开销跳过
- 最新消息非 HumanMessage 跳过
- 确认类兜底：确认大纲/当日设计但对应展示工具从未被调用 -> 注入补展示约束
- 阶段类兜底：大纲/逐日设计/装配审批阶段 -> 注入「走展示工具、禁止正文写表格」约束
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

import pytest

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.harness.runtime.middleware import plan_queue_middleware as pqm
from src.agents.harness.runtime.middleware.content_validation_middleware import (
    ContentValidationMiddleware,
)


@pytest.fixture(autouse=True)
def _clear_queue_snapshot_cache():
    """每个用例前清空队列快照缓存（单测里 messages 列表短命、对象 id 可能复用）。"""
    pqm._queue_snapshot_cache.clear()
    yield
    pqm._queue_snapshot_cache.clear()


def _run(mw: ContentValidationMiddleware, messages: list) -> str:
    """跑一轮 wrap_model_call，返回最终合并进 system_message 的提示词文本。

    未注入时 handler 收到原始 request（system_message 为 None），返回空串。
    """
    request = ModelRequest(model=None, messages=messages)
    captured = {}

    def handler(req):
        captured["req"] = req
        return "ok"

    result = mw.wrap_model_call(request, handler)
    assert result == "ok"
    sys_msg = captured["req"].system_message
    return sys_msg.content if sys_msg else ""


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


def _outline_ai() -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "present_outline_tool",
                "args": {"title": "大纲", "strategy": "三分化", "days": []},
                "id": "c2",
                "type": "tool_call",
            }
        ],
    )


def _day_ai() -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "present_day_design_tool",
                "args": {"item_id": "design-day-1", "day_design": {}},
                "id": "c3",
                "type": "tool_call",
            }
        ],
    )


OUTLINE_STAGE_TODOS = [
    {"id": "intake-health", "title": "健康", "status": "completed"},
    {"id": "analyze", "title": "分析", "status": "in_progress"},
    {"id": "outline", "title": "大纲", "status": "pending"},
]
DAY_STAGE_TODOS = [
    {"id": "outline", "title": "大纲", "status": "completed"},
    {"id": "design-day-1", "title": "周一", "status": "in_progress"},
]
ASSEMBLE_STAGE_TODOS = [
    {"id": "design-day-1", "title": "周一", "status": "completed"},
    {"id": "assemble", "title": "装配", "status": "in_progress"},
]
INTAKE_STAGE_TODOS = [
    {"id": "intake-health", "title": "健康", "status": "in_progress"},
]


ROADMAP_STAGE_TODOS = [
    {"id": "baseline", "title": "基线", "status": "completed"},
    {"id": "roadmap", "title": "路线图", "status": "in_progress"},
    {"id": "analyze", "title": "分析", "status": "pending"},
]


def _roadmap_ai() -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "present_roadmap_tool",
                "args": {"title": "薄肌闯关", "description": "", "stages": []},
                "id": "c4",
                "type": "tool_call",
            }
        ],
    )


class TestContentValidationMiddleware:
    def test_no_queue_returns_none(self):
        mw = ContentValidationMiddleware()
        msgs = [HumanMessage(content="你好"), AIMessage(content="嗨")]
        assert _run(mw, msgs) == ""

    def test_last_not_human_returns_none(self):
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(OUTLINE_STAGE_TODOS),
            _outline_ai(),
        ]
        assert _run(mw, msgs) == ""

    def test_intake_stage_no_guard(self):
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(INTAKE_STAGE_TODOS),
            HumanMessage(content="我填好了"),
        ]
        assert _run(mw, msgs) == ""

    def test_outline_confirm_without_tool_injects_guard(self):
        # 用户确认大纲，但历史从未调用 present_outline_tool -> 必须补展示，不得直接接受
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(OUTLINE_STAGE_TODOS),
            HumanMessage(content="[确认大纲]"),
        ]
        text = _run(mw, msgs)
        assert text != ""
        assert "尚未调用 present_outline_tool" in text

    def test_outline_confirm_with_tool_no_confirm_guard(self):
        # 已调用过 present_outline_tool，确认类兜底不再触发
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(OUTLINE_STAGE_TODOS),
            _outline_ai(),
            HumanMessage(content="[确认大纲]"),
        ]
        text = _run(mw, msgs)
        assert "尚未调用 present_outline_tool" not in text

    def test_day_confirm_without_tool_injects_guard(self):
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(DAY_STAGE_TODOS),
            HumanMessage(content="[确认当日设计: design-day-1]"),
        ]
        text = _run(mw, msgs)
        assert text != ""
        assert "尚未调用 present_day_design_tool" in text

    def test_outline_stage_injects_stage_guard(self):
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(OUTLINE_STAGE_TODOS),
            HumanMessage(content="继续"),
        ]
        text = _run(mw, msgs)
        assert text != ""
        assert "大纲必须通过 present_outline_tool" in text

    def test_day_design_stage_injects_stage_guard(self):
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(DAY_STAGE_TODOS),
            HumanMessage(content="继续"),
        ]
        text = _run(mw, msgs)
        assert text != ""
        assert "present_day_design_tool" in text

    def test_assemble_stage_injects_stage_guard(self):
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(ASSEMBLE_STAGE_TODOS),
            HumanMessage(content="继续"),
        ]
        text = _run(mw, msgs)
        assert text != ""
        assert "present_plan_tool" in text

    def test_roadmap_confirm_without_tool_injects_guard(self):
        # 用户确认路线图，但历史从未调用 present_roadmap_tool -> 必须补展示
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(ROADMAP_STAGE_TODOS),
            HumanMessage(content="[确认路线图]"),
        ]
        text = _run(mw, msgs)
        assert text != ""
        assert "尚未调用 present_roadmap_tool" in text

    def test_roadmap_confirm_with_tool_no_confirm_guard(self):
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(ROADMAP_STAGE_TODOS),
            _roadmap_ai(),
            HumanMessage(content="[确认路线图]"),
        ]
        text = _run(mw, msgs)
        assert "尚未调用 present_roadmap_tool" not in text

    def test_roadmap_stage_injects_stage_guard(self):
        mw = ContentValidationMiddleware()
        msgs = [
            HumanMessage(content="帮我设计计划"),
            _queue_ai(ROADMAP_STAGE_TODOS),
            HumanMessage(content="继续"),
        ]
        text = _run(mw, msgs)
        assert text != ""
        assert "present_roadmap_tool" in text
        assert "禁止在回复正文里输出路线图表格" in text
