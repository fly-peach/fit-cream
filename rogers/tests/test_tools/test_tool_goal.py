"""
目标闯关工具测试（管理员账户）

覆盖：get_goal_knowledge_tool / create_roadmap_tool / get_roadmap_tool /
record_baseline_tool / check_milestone_tool。验证知识层目录、路线图确定性校验落库、
基线/复测记录与出关判定。
"""
import pytest
from pydantic import ValidationError

from src.agents.harness.tools.goal.goal_knowledge_tools import get_goal_knowledge_tool
from src.agents.harness.tools.goal.roadmap_tools import (
    check_milestone_tool,
    create_roadmap_tool,
    get_roadmap_tool,
    record_baseline_tool,
)

MILESTONE_STATUSES = ("active", "locked", "achieved")


@pytest.fixture
async def goal_seed(db_session):
    """在测试 schema 灌入目标闯关知识层参考数据（幂等，与启动期 seed 同源）。"""
    from src.fitme.services.goal_knowledge_seed import seed_goal_knowledge

    await seed_goal_knowledge(db_session)
    await db_session.commit()
    return True


def _stages():
    return [
        {
            "stage_index": 1,
            "title": "基础力量适应",
            "description": "建立动作模式",
            "exit_criteria": [{"metric": "bench_kg", "op": ">=", "value": 40}],
            "expected_weeks": 4,
            "training_focus": "全身基础力量",
        },
        {
            "stage_index": 2,
            "title": "力量进阶",
            "description": "提升卧推",
            "exit_criteria": [{"metric": "bench_kg", "op": ">=", "value": 60}],
            "expected_weeks": 8,
            "training_focus": "胸部推举强化",
        },
    ]


async def test_get_goal_knowledge(goal_seed, agent_config):
    res = await get_goal_knowledge_tool.ainvoke({}, config=agent_config)
    assert res["success"] is True, res
    assert isinstance(res["archetypes"], list) and res["archetypes"], "原型目录不应为空（需种子数据）"
    assert isinstance(res["strength_standards"], list) and res["strength_standards"]
    assert isinstance(res["progress_rates"], list) and res["progress_rates"]
    assert isinstance(res["safety_limits"], list) and res["safety_limits"]
    assert res["gender"] in ("male", "female")
    assert "note" in res


async def test_get_goal_knowledge_by_key(goal_seed, agent_config):
    res = await get_goal_knowledge_tool.ainvoke({"archetype_key": "lean_aesthetic"}, config=agent_config)
    assert res["success"] is True, res
    assert res["archetypes"]
    assert all(a["key"] == "lean_aesthetic" for a in res["archetypes"])


async def test_get_goal_knowledge_bad_key(goal_seed, agent_config):
    res = await get_goal_knowledge_tool.ainvoke({"archetype_key": "不存在的原型"}, config=agent_config)
    assert res["success"] is False


async def test_get_roadmap_empty(agent_config):
    res = await get_roadmap_tool.ainvoke({}, config=agent_config)
    assert res["success"] is True
    assert res["has_roadmap"] is False
    assert res["roadmap"] is None


async def test_create_and_get_roadmap(goal_seed, agent_config):
    res = await create_roadmap_tool.ainvoke(
        {
            "archetype_key": "lean_aesthetic",
            "title": "薄肌有线条 · 2 关",
            "description": "循序渐进",
            "target_metrics": [{"metric": "bench_kg", "op": ">=", "value": 60, "unit": "kg"}],
            "horizon_months": 3,
            "stages": _stages(),
            "experience_level": "beginner",
        },
        config=agent_config,
    )
    assert res["success"] is True, res
    roadmap_id = res["roadmap_id"]
    assert res["milestones"]
    assert all(m["status"] in MILESTONE_STATUSES for m in res["milestones"])
    assert res["milestones"][0]["status"] == "active"

    got = await get_roadmap_tool.ainvoke({}, config=agent_config)
    assert got["success"] is True
    assert got["has_roadmap"] is True
    assert got["roadmap"]["id"] == roadmap_id
    assert got["current_milestone"]["stage_index"] == 1


async def test_create_roadmap_invalid_stages_rejected(goal_seed, agent_config):
    """跨关力量指标单调递减（60 -> 40）应被确定性校验拒绝，返回结构化错误而非落库。"""
    res = await create_roadmap_tool.ainvoke(
        {
            "archetype_key": "lean_aesthetic",
            "title": "t",
            "stages": [
                {
                    "stage_index": 1,
                    "title": "s1",
                    "exit_criteria": [{"metric": "bench_kg", "op": ">=", "value": 60}],
                    "expected_weeks": 4,
                },
                {
                    "stage_index": 2,
                    "title": "s2",
                    "exit_criteria": [{"metric": "bench_kg", "op": ">=", "value": 40}],
                    "expected_weeks": 8,
                },
            ],
            "experience_level": "beginner",
        },
        config=agent_config,
    )
    assert res["success"] is False
    assert "单调" in res["error"] or "增量" in res["error"] or "校验" in res["error"]


async def test_record_baseline_then_check_milestone(goal_seed, agent_config):
    await create_roadmap_tool.ainvoke(
        {
            "archetype_key": "lean_aesthetic",
            "title": "t",
            "stages": _stages(),
            "experience_level": "beginner",
        },
        config=agent_config,
    )

    res = await record_baseline_tool.ainvoke(
        {
            "lifts": [{"lift": "bench", "value": 30, "test_type": "1rm"}],
            "body_fat_pct": 20.0,
            "waist_cm": 80,
            "weight_kg": 72,
        },
        config=agent_config,
    )
    assert res["success"] is True, res
    assert "bench" in res["recorded"]
    assert "milestone_progress" in res

    # 30 天内重复记录同动作应幂等跳过
    again = await record_baseline_tool.ainvoke(
        {"lifts": [{"lift": "bench", "value": 32, "test_type": "1rm"}]},
        config=agent_config,
    )
    assert again["success"] is True
    assert "bench" in again["skipped"]

    check = await check_milestone_tool.ainvoke({}, config=agent_config)
    assert check["success"] is True
    assert check["has_roadmap"] is True
    assert "achieved" in check
    assert "criteria" in check
    assert isinstance(check["criteria"], list)


async def test_check_milestone_without_roadmap(agent_config):
    res = await check_milestone_tool.ainvoke({}, config=agent_config)
    assert res["success"] is True
    assert res["has_roadmap"] is False


async def test_record_baseline_invalid_lift(agent_config):
    """非法 lift 由 args_schema 枚举兜底，工具调用前即校验失败。"""
    with pytest.raises(ValidationError):
        await record_baseline_tool.ainvoke(
            {"lifts": [{"lift": "bench_press_wrong", "value": 30}]},
            config=agent_config,
        )
