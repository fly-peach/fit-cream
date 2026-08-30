"""
用户类工具测试（管理员账户）

覆盖：get_user_profile_tool / update_user_profile_tool / 更新健身画像 /
get_user_summary_tool。验证设计契约（返回结构）与数据库读写均正常。
"""
from src.agents.harness.tools.user.summary_tools import get_user_summary_tool
from src.agents.harness.tools.user.user_tools import (
    get_user_profile_tool,
    update_user_profile_tool,
    更新健身画像,
)


async def test_get_user_profile(agent_config):
    res = await get_user_profile_tool.ainvoke({}, config=agent_config)
    assert res["success"] is True
    profile = res["profile"]
    assert isinstance(profile, dict)
    assert "height_cm" in profile and "weight_kg" in profile
    assert "goal" in profile and "gender" in profile


async def test_update_user_profile_then_get(agent_config):
    res = await update_user_profile_tool.ainvoke(
        {
            "name": "管理员",
            "height_cm": 178,
            "weight_kg": 72,
            "birth_date": "1995-05-20",
            "gender": "male",
            "goal": "gain_muscle",
        },
        config=agent_config,
    )
    assert res["success"] is True
    profile = res["profile"]
    assert profile["height_cm"] == 178
    assert profile["weight_kg"] == 72
    assert profile["goal"] == "gain_muscle"

    got = await get_user_profile_tool.ainvoke({}, config=agent_config)
    assert got["profile"]["height_cm"] == 178
    assert got["profile"]["gender"] == "male"


async def test_update_partial_keeps_other_fields(agent_config):
    """只更新体重时，身高等其他已落库字段不能被清空（exclude_unset 回归）。"""
    await update_user_profile_tool.ainvoke(
        {"height_cm": 175, "weight_kg": 70, "gender": "male"},
        config=agent_config,
    )
    res = await update_user_profile_tool.ainvoke(
        {"weight_kg": 68},
        config=agent_config,
    )
    assert res["success"] is True
    profile = res["profile"]
    assert profile["weight_kg"] == 68
    assert profile["height_cm"] == 175
    assert profile["gender"] == "male"


async def test_update_fitness_profile(agent_config):
    res = await 更新健身画像.ainvoke(
        {
            "medical_history": "无",
            "injuries": "膝盖旧伤",
            "training_experience": "beginner",
            "strength_level": "beginner",
            "weekly_frequency": "3-4",
            "sleep_quality": "normal",
            "equipment": "健身房",
            "diet_preferences": "少油",
            "meals_per_day": "3",
        },
        config=agent_config,
    )
    assert res["success"] is True
    assert res["intake"]["injuries"] == "膝盖旧伤"
    assert res["intake"]["weekly_frequency"] == "3-4"


async def test_update_fitness_profile_partial_keeps_others(agent_config):
    """健身画像同样不能因局部更新而清空其它已填字段。"""
    await 更新健身画像.ainvoke(
        {"injuries": "腰背不适", "training_experience": "intermediate"},
        config=agent_config,
    )
    res = await 更新健身画像.ainvoke(
        {"training_experience": "advanced"},
        config=agent_config,
    )
    assert res["success"] is True
    summary = await get_user_summary_tool.ainvoke({}, config=agent_config)
    intake = summary["intake"]
    assert intake["training_experience"] == "advanced"
    assert intake["injuries"] == "腰背不适"


async def test_get_user_summary_shape(agent_config):
    res = await get_user_summary_tool.ainvoke({}, config=agent_config)
    assert res["success"] is True
    assert isinstance(res["body"], dict)
    assert "missing_fields" in res
    assert "profile_complete" in res
    assert "intake_dimensions" in res
    assert "intake" in res
    # 管理员默认未填身体数据 -> 缺失字段非空
    for f in ("height_cm", "weight_kg", "birth_date", "gender", "goal"):
        assert f in res["missing_fields"], f"{f} 应计入缺失字段"


async def test_get_user_summary_complete_after_update(agent_config):
    await update_user_profile_tool.ainvoke(
        {"height_cm": 178, "weight_kg": 72, "birth_date": "1995-05-20", "gender": "male", "goal": "lose_fat"},
        config=agent_config,
    )
    res = await get_user_summary_tool.ainvoke({}, config=agent_config)
    assert res["success"] is True
    assert res["profile_complete"] is True
    assert res["missing_fields"] == []
    assert res["body"]["height_cm"] == 178
