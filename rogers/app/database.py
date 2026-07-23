"""
异步数据库引擎、Session 工厂、声明式基类

- engine: 全局 AsyncEngine（连接池配置来自 settings）
- async_session_factory: async_sessionmaker 工厂，供 Service 层和 Agent Tools 使用
- Base: SQLAlchemy DeclarativeBase，所有 ORM Model 继承此类
- get_db: FastAPI 依赖注入，自动管理 session 生命周期（commit/rollback/close）
- init_db: 开发环境自动建表（DEBUG=True 时）
"""
import logging
from typing import AsyncGenerator

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger("fitcream")

# 异步引擎
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
    echo=False,
)

# Session 工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# 声明式基类
class Base(DeclarativeBase):
    pass


# 依赖注入：获取 db session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# 初始化数据库（开发环境自动建表）
async def init_db() -> None:
    if not settings.DEBUG:
        return

    import app.models  # noqa: F401 导入所有 model

    async with engine.begin() as conn:
        existing = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )
        tables = Base.metadata.tables.keys()
        new_tables = [t for t in tables if t not in existing]

        if new_tables:
            await conn.run_sync(Base.metadata.create_all)
            logger.info(f"数据库建表完成: {', '.join(new_tables)}")
        else:
            logger.info("数据库表已存在，跳过建表")
