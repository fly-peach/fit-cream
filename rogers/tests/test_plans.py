"""训练计划路由 /api/plans/* 测试"""
from tests.util import auth_headers, biz_code, create_user, unwrap

PLAN_PAYLOAD = {
    "name": "减脂计划",
    "goal": "lose_fat",
    "difficulty": "beginner",
    "weeks": 4,
    "days": [
        {
            "day_of_week": 1,
            "focus": "胸",
            "rest_seconds": 60,
            "exercises": [{"custom_name": "俯卧撑", "sets": 3, "reps": 12}],
        }
    ],
}


async def test_create_plan(user_client):
    data = unwrap(await user_client.post("/api/plans", json=PLAN_PAYLOAD))
    assert data["name"] == "减脂计划"
    assert data["status"] == "active"
    assert len(data["days"]) == 1
    assert data["days"][0]["exercises"][0]["exercise_name"] == "俯卧撑"


async def test_create_plan_invalid_goal(user_client):
    resp = await user_client.post("/api/plans", json={"name": "x", "goal": "xyz"})
    assert resp.status_code == 422


async def test_list_and_active_plan(user_client):
    created = unwrap(await user_client.post("/api/plans", json=PLAN_PAYLOAD))
    lst = unwrap(await user_client.get("/api/plans"))
    assert lst["total"] == 1
    active = unwrap(await user_client.get("/api/plans/active"))
    assert active["id"] == created["id"]


async def test_list_plans_status_filter(user_client):
    unwrap(await user_client.post("/api/plans", json=PLAN_PAYLOAD))
    active = unwrap(await user_client.get("/api/plans", params={"status": "active"}))
    assert active["total"] == 1
    archived = unwrap(await user_client.get("/api/plans", params={"status": "archived"}))
    assert archived["total"] == 0


async def test_get_update_plan(user_client):
    created = unwrap(await user_client.post("/api/plans", json=PLAN_PAYLOAD))
    pid = created["id"]

    got = unwrap(await user_client.get(f"/api/plans/{pid}"))
    assert got["id"] == pid

    updated = unwrap(await user_client.put(f"/api/plans/{pid}", json={"name": "新计划名"}))
    assert updated["name"] == "新计划名"


async def test_get_nonexistent_plan(user_client):
    import uuid

    assert biz_code(await user_client.get(f"/api/plans/{uuid.uuid4()}")) == 40400


async def test_delete_plan_archives(user_client):
    created = unwrap(await user_client.post("/api/plans", json=PLAN_PAYLOAD))
    pid = created["id"]

    unwrap(await user_client.delete(f"/api/plans/{pid}"))

    # 软删除：计划仍存在但状态为 archived，且不再是活跃计划
    got = unwrap(await user_client.get(f"/api/plans/{pid}"))
    assert got["status"] == "archived"
    active = unwrap(await user_client.get("/api/plans/active"))
    assert active is None or active["id"] != pid


async def test_plan_day_and_exercise_operations(user_client):
    created = unwrap(await user_client.post("/api/plans", json=PLAN_PAYLOAD))
    pid = created["id"]

    # 添加训练日
    updated = unwrap(
        await user_client.post(f"/api/plans/{pid}/days", json={"day_of_week": 3, "focus": "背"})
    )
    assert len(updated["days"]) == 2
    day3 = next(d for d in updated["days"] if d["day_of_week"] == 3)
    day3_id = day3["id"]

    # 更新训练日
    updated = unwrap(
        await user_client.put(f"/api/plans/days/{day3_id}", json={"focus": "背+二头"})
    )
    day3 = next(d for d in updated["days"] if d["id"] == day3_id)
    assert day3["focus"] == "背+二头"

    # 添加动作
    updated = unwrap(
        await user_client.post(
            f"/api/plans/days/{day3_id}/exercises",
            json={"custom_name": "引体向上", "sets": 3, "reps": 8},
        )
    )
    day3 = next(d for d in updated["days"] if d["id"] == day3_id)
    assert len(day3["exercises"]) == 1
    ex_id = day3["exercises"][0]["id"]

    # 更新动作
    updated = unwrap(
        await user_client.put(f"/api/plans/exercises/{ex_id}", json={"sets": 4})
    )
    day3 = next(d for d in updated["days"] if d["id"] == day3_id)
    assert day3["exercises"][0]["sets"] == 4

    # 删除动作
    updated = unwrap(await user_client.delete(f"/api/plans/exercises/{ex_id}"))
    day3 = next(d for d in updated["days"] if d["id"] == day3_id)
    assert len(day3["exercises"]) == 0

    # 删除训练日
    updated = unwrap(await user_client.delete(f"/api/plans/days/{day3_id}"))
    assert len(updated["days"]) == 1


async def test_plan_exercise_requires_source(user_client):
    created = unwrap(await user_client.post("/api/plans", json=PLAN_PAYLOAD))
    day_id = created["days"][0]["id"]
    resp = await user_client.post(
        f"/api/plans/days/{day_id}/exercises", json={"sets": 3, "reps": 8}
    )
    assert resp.status_code == 422  # 缺 exercise_id 与 custom_name


async def test_plan_ownership(user_client, db_session):
    created = unwrap(await user_client.post("/api/plans", json=PLAN_PAYLOAD))
    pid = created["id"]

    other = await create_user(db_session, phone="13700000002", name="其他用户")
    resp = await user_client.get(f"/api/plans/{pid}", headers=auth_headers(other))
    assert biz_code(resp) == 40300
