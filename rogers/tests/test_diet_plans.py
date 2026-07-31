"""饮食计划路由 /api/diet-plans/* 测试"""
from tests.util import biz_code, unwrap

DIET_PLAN_PAYLOAD = {
    "name": "减脂饮食",
    "target_calories": 1800,
    "goal": "lose_fat",
    "days": [
        {
            "day_of_week": 1,
            "focus": "低碳",
            "meals": [{"meal_type": "breakfast", "food_name": "燕麦", "calories": 300}],
        }
    ],
}


async def test_create_diet_plan(user_client):
    data = unwrap(await user_client.post("/api/diet-plans", json=DIET_PLAN_PAYLOAD))
    assert data["name"] == "减脂饮食"
    assert data["status"] == "active"
    assert len(data["days"]) == 1
    assert data["days"][0]["meals"][0]["food_name"] == "燕麦"


async def test_create_diet_plan_invalid_goal(user_client):
    resp = await user_client.post("/api/diet-plans", json={"name": "x", "goal": "xyz"})
    assert resp.status_code == 422


async def test_list_and_active_diet_plan(user_client):
    created = unwrap(await user_client.post("/api/diet-plans", json=DIET_PLAN_PAYLOAD))
    lst = unwrap(await user_client.get("/api/diet-plans"))
    assert lst["total"] == 1
    active = unwrap(await user_client.get("/api/diet-plans/active"))
    assert active["id"] == created["id"]


async def test_get_update_diet_plan(user_client):
    created = unwrap(await user_client.post("/api/diet-plans", json=DIET_PLAN_PAYLOAD))
    dpid = created["id"]

    got = unwrap(await user_client.get(f"/api/diet-plans/{dpid}"))
    assert got["id"] == dpid

    updated = unwrap(
        await user_client.put(f"/api/diet-plans/{dpid}", json={"name": "新饮食计划"})
    )
    assert updated["name"] == "新饮食计划"


async def test_diet_day_and_meal_operations(user_client):
    created = unwrap(await user_client.post("/api/diet-plans", json=DIET_PLAN_PAYLOAD))
    dpid = created["id"]

    # 添加饮食日
    updated = unwrap(
        await user_client.post(f"/api/diet-plans/{dpid}/days", json={"day_of_week": 2})
    )
    assert len(updated["days"]) == 2
    day2 = next(d for d in updated["days"] if d["day_of_week"] == 2)
    day2_id = day2["id"]

    # 更新饮食日
    updated = unwrap(
        await user_client.put(f"/api/diet-plans/days/{day2_id}", json={"focus": "高蛋白"})
    )
    day2 = next(d for d in updated["days"] if d["id"] == day2_id)
    assert day2["focus"] == "高蛋白"

    # 添加餐食
    updated = unwrap(
        await user_client.post(
            f"/api/diet-plans/days/{day2_id}/meals",
            json={"meal_type": "lunch", "food_name": "米饭", "calories": 400},
        )
    )
    day2 = next(d for d in updated["days"] if d["id"] == day2_id)
    assert len(day2["meals"]) == 1
    meal_id = day2["meals"][0]["id"]

    # 更新餐食
    updated = unwrap(
        await user_client.put(f"/api/diet-plans/meals/{meal_id}", json={"calories": 450})
    )
    day2 = next(d for d in updated["days"] if d["id"] == day2_id)
    assert day2["meals"][0]["calories"] == 450

    # 删除餐食
    updated = unwrap(await user_client.delete(f"/api/diet-plans/meals/{meal_id}"))
    day2 = next(d for d in updated["days"] if d["id"] == day2_id)
    assert len(day2["meals"]) == 0


async def test_delete_diet_plan_archives(user_client):
    created = unwrap(await user_client.post("/api/diet-plans", json=DIET_PLAN_PAYLOAD))
    dpid = created["id"]

    unwrap(await user_client.delete(f"/api/diet-plans/{dpid}"))

    # 归档后不再是活跃计划
    active = unwrap(await user_client.get("/api/diet-plans/active"))
    assert active is None
