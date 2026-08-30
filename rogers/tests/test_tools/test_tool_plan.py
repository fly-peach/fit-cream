"""
计划类工具测试（管理员账户）

覆盖：create_plan / create_diet_plan / list_plans / get_plan_detail / update_plan /
delete_plan / add_plan_day / remove_plan_day / sync_plan_day / add_exercise /
update_exercise / remove_exercise。验证逐日设计落库（days）与模板生成两条路径。
"""
import uuid

from tests.util import create_exercise

from src.agents.harness.tools.plan.plan_tools import (
    add_exercise_tool,
    add_plan_day_tool,
    create_diet_plan_tool,
    create_plan_tool,
    delete_plan_tool,
    get_plan_detail_tool,
    list_plans_tool,
    remove_exercise_tool,
    remove_plan_day_tool,
    sync_plan_day_tool,
    update_exercise_tool,
    update_plan_tool,
)
from src.agents.harness.tools.user.user_tools import update_user_profile_tool


def _day(exercise_id=None, custom_name=None, day_of_week=1):
    ex = {}
    if exercise_id:
        ex["exercise_id"] = str(exercise_id)
    else:
        ex["custom_name"] = custom_name or "俯卧撑"
    ex.update({"exercise_type": "strength", "sets": 3, "reps": 12})
    return {
        "day_of_week": day_of_week,
        "focus": "胸",
        "rest_seconds": 60,
        "exercises": [ex],
    }


async def _seed_profile(agent_config):
    await update_user_profile_tool.ainvoke(
        {"height_cm": 178, "weight_kg": 72, "birth_date": "1995-05-20", "gender": "male", "goal": "lose_fat"},
        config=agent_config,
    )


async def test_list_plans_empty(agent_config):
    res = await list_plans_tool.ainvoke({}, config=agent_config)
    assert res["success"] is True
    assert res["total"] == 0
    assert res["plans"] == []


async def test_create_plan_with_days(admin, db_session, agent_config):
    ex = await create_exercise(db_session, name="杠铃卧推")
    res = await create_plan_tool.ainvoke(
        {
            "goal": "gain_muscle",
            "days_per_week": 3,
            "difficulty": "beginner",
            "name": "增肌计划",
            "weeks": 4,
            "days": [_day(exercise_id=ex.id)],
        },
        config=agent_config,
    )
    assert res["success"] is True, res
    assert res["mode"] == "days"
    assert res["plan"]["name"] == "增肌计划"
    assert res["plan"]["goal"] == "gain_muscle"
    plan_id = res["plan"]["id"]

    lst = await list_plans_tool.ainvoke({}, config=agent_config)
    assert lst["total"] == 1
    assert lst["plans"][0]["id"] == plan_id

    detail = await get_plan_detail_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    assert detail["success"] is True
    assert detail["plan"]["id"] == plan_id
    assert len(detail["plan"]["days"]) == 1


async def test_create_plan_missing_exercise_rejected(admin, db_session, agent_config):
    res = await create_plan_tool.ainvoke(
        {
            "goal": "lose_fat",
            "days_per_week": 3,
            "days": [_day(exercise_id=uuid.uuid4())],
        },
        config=agent_config,
    )
    assert res["success"] is False
    assert "动作库中不存在" in res["error"]


async def test_create_plan_template_mode(admin, db_session, agent_config):
    await _seed_profile(agent_config)
    res = await create_plan_tool.ainvoke(
        {"goal": "lose_fat", "days_per_week": 3, "difficulty": "beginner"},
        config=agent_config,
    )
    assert res["success"] is True, res
    assert res["mode"] == "template_generated"
    assert res["plan"]["id"]


async def test_create_diet_plan_with_days(agent_config):
    res = await create_diet_plan_tool.ainvoke(
        {
            "goal": "lose_fat",
            "target_calories": 1800,
            "days": [
                {
                    "day_of_week": 1,
                    "focus": "减脂日",
                    "meals": [
                        {"meal_type": "breakfast", "food_name": "燕麦", "calories": 300},
                        {"meal_type": "lunch", "food_name": "鸡胸肉", "calories": 500},
                    ],
                }
            ],
        },
        config=agent_config,
    )
    assert res["success"] is True, res
    assert res["mode"] == "days"
    assert res["diet_plan"]["target_calories"] == 1800
    assert len(res["diet_plan"]["days"][0]["meals"]) == 2


async def test_update_plan(admin, db_session, agent_config):
    ex = await create_exercise(db_session, name="杠铃卧推")
    created = await create_plan_tool.ainvoke(
        {"goal": "gain_muscle", "days_per_week": 3, "name": "增肌计划", "days": [_day(exercise_id=ex.id)]},
        config=agent_config,
    )
    plan_id = created["plan"]["id"]

    res = await update_plan_tool.ainvoke(
        {"plan_id": plan_id, "name": "新名字", "difficulty": "intermediate"},
        config=agent_config,
    )
    assert res["success"] is True
    assert res["plan_name"] == "新名字"

    detail = await get_plan_detail_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    assert detail["plan"]["name"] == "新名字"
    assert detail["plan"]["difficulty"] == "intermediate"


async def test_add_remove_plan_day(admin, db_session, agent_config):
    ex = await create_exercise(db_session, name="杠铃卧推")
    created = await create_plan_tool.ainvoke(
        {"goal": "gain_muscle", "days_per_week": 3, "name": "p", "days": [_day(exercise_id=ex.id, day_of_week=1)]},
        config=agent_config,
    )
    plan_id = created["plan"]["id"]

    added = await add_plan_day_tool.ainvoke(
        {"plan_id": plan_id, "day_of_week": 3, "focus": "背"},
        config=agent_config,
    )
    assert added["success"] is True
    assert added["day_of_week"] == 3

    detail = await get_plan_detail_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    assert {d["day_of_week"] for d in detail["plan"]["days"]} == {1, 3}

    removed = await remove_plan_day_tool.ainvoke(
        {"plan_id": plan_id, "day_of_week": 3},
        config=agent_config,
    )
    assert removed["success"] is True

    detail = await get_plan_detail_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    assert {d["day_of_week"] for d in detail["plan"]["days"]} == {1}


async def test_sync_plan_day(admin, db_session, agent_config):
    ex = await create_exercise(db_session, name="杠铃卧推")
    created = await create_plan_tool.ainvoke(
        {"goal": "gain_muscle", "days_per_week": 3, "name": "p", "days": [_day(exercise_id=ex.id, day_of_week=1)]},
        config=agent_config,
    )
    plan_id = created["plan"]["id"]

    res = await sync_plan_day_tool.ainvoke(
        {"plan_id": plan_id, "source_day_of_week": 1, "target_day_of_week": 5},
        config=agent_config,
    )
    assert res["success"] is True
    # 注意：工具返回的 plan 可能未刷新出新训练日（关系集合陈旧），以 DB 实况为准
    detail = await get_plan_detail_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    days = {d["day_of_week"]: d for d in detail["plan"]["days"]}
    assert 1 in days and 5 in days
    assert len(days[5]["exercises"]) == 1
    assert days[5]["focus"] == "胸"


async def test_add_update_remove_exercise(admin, db_session, agent_config):
    ex = await create_exercise(db_session, name="杠铃卧推")
    created = await create_plan_tool.ainvoke(
        {"goal": "gain_muscle", "days_per_week": 3, "name": "p", "days": [_day(exercise_id=ex.id)]},
        config=agent_config,
    )
    plan_id = created["plan"]["id"]
    detail0 = await get_plan_detail_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    day_id = detail0["plan"]["days"][0]["id"]

    added = await add_exercise_tool.ainvoke(
        {"plan_day_id": day_id, "custom_name": "引体向上", "sets": 3, "reps": 8},
        config=agent_config,
    )
    assert added["success"] is True

    detail = await get_plan_detail_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    day = detail["plan"]["days"][0]
    assert len(day["exercises"]) == 2
    ex_item = next(e for e in day["exercises"] if e["custom_name"] == "引体向上")
    ex_item_id = ex_item["id"]

    updated = await update_exercise_tool.ainvoke(
        {"exercise_id": ex_item_id, "sets": 4, "weight_kg": 40},
        config=agent_config,
    )
    assert updated["success"] is True, updated
    detail = await get_plan_detail_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    updated_item = next(e for e in detail["plan"]["days"][0]["exercises"] if e["id"] == ex_item_id)
    assert updated_item["sets"] == 4
    assert updated_item["weight_kg"] == 40
    # 局部更新不得清空未指定的字段（sort_order / reps / custom_name 等）
    assert updated_item["reps"] == 8
    assert updated_item["custom_name"] == "引体向上"

    removed = await remove_exercise_tool.ainvoke({"exercise_id": ex_item_id}, config=agent_config)
    assert removed["success"] is True
    detail = await get_plan_detail_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    assert len(detail["plan"]["days"][0]["exercises"]) == 1


async def test_delete_plan_archives(admin, db_session, agent_config):
    ex = await create_exercise(db_session, name="杠铃卧推")
    created = await create_plan_tool.ainvoke(
        {"goal": "gain_muscle", "days_per_week": 3, "name": "p", "days": [_day(exercise_id=ex.id)]},
        config=agent_config,
    )
    plan_id = created["plan"]["id"]

    res = await delete_plan_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    assert res["success"] is True

    detail = await get_plan_detail_tool.ainvoke({"plan_id": plan_id}, config=agent_config)
    assert detail["plan"]["status"] == "archived"


async def test_create_plan_without_user(admin, db_session):
    """无身份时工具返回结构化错误（HITL 之外的身份兜底）。"""
    from langchain_core.runnables import RunnableConfig

    res = await create_plan_tool.ainvoke(
        {"goal": "lose_fat", "days_per_week": 3},
        config=RunnableConfig(),
    )
    assert res["success"] is False
