"""动作库路由 /api/exercises/* 测试"""
import uuid

from tests.util import biz_code, create_exercise, unwrap


async def test_list_exercises(user_client, db_session):
    await create_exercise(db_session, name="杠铃卧推", muscle_group="chest")
    await create_exercise(db_session, name="深蹲", muscle_group="legs")
    data = unwrap(await user_client.get("/api/exercises"))
    assert len(data) >= 2


async def test_filter_by_muscle_group(user_client, db_session):
    await create_exercise(db_session, name="杠铃卧推", muscle_group="chest")
    await create_exercise(db_session, name="深蹲", muscle_group="legs")
    data = unwrap(await user_client.get("/api/exercises", params={"muscle_group": "chest"}))
    assert all(e["muscle_group"] == "chest" for e in data)
    assert any(e["name"] == "杠铃卧推" for e in data)


async def test_keyword_search(user_client, db_session):
    await create_exercise(db_session, name="杠铃卧推")
    data = unwrap(await user_client.get("/api/exercises", params={"keyword": "卧推"}))
    assert any("卧推" in e["name"] for e in data)


async def test_category_endpoints(user_client, db_session):
    await create_exercise(db_session, name="杠铃卧推", category="strength")
    unwrap(await user_client.get("/api/exercises/categories"))
    unwrap(await user_client.get("/api/exercises/muscle-groups"))
    unwrap(await user_client.get("/api/exercises/equipments"))


async def test_get_exercise_by_id(user_client, db_session):
    ex = await create_exercise(db_session, name="硬拉")
    data = unwrap(await user_client.get(f"/api/exercises/{ex.id}"))
    assert data["name"] == "硬拉"


async def test_get_nonexistent_exercise(user_client):
    assert biz_code(await user_client.get(f"/api/exercises/{uuid.uuid4()}")) == 40400


async def test_favorite_toggle(user_client, db_session):
    ex = await create_exercise(db_session, name="卧推")

    first = unwrap(await user_client.post(f"/api/exercises/{ex.id}/favorite"))
    assert first["favorited"] is True

    ids = unwrap(await user_client.get("/api/exercises/favorites/ids"))
    assert str(ex.id) in ids

    fav_list = unwrap(await user_client.get("/api/exercises/favorites/list"))
    assert fav_list["total"] == 1

    second = unwrap(await user_client.post(f"/api/exercises/{ex.id}/favorite"))
    assert second["favorited"] is False

    ids_after = unwrap(await user_client.get("/api/exercises/favorites/ids"))
    assert str(ex.id) not in ids_after


async def test_admin_create_exercise(admin_client):
    data = unwrap(
        await admin_client.post(
            "/api/exercises", json={"name": "哑铃飞鸟", "muscle_group": "chest"}
        )
    )
    assert data["name"] == "哑铃飞鸟"


async def test_create_exercise_forbidden_for_user(user_client):
    resp = await user_client.post("/api/exercises", json={"name": "x"})
    assert biz_code(resp) == 40300


async def test_admin_update_delete_exercise(admin_client, user_client, db_session):
    ex = await create_exercise(db_session, name="坐姿划船")

    updated = unwrap(
        await admin_client.put(f"/api/exercises/{ex.id}", json={"difficulty": "advanced"})
    )
    assert updated["difficulty"] == "advanced"

    # 普通用户无写权限
    assert biz_code(await user_client.put(f"/api/exercises/{ex.id}", json={"name": "y"})) == 40300
    assert biz_code(await user_client.delete(f"/api/exercises/{ex.id}")) == 40300

    unwrap(await admin_client.delete(f"/api/exercises/{ex.id}"))
    assert biz_code(await admin_client.get(f"/api/exercises/{ex.id}")) == 40400
