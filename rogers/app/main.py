"""
FastAPI 应用入口

- lifespan: 启动时初始化日志、数据库、Agent，关闭时释放连接池
- CORS: 允许前端跨域访问
- 路由: 以 /api 前缀挂载所有业务路由
- 静态文件: 托管前端构建产物（rogers/static/），SPA fallback
- 异常处理: 统一业务异常 → JSON 响应
- 请求日志: 每次 HTTP 请求记录到 access.log

启动方式:
    cd rogers && uv run uvicorn app.main:app --reload --port 8000
    # 或
    cd rogers && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Windows 上 psycopg 需要 SelectorEventLoop（ProactorEventLoop 不兼容）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, init_db
from app.routers import api_router
from utils.exceptions import register_exception_handlers
from utils.logger import setup_logging
from utils.request_logging import RequestLoggingMiddleware

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
logger = logging.getLogger("fitcream")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    Startup:
        1. 初始化日志系统（控制台 + 文件轮转）
        2. 初始化数据库（DEBUG 模式自动建表）
        3. 初始化 Agent（创建带 checkpointer 的 LangGraph Agent，支持多轮对话持久化）
    Shutdown:
        4. 释放数据库连接池
    """
    setup_logging()
    await init_db()

    from app.database import async_session_factory
    from src.auth.seed_service import seed_admin
    from src.fitme.services.exercise_seed import seed_exercises
    async with async_session_factory() as session:
        await seed_admin(session)
        await seed_exercises(session)
        await session.commit()

    try:
        from src.agents.agent_graph import init_agent
        await init_agent()
    except Exception:
        pass

    logger.info("FitCream ready: http://localhost:8000")

    yield

    # Shutdown: 释放 Agent checkpointer 连接
    try:
        from src.agents.agent_graph import shutdown_agent
        await shutdown_agent()
    except Exception:
        pass

    await engine.dispose()


app = FastAPI(
    title="FitCream API",
    version="1.0.0",
    description="FitCream 健身训练管理后端 API",
    lifespan=lifespan,
)

# 请求日志中间件（记录每次 HTTP 请求到 access.log）
# 注意：Starlette 中后添加的中间件位于最外层。CORS 必须处于最外层才能
# 正确处理浏览器预检（OPTIONS）请求，因此先添加日志中间件（内层），
# 再添加 CORS 中间件（外层）。
if settings.ACCESS_LOG_ENABLED:
    app.add_middleware(RequestLoggingMiddleware)

# CORS 中间件（最后添加 → 最外层，确保预检请求被正确拦截处理）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router, prefix=settings.API_PREFIX)

# 注册 MCP 服务（fastapi-mcp，两个分权限实例）
try:
    if settings.MCP_ENABLED:
        from app.mcp_server import setup_mcp
        setup_mcp(app)
except Exception:
    pass

# 注册异常处理器
register_exception_handlers(app)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "version": "1.0.0"}


# ============================================================
# 前端静态文件托管（SPA 模式）
# ============================================================

if STATIC_DIR.exists():
    # 托管 assets 目录（JS/CSS/图片等带 hash 的文件）
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # 托管动作库媒体（© Gym visual）：图片 + 动图，需在 SPA catch-all 之前挂载
    exercises_media_dir = STATIC_DIR / "exercises"
    if exercises_media_dir.exists():
        app.mount(
            "/static/exercises",
            StaticFiles(directory=str(exercises_media_dir)),
            name="exercises-media",
        )

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """SPA fallback: 非 API / 非静态文件请求返回 index.html"""
        # API 路径未匹配时返回 JSON 404，不返回 HTML
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        # 尝试精确匹配静态文件（favicon.ico, robots.txt 等）
        file_path = STATIC_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # 其余路由返回 index.html，由 React Router 处理
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"detail": "Frontend not built. Run: python build_web.py"}, status_code=404)