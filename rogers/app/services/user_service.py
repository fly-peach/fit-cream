"""
用户服务

提供用户查询和资料更新的业务逻辑。
支持部分更新（仅修改传入的字段）。
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserUpdate
from app.utils.exceptions import NotFoundException


class UserService:
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: UUID) -> User:
        """根据 ID 获取用户"""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException("用户不存在")
        return user

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        """根据邮箱获取用户"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_profile(
        db: AsyncSession, user_id: UUID, data: UserUpdate
    ) -> User:
        """更新用户资料（部分更新）"""
        user = await UserService.get_by_id(db, user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        await db.flush()
        await db.refresh(user)
        return user