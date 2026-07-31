"""饮食记录路由 /api/diet-meals/* 测试"""
import uuid
from datetime import date

from tests.util import auth_headers, biz_code, create_user, unwrap

TODAY = date.today().isoformat()


def _meal_payload(**overrides):
    payload = {
        "meal_date": TODAY,
        "meal_type": "lunch",
        "food_name": "鸡胸肉",
        "calories": 300,
        "protein_g": 50,
        "carbs_g": 5,
        "fat_g": 3,
    }
    payload.update(overrides)
    return payload


async def test_create_meal(user_client):
    data = unwrap(await user_client.post("/api/diet-meals", json=_meal_payload()))
    assert data["food_name"] == "鸡胸肉"
    assert data["calories"] == 300


async def test_create_meal_invalid_type(user_client):
    resp = await user_client.post("/api/diet-meals", json=_meal_payload(meal_type="brunch"))
    assert resp.status_code == 422


async def test_list_and_filter_meals(user_client):
    unwrap(await user_client.post("/api/diet-meals", json=_meal_payload()))
    unwrap(await user_client.post("/api/diet-meals", json=_meal_payload(meal_type="breakfast", food_name="燕麦")))

    all_meals = unwrap(await user_client.get("/api/diet-meals"))
    assert all_meals["total"] == 2

    lunch = unwrap(await user_client.get("/api/diet-meals", params={"meal_type": "lunch"}))
    assert lunch["total"] == 1


async def test_daily_summary_aggregates(user_client):
    unwrap(await user_client.post("/api/diet-meals", json=_meal_payload(calories=300, protein_g=50)))
    unwrap(await user_client.post("/api/diet-meals", json=_meal_payload(meal_type="dinner", food_name="米饭", calories=200, protein_g=5)))

    summary = unwrap(await user_client.get("/api/diet-meals/summary", params={"date": TODAY}))
    assert summary["total_calories"] == 500
    assert summary["meal_count"] == 2


async def test_list_summaries(user_client):
    unwrap(await user_client.post("/api/diet-meals", json=_meal_payload()))
    summaries = unwrap(
        await user_client.get(
            "/api/diet-meals/summaries", params={"start": TODAY, "end": TODAY}
        )
    )
    assert len(summaries) >= 1


async def test_custom_food_crud(user_client):
    created = unwrap(
        await user_client.post(
            "/api/diet-meals/foods",
            json={"name": "自制蛋白棒", "calories_per_portion": 200, "portion": "1根"},
        )
    )
    fid = created["id"]

    lst = unwrap(await user_client.get("/api/diet-meals/foods/list"))
    assert any(i["id"] == fid for i in lst)

    updated = unwrap(
        await user_client.put(
            f"/api/diet-meals/foods/{fid}", json={"calories_per_portion": 250}
        )
    )
    assert updated["calories_per_portion"] == 250

    unwrap(await user_client.delete(f"/api/diet-meals/foods/{fid}"))
    lst_after = unwrap(await user_client.get("/api/diet-meals/foods/list"))
    assert not any(i["id"] == fid for i in lst_after)


async def test_batch_create_meals(user_client):
    payload = {"meals": [_meal_payload(), _meal_payload(meal_type="snack", food_name="坚果")]}
    data = unwrap(await user_client.post("/api/diet-meals/batch", json=payload))
    assert len(data) == 2


async def test_get_update_delete_meal(user_client):
    created = unwrap(await user_client.post("/api/diet-meals", json=_meal_payload()))
    mid = created["id"]

    got = unwrap(await user_client.get(f"/api/diet-meals/{mid}"))
    assert got["id"] == mid

    updated = unwrap(await user_client.put(f"/api/diet-meals/{mid}", json={"calories": 350}))
    assert updated["calories"] == 350

    unwrap(await user_client.delete(f"/api/diet-meals/{mid}"))
    assert biz_code(await user_client.get(f"/api/diet-meals/{mid}")) != 0


async def test_meal_ownership(user_client, db_session):
    created = unwrap(await user_client.post("/api/diet-meals", json=_meal_payload()))
    mid = created["id"]
    other = await create_user(db_session, phone="13700000004", name="其他用户")
    resp = await user_client.get(f"/api/diet-meals/{mid}", headers=auth_headers(other))
    assert biz_code(resp) != 0
