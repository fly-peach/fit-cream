"""认证路由 /api/auth/* 测试"""
from datetime import datetime, timedelta, timezone

from src.fitme.models.auth_models import VerificationCode
from tests.util import biz_code, create_user, unwrap

PHONE = "13800138000"
PASSWORD = "pass123456"


async def _register(client, phone=PHONE, password=PASSWORD, name="新用户"):
    return await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": password, "name": name},
    )


async def _insert_code(db, phone, code, code_type):
    db.add(
        VerificationCode(
            phone=phone,
            code=code,
            code_type=code_type,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    )
    await db.commit()


async def test_register_success(client):
    data = unwrap(await _register(client))
    assert data["user"]["phone"] == PHONE
    assert data["user"]["name"] == "新用户"
    assert data["tokens"]["access_token"]
    assert data["tokens"]["refresh_token"]


async def test_register_duplicate_phone(client):
    unwrap(await _register(client))
    assert biz_code(await _register(client)) == 40001


async def test_register_invalid_phone_too_short(client):
    resp = await client.post(
        "/api/auth/register", json={"phone": "123", "password": PASSWORD}
    )
    assert resp.status_code == 422


async def test_login_success(client):
    unwrap(await _register(client))
    data = unwrap(
        await client.post(
            "/api/auth/login", json={"phone": PHONE, "password": PASSWORD}
        )
    )
    assert data["tokens"]["access_token"]


async def test_login_wrong_password(client):
    unwrap(await _register(client))
    resp = await client.post(
        "/api/auth/login", json={"phone": PHONE, "password": "wrong-pass"}
    )
    assert biz_code(resp) == 40103


async def test_login_nonexistent_user(client):
    resp = await client.post(
        "/api/auth/login", json={"phone": "13999999999", "password": PASSWORD}
    )
    assert biz_code(resp) == 40103


async def test_refresh_token(client):
    data = unwrap(await _register(client))
    refresh = data["tokens"]["refresh_token"]
    new_tokens = unwrap(
        await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    )
    assert new_tokens["access_token"]


async def test_refresh_invalid_token(client):
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": "not-a-token"}
    )
    assert biz_code(resp) == 40101


async def test_change_password_flow(client, user):
    from tests.util import auth_headers

    # 原密码错误
    bad = await client.post(
        "/api/auth/change-password",
        json={"old_password": "nope", "new_password": "newpass123"},
        headers=auth_headers(user),
    )
    assert biz_code(bad) == 40103

    # 正确修改（create_user 默认密码 pass123456）
    ok = await client.post(
        "/api/auth/change-password",
        json={"old_password": "pass123456", "new_password": "newpass123"},
        headers=auth_headers(user),
    )
    unwrap(ok)

    # 新密码可登录
    login = await client.post(
        "/api/auth/login", json={"phone": user.phone, "password": "newpass123"}
    )
    unwrap(login)


async def test_change_password_requires_auth(client):
    resp = await client.post(
        "/api/auth/change-password",
        json={"old_password": "a", "new_password": "newpass123"},
    )
    # 缺少凭证：新版 FastAPI HTTPBearer 返回 401，旧版 403
    assert resp.status_code in (401, 403)


async def test_logout_blacklists_refresh_token(client):
    data = unwrap(await _register(client))
    refresh = data["tokens"]["refresh_token"]

    unwrap(await client.post("/api/auth/logout", json={"refresh_token": refresh}))

    # 注销后 refresh 应失败
    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert biz_code(resp) == 40101


async def test_send_verification_code_dev_mode(client):
    resp = await client.post(
        "/api/auth/send-verification-code",
        json={"phone": PHONE, "code_type": "register"},
    )
    unwrap(resp)  # dev 模式仅打日志，返回成功


async def test_verify_code_success_and_failure(client, db_session):
    await _insert_code(db_session, PHONE, "123456", "register")

    wrong = await client.post(
        "/api/auth/verify-code",
        json={"phone": PHONE, "code": "000000", "code_type": "register"},
    )
    assert biz_code(wrong) == 40000

    ok = await client.post(
        "/api/auth/verify-code",
        json={"phone": PHONE, "code": "123456", "code_type": "register"},
    )
    unwrap(ok)


async def test_reset_password_flow(client, db_session):
    await create_user(db_session, phone=PHONE, password="oldpass123")
    await _insert_code(db_session, PHONE, "654321", "reset_password")

    ok = await client.post(
        "/api/auth/reset-password",
        json={"phone": PHONE, "code": "654321", "new_password": "newpass123"},
    )
    unwrap(ok)

    login_new = await client.post(
        "/api/auth/login", json={"phone": PHONE, "password": "newpass123"}
    )
    unwrap(login_new)

    login_old = await client.post(
        "/api/auth/login", json={"phone": PHONE, "password": "oldpass123"}
    )
    assert biz_code(login_old) == 40103
