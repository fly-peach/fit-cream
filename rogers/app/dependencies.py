"""
公共依赖

提供 FastAPI 路由共用的依赖注入函数（两级权限模型）：
- get_current_user: 多态认证（JWT 或用户 API Key），解析当前用户
- get_admin_user:   要求管理员权限（role=admin，所有写操作）
"""
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from src.auth.api_key_service import UserApiKeyService
from src.fitme.models.user import User
from utils.exceptions import ForbiddenException, UnauthorizedException
from utils.security import verify_access_token

security = HTTPBearer()


async def _load_active_user(db: AsyncSession, user_id: UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedException("用户不存在")

    if not user.is_active:
        raise ForbiddenException("账号已被禁用")

    if user.deleted_at:
        raise UnauthorizedException("用户不存在")

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """多态认证：先尝试 JWT，再尝试用户 API Key"""
    credential = credentials.credentials

    payload = verify_access_token(credential)
    if payload:
        return await _load_active_user(db, UUID(payload.get("sub")))

    user = await UserApiKeyService.authenticate(db, credential)
    if user:
        return user

    raise UnauthorizedException("无效的访问令牌或 API Key")


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """要求管理员权限（role=admin）"""
    if user.role != "admin":
        raise ForbiddenException("需要管理员权限")
    return user
