"""
FastAPI 应用入口

- lifespan: 启动时初始化日志和数据库，关闭时释放连接池
- CORS: 允许前端跨域访问
- 路由: 以 /api 前缀挂载所有业务路由
- 异常处理: 统一业务异常 → JSON 响应
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, init_db
from app.routers import api_router
from app.utils.exceptions import register_exception_handlers
from app.utils.logger import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # Startup
    setup_logging()
    await init_db()
    yield
    # Shutdown
    await engine.dispose()


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

# 注册路由
app.include_router(api_router, prefix=settings.API_PREFIX)

# 注册异常处理器
register_exception_handlers(app)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "version": "1.0.0"}