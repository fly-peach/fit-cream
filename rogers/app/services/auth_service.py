"""
认证服务

处理用户注册、登录、Token 刷新的核心业务逻辑。
密码使用 bcrypt 哈希存储，Token 使用 JWT（HS256）签发。
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.schemas.auth import TokenPair
from app.utils.exceptions import BusinessException, ErrorCode
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_access_token,
    verify_password,
    verify_refresh_token,
)


class AuthService:
    @staticmethod
    async def register(
        db: AsyncSession,
        email: str,
        password: str,
        name: str | None = None,
    ) -> tuple[User, TokenPair]:
        """注册新用户，返回 (user, tokens)"""
        # 检查邮箱是否已注册
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS, "邮箱已注册")

        user = User(
            email=email,
            password_hash=hash_password(password),
            name=name,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

        tokens = AuthService._generate_tokens(user.id)
        return user, tokens

    @staticmethod
    async def login(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> tuple[User, TokenPair]:
        """登录，返回 (user, tokens)"""
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise BusinessException(ErrorCode.INVALID_CREDENTIALS, "邮箱或密码错误")

        tokens = AuthService._generate_tokens(user.id)
        return user, tokens

    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_token: str) -> TokenPair:
        """刷新 access token"""
        payload = verify_refresh_token(refresh_token)
        if not payload:
            raise BusinessException(ErrorCode.INVALID_TOKEN, "无效的刷新令牌")

        user_id = UUID(payload.get("sub"))
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise BusinessException(ErrorCode.USER_NOT_FOUND, "用户不存在")

        return AuthService._generate_tokens(user.id)

    @staticmethod
    def _generate_tokens(user_id: UUID) -> TokenPair:
        """生成 token 对"""
        return TokenPair(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )