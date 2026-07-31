"""
测试辅助工具

提供：
- 数据工厂：create_user / create_exercise（直接写库，绕过 SMS 等外部依赖）
- 认证辅助：auth_headers（签发 JWT）
- 响应断言：unwrap（成功解包 data）/ biz_code（业务错误码）

注意：本模块会导入 app.* / src.*，必须在 conftest 设置好测试环境变量之后导入。
"""
from httpx import Response

from src.fitme.models.exercise import Exercise
from src.fitme.models.user import User
from src.fitme.models.user_settings import UserSettings
from utils.security import create_access_token, hash_password


async def create_user(
    db,
    phone: str,
    password: str = "pass123456",
    role: str = "user",
    name: str | None = None,
    is_active: bool = True,
) -> User:
    """直接写库创建用户（含默认设置），返回 User ORM 对象。"""
    user = User(
        phone=phone,
        password_hash=hash_password(password),
        name=name,
        role=role,
        is_active=is_active,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    db.add(UserSettings(user_id=user.id))
    await db.commit()
    await db.refresh(user)
    return user


def auth_headers(user: User) -> dict[str, str]:
    """为用户签发 Bearer JWT 请求头。"""
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


async def create_exercise(
    db,
    name: str = "杠铃卧推",
    muscle_group: str = "chest",
    equipment: str = "barbell",
    category: str = "strength",
    difficulty: str = "intermediate",
) -> Exercise:
    """直接写库创建动作库动作（供打卡 / 计划 / 收藏引用）。"""
    ex = Exercise(
        name=name,
        muscle_group=muscle_group,
        equipment=equipment,
        category=category,
        difficulty=difficulty,
    )
    db.add(ex)
    await db.commit()
    await db.refresh(ex)
    return ex


def unwrap(resp: Response):
    """断言 HTTP 200 且业务 code==0，返回 data。"""
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:400]}"
    body = resp.json()
    assert body.get("code") == 0, f"业务错误: {body}"
    return body.get("data")


def biz_code(resp: Response) -> int:
    """断言 HTTP 200 且业务 code!=0，返回错误码。"""
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:400]}"
    body = resp.json()
    assert body.get("code", 0) != 0, f"期望业务错误，实际成功: {body}"
    return body["code"]
