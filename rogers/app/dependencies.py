"""
公共依赖

提供 FastAPI 路由共用的依赖注入函数：
- get_current_user: 从 Authorization: Bearer <token> 解析当前登录用户
"""
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.utils.exceptions import UnauthorizedException
from app.utils.security import verify_access_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT token 解析当前用户"""
    token = credentials.credentials
    payload = verify_access_token(token)

    if not payload:
        raise UnauthorizedException("无效的访问令牌")

    user_id = UUID(payload.get("sub"))
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedException("用户不存在")

    return user