"""用户路由 /api/users/* 测试"""
from tests.util import biz_code, unwrap


async def test_get_me(user_client, user):
    data = unwrap(await user_client.get("/api/users/me"))
    assert data["id"] == str(user.id)
    assert data["phone"] == user.phone


async def test_update_me(user_client):
    data = unwrap(
        await user_client.put(
            "/api/users/me", json={"name": "新名字", "age": 30, "gender": "male"}
        )
    )
    assert data["name"] == "新名字"
    assert data["age"] == 30


async def test_update_me_invalid_gender(user_client):
    resp = await user_client.put("/api/users/me", json={"gender": "x"})
    assert resp.status_code == 422


async def test_get_settings_defaults(user_client):
    data = unwrap(await user_client.get("/api/users/settings"))
    assert data["weekly_training_goal"] == 5
    assert data["weekly_duration_goal_min"] == 300
    assert data["calorie_goal"] == 2000


async def test_update_settings(user_client):
    data = unwrap(
        await user_client.put(
            "/api/users/settings",
            json={
                "calorie_goal": 2500,
                "goal": "lose_fat",
                "weekly_duration_goal_min": 360,
            },
        )
    )
    assert data["calorie_goal"] == 2500
    assert data["goal"] == "lose_fat"
    assert data["weekly_duration_goal_min"] == 360


async def test_health_metrics_crud(user_client):
    created = unwrap(
        await user_client.post(
            "/api/users/health-metrics",
            json={"measure_date": "2026-07-01", "height_cm": 175, "weight_kg": 70},
        )
    )
    mid = created["id"]
    assert created["weight_kg"] == 70

    lst = unwrap(await user_client.get("/api/users/health-metrics"))
    assert lst["total"] == 1

    latest = unwrap(await user_client.get("/api/users/health-metrics/latest"))
    assert latest["id"] == mid

    one = unwrap(await user_client.get(f"/api/users/health-metrics/{mid}"))
    assert one["id"] == mid

    updated = unwrap(
        await user_client.put(f"/api/users/health-metrics/{mid}", json={"weight_kg": 69})
    )
    assert updated["weight_kg"] == 69

    unwrap(await user_client.delete(f"/api/users/health-metrics/{mid}"))
    assert biz_code(await user_client.get(f"/api/users/health-metrics/{mid}")) == 40400


async def test_api_key_lifecycle(user_client):
    # 初始无 key
    assert unwrap(await user_client.get("/api/users/me/api-key")) is None

    created = unwrap(await user_client.post("/api/users/me/api-key"))
    raw_key = created["key"]
    assert raw_key
    assert created["key_out"]["key_prefix"]

    meta = unwrap(await user_client.get("/api/users/me/api-key"))
    assert meta["key_prefix"] == created["key_out"]["key_prefix"]

    # 用 API Key 认证（多态认证：JWT 或 API Key）
    resp = await user_client.get(
        "/api/users/me", headers={"Authorization": f"Bearer {raw_key}"}
    )
    unwrap(resp)

    # 删除后 API Key 失效
    unwrap(await user_client.delete("/api/users/me/api-key"))
    assert unwrap(await user_client.get("/api/users/me/api-key")) is None
    revoked = await user_client.get(
        "/api/users/me", headers={"Authorization": f"Bearer {raw_key}"}
    )
    assert biz_code(revoked) == 40100
