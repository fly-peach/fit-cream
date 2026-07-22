"""
种子数据服务

首次启动时自动创建管理员账号（如果不存在）。
从环境变量 SEED_ADMIN_PHONE / SEED_ADMIN_PASSWORD 读取配置。
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.utils.security import hash_password

logger = logging.getLogger("fitcream")


async def seed_admin(db: AsyncSession) -> None:
    """
    创建种子管理员（幂等：已存在则跳过）

    读取 settings.SEED_ADMIN_PHONE / SEED_ADMIN_PASSWORD，
    若未配置则跳过。
    """
    phone = settings.SEED_ADMIN_PHONE
    password = settings.SEED_ADMIN_PASSWORD

    if not phone or not password:
        logger.info("种子管理员未配置（SEED_ADMIN_PHONE / SEED_ADMIN_PASSWORD 为空），跳过")
        return

    # 检查是否已存在
    result = await db.execute(select(User).where(User.phone == phone))
    existing = result.scalar_one_or_none()
    if existing:
        logger.info(f"种子管理员已存在: {phone}，跳过创建")
        return

    # 创建管理员
    admin = User(
        phone=phone,
        password_hash=hash_password(password),
        name="管理员",
    )
    db.add(admin)
    await db.commit()
    logger.info(f"种子管理员创建成功: {phone}")