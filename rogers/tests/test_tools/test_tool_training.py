"""
训练类工具测试（管理员账户）

覆盖：checkin_tool / get_streak_tool / get_exercises_tool / query_stats_tool。
验证动作匹配三级策略、打卡落库、连续天数、动作库检索与统计聚合。
"""
from tests.util import create_exercise

from src.agents.harness.tools.training.checkin_tools import checkin_tool, get_streak_tool
from src.agents.harness.tools.training.exercise_tools import get_exercises_tool
from src.agents.harness.tools.training.stats_tools import query_stats_tool


async def test_get_exercises_keyword(admin, db_session, agent_config):
    await create_exercise(db_session, name="杠铃卧推", muscle_group="chest", equipment="barbell")
    res = await get_exercises_tool.ainvoke({"keyword": "卧推"}, config=agent_config)
    assert res["success"] is True
    assert res["count"] >= 1
    names = [e["name"] for e in res["exercises"]]
    assert "杠铃卧推" in names


async def test_get_exercises_muscle_filter(admin, db_session, agent_config):
    await create_exercise(db_session, name="杠铃深蹲", muscle_group="legs", equipment="barbell")
    res = await get_exercises_tool.ainvoke({"muscle_group": "legs"}, config=agent_config)
    assert res["success"] is True
    assert res["count"] >= 1
    assert all(e["muscle_group"] == "legs" for e in res["exercises"])


async def test_get_exercises_no_match(agent_config):
    res = await get_exercises_tool.ainvoke({"keyword": "不存在的动作xyz"}, config=agent_config)
    assert res["success"] is True
    assert res["count"] == 0


async def test_checkin_with_library_exercise(admin, db_session, agent_config):
    await create_exercise(db_session, name="杠铃卧推")
    res = await checkin_tool.ainvoke(
        {
            "exercises": [{"name": "杠铃卧推", "sets_done": 3, "reps_done": 10, "weight_kg": 60}],
            "duration_min": 45,
            "mood": 4,
        },
        config=agent_config,
    )
    assert res["success"] is True
    assert res["checkin_id"]
    assert res["exercises_count"] == 1
    assert res["custom_actions"] is None

    streak = await get_streak_tool.ainvoke({}, config=agent_config)
    assert streak["success"] is True
    assert streak["current_streak"] >= 1


async def test_checkin_unmatched_returns_suggestions(admin, db_session, agent_config):
    await create_exercise(db_session, name="杠铃深蹲")
    res = await checkin_tool.ainvoke(
        {
            "exercises": [{"name": "深蹲架怪动作", "sets_done": 3, "reps_done": 10}],
            "duration_min": 30,
        },
        config=agent_config,
    )
    assert res["success"] is False
    assert "深蹲架怪动作" in res["unmatched"]
    assert isinstance(res["suggestions"], dict)


async def test_checkin_with_custom_allow(admin, db_session, agent_config):
    res = await checkin_tool.ainvoke(
        {
            "exercises": [{"name": "壶铃甩摆", "sets_done": 4, "reps_done": 12}],
            "duration_min": 30,
            "allow_custom": True,
        },
        config=agent_config,
    )
    assert res["success"] is True
    assert res["custom_actions"] == ["壶铃甩摆"]


async def test_checkin_invalid_date(agent_config):
    res = await checkin_tool.ainvoke(
        {
            "exercises": [{"name": "卧推", "sets_done": 3, "reps_done": 10}],
            "duration_min": 30,
            "checkin_date": "not-a-date",
        },
        config=agent_config,
    )
    assert res["success"] is False
    assert "日期格式无效" in res["error"]


async def test_get_streak_empty(agent_config):
    res = await get_streak_tool.ainvoke({}, config=agent_config)
    assert res["success"] is True
    assert res["current_streak"] == 0
    assert res["longest_streak"] == 0


async def test_query_stats_weekly(admin, db_session, agent_config):
    await create_exercise(db_session, name="杠铃卧推")
    await checkin_tool.ainvoke(
        {"exercises": [{"name": "杠铃卧推", "sets_done": 3, "reps_done": 10}], "duration_min": 45},
        config=agent_config,
    )
    res = await query_stats_tool.ainvoke({"period": "weekly"}, config=agent_config)
    assert res["success"] is True
    assert res["stats"]["total_workouts"] >= 1
    assert res["analysis"]


async def test_query_stats_all_empty(agent_config):
    res = await query_stats_tool.ainvoke({"period": "all"}, config=agent_config)
    assert res["success"] is True
    assert res["stats"]["total_workouts"] == 0
