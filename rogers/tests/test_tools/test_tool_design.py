"""
工具层设计完整性测试

不依赖业务数据，纯静态 + 最小调用验证：
- 所有导出工具具备 name/description/args_schema，名称无冲突
- 纯展示工具（present_* / queue / skill）调用成功且返回契约结构
- 缺用户身份时工具返回结构化错误而非抛异常（防 Agent 中断）
- 关键容错 schema（present_plan_tool.changes 等）接受模型字符串化的嵌套数组
"""
import inspect

import pytest
from langchain_core.runnables import RunnableConfig

import src.agents.harness.tools as tools_pkg

PURE_DISPLAY = {
    "present_plan_tool",
    "present_form_tool",
    "present_plan_queue_tool",
    "present_outline_tool",
    "present_day_design_tool",
    "update_plan_queue_item_tool",
    "present_roadmap_tool",
    "skill_load_tool",
}


def _all_tools():
    for name in tools_pkg.__all__:
        yield name, getattr(tools_pkg, name)


@pytest.mark.parametrize("name,tool", list(_all_tools()))
def test_tool_metadata(name, tool):
    from langchain_core.tools import BaseTool

    assert isinstance(tool, BaseTool), f"{name} 不是 BaseTool"
    assert getattr(tool, "name", ""), f"{name} 缺 name"
    desc = getattr(tool, "description", "") or ""
    assert desc.strip(), f"{name} 缺 description"
    schema = getattr(tool, "args_schema", None)
    assert schema is not None, f"{name} 缺 args_schema"
    # 工具主体应为 async 可调用（Agent 全异步）
    coro = getattr(tool, "coroutine", None) or getattr(tool, "func", None)
    assert coro is not None and inspect.iscoroutinefunction(coro), f"{name} 不是 async 工具"


def test_no_duplicate_tool_names():
    names = [n for n, _ in _all_tools()]
    assert len(names) == len(set(names)), f"工具名冲突: {names}"


async def test_skill_tool_loads_real_skill():
    """skill_load_tool 应能加载 harness/skills 下真实技能（设计闭环：catalog 可加载）。"""
    from src.agents.harness.tools.skill.skill_load_tool import skill_load_tool

    res = await skill_load_tool.ainvoke(
        {"skill_name": "plan-creation"}, config=RunnableConfig()
    )
    assert res["success"] is True
    assert res["content"]

    missing = await skill_load_tool.ainvoke(
        {"skill_name": "不存在的技能"}, config=RunnableConfig()
    )
    assert missing["success"] is False
    assert "available_skills" in missing


async def test_present_plan_tool():
    from src.agents.harness.tools.plan.present_plan_tool import present_plan_tool

    res = await present_plan_tool.ainvoke(
        {
            "title": "4 周增肌计划",
            "description": "每周 4 次力量训练",
            "content": "## 训练安排\n...",
        }
    )
    assert res == {"ok": True}


async def test_present_plan_tool_lenient_changes():
    """changes 被模型字符串化（'[{...}]'）时应容错解析，不炸调用。"""
    from src.agents.harness.tools.plan.present_plan_tool import present_plan_tool

    res = await present_plan_tool.ainvoke(
        {
            "title": "t",
            "description": "d",
            "content": "c",
            "changes": '[{"domain": "训练计划", "action": "新增", "target": "x", "detail": "y"}]',
        }
    )
    assert res == {"ok": True}


async def test_present_form_tool():
    from src.agents.harness.tools.plan.present_form_tool import present_form_tool

    res = await present_form_tool.ainvoke(
        {"form_id": "body_profile", "title": "补充基础数据", "description": "d", "fields": {"height_cm": 175}}
    )
    assert res == {"ok": True}


async def test_present_plan_queue_tool_lenient_todos():
    from src.agents.harness.tools.plan.plan_queue_tools import present_plan_queue_tool

    res = await present_plan_queue_tool.ainvoke(
        {
            "title": "计划设计",
            "todos": '[{"id": "intake-body", "title": "收集数据", "status": "pending"}]',
        }
    )
    assert res["ok"] is True


async def test_update_plan_queue_item_completed_all():
    from src.agents.harness.tools.plan.plan_queue_tools import update_plan_queue_item_tool

    res = await update_plan_queue_item_tool.ainvoke(
        {
            "item_id": "approve",
            "status": "completed",
            "queue": {
                "title": "q",
                "todos": [
                    {"id": "intake", "title": "收集", "status": "completed"},
                    {"id": "approve", "title": "审批", "status": "completed"},
                ],
            },
        }
    )
    assert res["ok"] is True
    assert "present_plan_tool" in res["next"]


async def test_present_outline_and_day_design():
    from src.agents.harness.tools.plan.plan_queue_tools import (
        present_day_design_tool,
        present_outline_tool,
    )

    outline = await present_outline_tool.ainvoke(
        {
            "title": "4 周计划 · 大纲",
            "strategy": "上下肢分化",
            "days": [
                {"day_of_week": 1, "focus": "胸+三头", "day_type": "strength"},
                {"day_of_week": 7, "focus": "休息", "day_type": "rest"},
            ],
        }
    )
    assert outline == {"ok": True}

    design = await present_day_design_tool.ainvoke(
        {
            "item_id": "design-day-1",
            "rationale": "新手友好",
            "day_design": {
                "day_of_week": 1,
                "focus": "胸+三头",
                "day_type": "strength",
                "exercises": [
                    {"name": "卧推", "custom_name": "卧推", "exercise_type": "strength", "sets": 3, "reps": 10}
                ],
            },
        }
    )
    assert design == {"ok": True}


async def test_present_roadmap_tool():
    from src.agents.harness.tools.goal.roadmap_tools import present_roadmap_tool

    res = await present_roadmap_tool.ainvoke(
        {
            "title": "薄肌有线条 · 3 关",
            "description": "d",
            "stages": [
                {"stage_index": 1, "title": "适应", "exit_criteria": [{"metric": "bench_kg", "op": ">=", "value": 40}], "expected_weeks": 4},
                {"stage_index": 2, "title": "进阶", "exit_criteria": [{"metric": "bench_kg", "op": ">=", "value": 60}], "expected_weeks": 8},
            ],
        }
    )
    assert res == {"ok": True}


async def test_user_required_tools_error_without_user():
    """依赖身份的工具在无 user_id 时应返回结构化错误，而非抛异常。"""
    from src.agents.harness.tools.training.checkin_tools import checkin_tool
    from src.agents.harness.tools.training.stats_tools import query_stats_tool
    from src.agents.harness.tools.plan.plan_tools import create_plan_tool
    from src.agents.harness.tools.user.user_tools import update_user_profile_tool
    from src.agents.harness.tools.diet.diet_tools import record_meal_tool
    from src.agents.harness.tools.goal.roadmap_tools import create_roadmap_tool
    from src.agents.harness.tools.knowledge.knowledge_tools import search_knowledge_base

    cases = [
        (checkin_tool, {"exercises": [{"name": "卧推", "sets_done": 3, "reps_done": 10}], "duration_min": 30}),
        (query_stats_tool, {}),
        (create_plan_tool, {"goal": "lose_fat", "days_per_week": 3}),
        (update_user_profile_tool, {"weight_kg": 70}),
        (record_meal_tool, {"meal_type": "lunch", "food_name": "米饭"}),
        (create_roadmap_tool, {
            "archetype_key": "lean_aesthetic",
            "title": "t",
            "stages": [
                {"stage_index": 1, "title": "s1", "exit_criteria": [{"metric": "bench_kg", "op": ">=", "value": 40}], "expected_weeks": 4},
                {"stage_index": 2, "title": "s2", "exit_criteria": [{"metric": "bench_kg", "op": ">=", "value": 60}], "expected_weeks": 8},
            ],
        }),
        (search_knowledge_base, {"query": "深蹲", "kb_enabled": True}),
    ]
    for tool, args in cases:
        res = await tool.ainvoke(args, config=RunnableConfig())
        assert isinstance(res, dict), tool.name
        assert res.get("success") is False, f"{tool.name} 缺身份时应失败: {res}"


def test_memory_tools_metadata():
    from src.agents.harness.tools.memory.memory_tools import create_memory_tools

    tools = create_memory_tools()
    names = [t.name for t in tools]
    assert len(names) == len(set(names))
    for t in tools:
        assert t.description
        assert getattr(t, "args_schema", None) is not None
