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
    assert data["calorie_goal"] == 2000


async def test_update_settings(user_client):
    data = unwrap(
        await user_client.put(
            "/api/users/settings",
            json={
                "calorie_goal": 2500,
                "goal": "lose_fat",
                "weekly_training_goal": 6,
            },
        )
    )
    assert data["calorie_goal"] == 2500
    assert data["goal"] == "lose_fat"
    assert data["weekly_training_goal"] == 6


async def test_get_fitness_profile_defaults(user_client):
    data = unwrap(await user_client.get("/api/users/me/fitness-profile"))
    assert data["medical_history"] is None
    assert data["parq_result"] is None
    assert data["body_fat_pct"] is None
    assert data["meals_per_day"] is None


async def test_update_fitness_profile_partial_roundtrip(user_client):
    data = unwrap(
        await user_client.put(
            "/api/users/me/fitness-profile",
            json={
                "medical_history": "无",
                "parq_result": "low",
                "training_experience": "intermediate",
                "weekly_frequency": "3-4",
                "sleep_quality": "good",
                "diet_preferences": "少油清淡",
                "body_fat_pct": 22.5,
            },
        )
    )
    assert data["medical_history"] == "无"
    assert data["parq_result"] == "low"
    assert data["training_experience"] == "intermediate"
    assert data["weekly_frequency"] == "3-4"
    assert data["sleep_quality"] == "good"
    assert data["diet_preferences"] == "少油清淡"
    assert data["body_fat_pct"] == 22.5
    # 未传字段保持 None
    assert data["injuries"] is None
    assert data["cardio_level"] is None

    # 再次 GET 往返一致
    fetched = unwrap(await user_client.get("/api/users/me/fitness-profile"))
    assert fetched["parq_result"] == "low"
    assert fetched["body_fat_pct"] == 22.5

    # 部分更新不影响已存字段
    data2 = unwrap(
        await user_client.put(
            "/api/users/me/fitness-profile", json={"strength_level": "advanced"}
        )
    )
    assert data2["strength_level"] == "advanced"
    assert data2["weekly_frequency"] == "3-4"


async def test_update_fitness_profile_invalid_enum(user_client):
    resp = await user_client.put(
        "/api/users/me/fitness-profile", json={"parq_result": "unknown"}
    )
    assert resp.status_code == 422

    resp = await user_client.put(
        "/api/users/me/fitness-profile", json={"body_fat_pct": 150}
    )
    assert resp.status_code == 422


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
