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

from sqlalchemy import inspect, text
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


def _column_default_literal(col) -> str | None:
    """返回列默认值的 SQL 字面量（用于 ALTER ADD COLUMN NOT NULL 时填充存量行）。"""
    if col.default is not None and getattr(col.default, "is_scalar", False):
        val = col.default.arg
        if isinstance(val, bool):
            return "TRUE" if val else "FALSE"
        if isinstance(val, (int, float)):
            return str(val)
        return "'" + str(val).replace("'", "''") + "'"
    if col.server_default is not None:
        try:
            return col.server_default.arg.text
        except AttributeError:
            return None
    return None


def _add_missing_columns(sync_conn) -> list[str]:
    """对已存在的表，补齐模型中新增但数据库缺失的列（DEBUG 便利，幂等）。"""
    insp = inspect(sync_conn)
    existing_tables = set(insp.get_table_names())
    added: list[str] = []
    for table_name, table_obj in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in insp.get_columns(table_name)}
        for col in table_obj.columns:
            if col.name in existing_cols:
                continue
            type_sql = col.type.compile(dialect=sync_conn.dialect)
            if col.nullable:
                sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {type_sql} NULL'
            else:
                default_sql = _column_default_literal(col)
                if default_sql is not None:
                    sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {type_sql} NOT NULL DEFAULT {default_sql}'
                else:
                    sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {type_sql} NULL'
            sync_conn.execute(text(sql))
            added.append(f"{table_name}.{col.name}")
    return added


# 初始化数据库（开发环境自动建表）
async def init_db() -> None:
    if not settings.DEBUG:
        return

    import src.fitme.models  # noqa: F401 导入所有 model

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

        # 自动补齐已有表缺失的列（DEBUG 便利：模型新增列后无需手写迁移）
        added_columns = await conn.run_sync(_add_missing_columns)
        if added_columns:
            logger.info(f"数据库补列完成: {', '.join(added_columns)}")
