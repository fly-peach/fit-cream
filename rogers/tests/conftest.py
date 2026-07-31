"""
测试基础设施（conftest）

方案：针对同一 PostgreSQL 实例上的独立 schema（fitcream_test）做集成测试，
通过 httpx ASGITransport 在进程内驱动真实 FastAPI 应用（不起服务、不跑 lifespan）。

为什么用 schema 而非独立数据库：业务数据库角色（fitcream）无 CREATEDB 权限，
但可在自己拥有的库内创建 schema。测试表全部落在 fitcream_test schema，
与开发数据（public schema）完全隔离，互不污染。

实现要点：
- 测试引擎通过 asyncpg server_settings 设置 search_path=fitcream_test，
  建表 / 查询 / 清理都默认命中测试 schema。
- 覆盖 FastAPI 的 get_db 依赖，使所有路由请求走测试引擎（而非应用默认 public 引擎）。
- 会话级建 schema + 建表一次；每个测试函数前 TRUNCATE 全表（RESTART IDENTITY CASCADE）。
- 整个会话共用一个事件循环（pytest.ini session 级 loop scope），避免 asyncpg 连接池跨 loop。
"""
import asyncio
import sys

# Windows 上 asyncpg 需要 SelectorEventLoop（ProactorEventLoop 不兼容）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os  # noqa: E402

# 关闭日志中间件 / MCP；SMS 凭证置空走 dev 模式（仅打日志）
os.environ["ACCESS_LOG_ENABLED"] = "false"
os.environ["MCP_ENABLED"] = "false"
os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"] = ""
os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"] = ""

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.config import settings  # noqa: E402

TEST_SCHEMA = "fitcream_test"

# ============================================================
# 测试引擎（search_path 指向测试 schema）
# ============================================================
test_engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"server_settings": {"search_path": TEST_SCHEMA}},
    pool_pre_ping=True,
)
test_session_factory = async_sessionmaker(
    test_engine, expire_on_commit=False
)

# 导入应用与模型（注册到 Base.metadata）
import app.models  # noqa: E401,F401
from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402

from tests.util import auth_headers, create_exercise, create_user  # noqa: E402,F401


# ============================================================
# 覆盖 get_db：让所有路由请求落到测试 schema
# ============================================================
async def _override_get_db():
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


fastapi_app.dependency_overrides[get_db] = _override_get_db


# ============================================================
# 会话级：建 schema + 建表
# ============================================================
async def _create_schema_and_tables() -> None:
    # 使用独立临时引擎建表（临时 loop），避免把 test_engine 的连接绑定到临时 loop；
    # test_engine 仅在会话 loop（测试 / 异步 fixture）中使用。
    setup_engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"server_settings": {"search_path": TEST_SCHEMA}},
    )
    try:
        async with setup_engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}"))
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            except Exception:
                # 业务角色通常无 superuser 权限；搜索走 ilike / 内置 tsvector，无扩展也可用
                pass
    finally:
        await setup_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _db_setup():
    asyncio.run(_create_schema_and_tables())
    yield


# ============================================================
# 函数级：清空全表（测试隔离）
# ============================================================
async def _truncate_all() -> None:
    table_names = ", ".join(f'"{t}"' for t in Base.metadata.tables.keys())
    if not table_names:
        return
    async with test_engine.begin() as conn:
        await conn.execute(
            text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
        )


@pytest.fixture(autouse=True)
async def _clean_tables():
    await _truncate_all()
    yield


# ============================================================
# 客户端与认证 fixtures
# ============================================================
def _make_client(headers: dict | None = None) -> AsyncClient:
    transport = ASGITransport(app=fastapi_app)
    return AsyncClient(transport=transport, base_url="http://testserver", headers=headers)


@pytest.fixture
async def client():
    async with _make_client() as c:
        yield c


@pytest.fixture
async def db_session():
    async with test_session_factory() as session:
        yield session


@pytest.fixture
async def user(db_session):
    return await create_user(db_session, phone="13800000001", name="普通用户")


@pytest.fixture
async def admin(db_session):
    return await create_user(
        db_session, phone="13900000001", name="管理员", role="admin"
    )


@pytest.fixture
async def user_client(user):
    # 独立客户端实例，避免与 admin_client 共享底层 client 导致请求头互相覆盖
    async with _make_client(auth_headers(user)) as c:
        yield c


@pytest.fixture
async def admin_client(admin):
    async with _make_client(auth_headers(admin)) as c:
        yield c
