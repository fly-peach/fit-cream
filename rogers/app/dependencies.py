"""
公共依赖

提供 FastAPI 路由共用的依赖注入函数（两级权限模型）：
- get_current_user: 从 Authorization: Bearer <token> 解析当前登录用户（读 + 订阅）
- get_admin_user:   要求管理员权限（role=admin，所有写操作）
- get_kb_from_token: 通过 API token 访问 KB（外部 MCP 接入）
"""
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from src.fitme.models.user import User
from src.knowledge_base.models import KnowledgeBase
from src.knowledge_base.service import KnowledgeBaseService
from utils.exceptions import ForbiddenException, UnauthorizedException
from utils.security import verify_access_token

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

    if not user.is_active:
        raise ForbiddenException("账号已被禁用")

    if user.deleted_at:
        raise UnauthorizedException("用户不存在")

    return user


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """要求管理员权限（role=admin）"""
    if user.role != "admin":
        raise ForbiddenException("需要管理员权限")
    return user


async def get_kb_from_token(
    kb_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> tuple[object, KnowledgeBase]:
    """通过 API token 访问 KB（用于外部 MCP 接入）。

    从 Authorization: Bearer <token> 提取 token，验证并锁定 KB scope。
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise UnauthorizedException("缺少 API token")
    raw_token = auth[7:]

    token = await KnowledgeBaseService.verify_token(db, kb_id, raw_token)
    if not token:
        raise UnauthorizedException("无效或已过期的 API token")
    kb = await KnowledgeBaseService.get_kb(db, kb_id)
    return token, kb
