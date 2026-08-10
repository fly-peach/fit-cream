"""
用户 API Key 服务

一人一把，明文仅创建时返回一次，存储 sha256 哈希。
用于 MCP 外部接入认证（/mcp/user，Authorization: Bearer <key>）。
"""
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.auth_models import UserApiKey
from src.fitme.models.user import User

KEY_PREFIX = "fc_uk_"


class UserApiKeyService:

    @staticmethod
    async def create_or_replace(
        db: AsyncSession, user_id: UUID, name: Optional[str] = None
    ) -> tuple[str, UserApiKey]:
        await db.execute(delete(UserApiKey).where(UserApiKey.user_id == user_id))
        raw_key = KEY_PREFIX + secrets.token_hex(24)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = UserApiKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=raw_key[:12],
            name=name,
        )
        db.add(api_key)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            await db.execute(delete(UserApiKey).where(UserApiKey.user_id == user_id))
            db.add(api_key)
            await db.commit()
        await db.refresh(api_key)
        return raw_key, api_key

    @staticmethod
    async def get_by_user(db: AsyncSession, user_id: UUID) -> Optional[UserApiKey]:
        result = await db.execute(
            select(UserApiKey).where(UserApiKey.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def revoke(db: AsyncSession, user_id: UUID) -> None:
        await db.execute(delete(UserApiKey).where(UserApiKey.user_id == user_id))
        await db.commit()

    @staticmethod
    async def authenticate(db: AsyncSession, raw_key: str) -> Optional[User]:
        if not raw_key.startswith(KEY_PREFIX):
            return None
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        result = await db.execute(
            select(UserApiKey).where(UserApiKey.key_hash == key_hash)
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            return None
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            return None
        result = await db.execute(select(User).where(User.id == api_key.user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active or user.deleted_at:
            return None
        api_key.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        return user
