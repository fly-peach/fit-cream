"""横切认证 / 权限测试"""
from datetime import datetime, timezone

from tests.util import auth_headers, biz_code, create_user


async def test_missing_token_rejected(client):
    resp = await client.get("/api/users/me")
    assert resp.status_code in (401, 403)


async def test_invalid_token_rejected(client):
    resp = await client.get("/api/users/me", headers={"Authorization": "Bearer garbage"})
    assert biz_code(resp) == 40100


async def test_non_admin_cannot_access_admin_endpoints(user_client):
    assert biz_code(await user_client.post("/api/exercises", json={"name": "x"})) == 40300
    assert biz_code(await user_client.post("/api/knowledge-bases", json={"name": "x"})) == 40300


async def test_inactive_user_forbidden(client, db_session):
    user = await create_user(db_session, phone="13600000001", is_active=False)
    resp = await client.get("/api/users/me", headers=auth_headers(user))
    assert biz_code(resp) == 40300


async def test_deleted_user_unauthorized(client, db_session):
    user = await create_user(db_session, phone="13600000002")
    user.deleted_at = datetime.now(timezone.utc)
    await db_session.commit()
    resp = await client.get("/api/users/me", headers=auth_headers(user))
    assert biz_code(resp) == 40100
