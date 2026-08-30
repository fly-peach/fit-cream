"""
饮食类工具测试（管理员账户）

覆盖：record_meal_tool / query_diet_summary_tool / manage_meal_tool /
set_nutrition_goals_tool。验证餐食落库、当日汇总、改删与营养目标写入。
"""
import pytest
from pydantic import ValidationError

from src.agents.harness.tools.diet.diet_tools import (
    manage_meal_tool,
    query_diet_summary_tool,
    record_meal_tool,
    set_nutrition_goals_tool,
)


async def test_record_meal(agent_config):
    res = await record_meal_tool.ainvoke(
        {"meal_type": "lunch", "food_name": "牛肉面", "calories": 600, "protein_g": 30},
        config=agent_config,
    )
    assert res["success"] is True, res
    meal = res["meal"]
    assert meal["food_name"] == "牛肉面"
    assert meal["calories"] == 600
    assert meal["meal_type"] == "lunch"
    assert meal["protein_g"] == 30


async def test_query_diet_summary_reflects_meal(agent_config):
    await record_meal_tool.ainvoke(
        {"meal_type": "breakfast", "food_name": "燕麦", "calories": 300, "protein_g": 10},
        config=agent_config,
    )
    await record_meal_tool.ainvoke(
        {"meal_type": "lunch", "food_name": "鸡胸肉", "calories": 500, "protein_g": 40},
        config=agent_config,
    )
    res = await query_diet_summary_tool.ainvoke({}, config=agent_config)
    assert res["success"] is True
    intake = res["intake"]
    assert intake["total_calories"] == 800
    assert intake["total_protein_g"] == 50
    assert res["date"]


async def test_query_diet_summary_empty(agent_config):
    res = await query_diet_summary_tool.ainvoke({}, config=agent_config)
    assert res["success"] is True
    assert res["intake"]["total_calories"] == 0


async def test_manage_meal_update(agent_config):
    created = await record_meal_tool.ainvoke(
        {"meal_type": "lunch", "food_name": "米饭", "calories": 400},
        config=agent_config,
    )
    meal_id = created["meal"]["id"]

    res = await manage_meal_tool.ainvoke(
        {"action": "update", "meal_id": meal_id, "calories": 500},
        config=agent_config,
    )
    assert res["success"] is True
    assert res["meal"]["calories"] == 500

    summary = await query_diet_summary_tool.ainvoke({}, config=agent_config)
    assert summary["intake"]["total_calories"] == 500


async def test_manage_meal_delete(agent_config):
    created = await record_meal_tool.ainvoke(
        {"meal_type": "dinner", "food_name": "沙拉", "calories": 200},
        config=agent_config,
    )
    meal_id = created["meal"]["id"]

    res = await manage_meal_tool.ainvoke(
        {"action": "delete", "meal_id": meal_id},
        config=agent_config,
    )
    assert res["success"] is True

    summary = await query_diet_summary_tool.ainvoke({}, config=agent_config)
    assert summary["intake"]["total_calories"] == 0


async def test_manage_meal_invalid_uuid(agent_config):
    res = await manage_meal_tool.ainvoke(
        {"action": "delete", "meal_id": "not-a-uuid"},
        config=agent_config,
    )
    assert res["success"] is False
    assert "无效的 meal_id" in res["error"]


async def test_manage_meal_no_fields(agent_config):
    created = await record_meal_tool.ainvoke(
        {"meal_type": "snack", "food_name": "坚果", "calories": 150},
        config=agent_config,
    )
    meal_id = created["meal"]["id"]
    res = await manage_meal_tool.ainvoke(
        {"action": "update", "meal_id": meal_id},
        config=agent_config,
    )
    assert res["success"] is False
    assert "未提供任何需要更新的字段" in res["error"]


async def test_set_nutrition_goals(agent_config):
    res = await set_nutrition_goals_tool.ainvoke(
        {"calorie_goal": 2000, "protein_goal_g": 140, "carbs_goal_g": 250, "fat_goal_g": 65},
        config=agent_config,
    )
    assert res["success"] is True
    assert res["goals"]["calorie_goal"] == 2000
    assert res["goals"]["protein_goal_g"] == 140


async def test_set_nutrition_goals_partial_keeps_others(agent_config):
    await set_nutrition_goals_tool.ainvoke(
        {"calorie_goal": 2000, "protein_goal_g": 140},
        config=agent_config,
    )
    res = await set_nutrition_goals_tool.ainvoke(
        {"protein_goal_g": 150},
        config=agent_config,
    )
    assert res["success"] is True
    assert res["goals"]["protein_goal_g"] == 150
    assert res["goals"]["calorie_goal"] == 2000


async def test_record_meal_invalid_type_rejected(agent_config):
    """非法 meal_type 由 args_schema 兜底，工具调用前即校验失败（防脏数据落库）。"""
    with pytest.raises(ValidationError):
        await record_meal_tool.ainvoke(
            {"meal_type": "brunch", "food_name": "x", "calories": 100},
            config=agent_config,
        )
