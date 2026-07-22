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
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, init_db
from app.routers import api_router
from app.utils.exceptions import register_exception_handlers
from app.utils.logger import setup_logging
from app.utils.request_logging import RequestLoggingMiddleware

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
    # 1. 日志
    setup_logging()
    logger.info("=" * 50)
    logger.info(f"  {settings.APP_NAME} v1.0.0 启动中...")
    logger.info(f"  DEBUG={settings.DEBUG} | LOG_FORMAT={settings.LOG_FORMAT}")
    logger.info(f"  DATABASE={settings.DATABASE_URL[:30]}...")
    logger.info("=" * 50)

    # 2. 数据库
    await init_db()
    logger.info("数据库初始化完成")

    # 2.5 种子管理员
    from app.database import async_session_factory
    from app.services.seed_service import seed_admin
    async with async_session_factory() as session:
        await seed_admin(session)

    # 3. Agent（带 checkpointer，支持多轮对话记忆）
    try:
        from agents.agent_graph import init_agent
        await init_agent()
        logger.info("Agent 初始化完成（含 checkpointer）")
    except Exception as e:
        logger.warning(f"Agent 初始化跳过: {e}（使用无状态模式）")

    logger.info(f"服务就绪: http://0.0.0.0:{settings.API_PREFIX}")

    yield

    # 4. 关闭
    await engine.dispose()
    logger.info("数据库连接池已释放，服务关闭")


app = FastAPI(
    title="FitCream API",
    version="1.0.0",
    description="FitCream 健身训练管理后端 API",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件（记录每次 HTTP 请求到 access.log）
if settings.ACCESS_LOG_ENABLED:
    app.add_middleware(RequestLoggingMiddleware)

# 注册 API 路由
app.include_router(api_router, prefix=settings.API_PREFIX)

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

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """SPA fallback: 非 API / 非静态文件请求返回 index.html"""
        # 尝试精确匹配静态文件（favicon.ico, robots.txt 等）
        file_path = STATIC_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # 其余路由返回 index.html，由 React Router 处理
        index = STATIC_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"detail": "Frontend not built. Run: python build_console.py"}, status_code=404)