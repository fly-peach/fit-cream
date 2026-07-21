"""
API 路由汇总

将所有子路由注册到统一的 api_router，
由 main.py 以 settings.API_PREFIX（默认 /api）前缀挂载。

子路由：
- auth: 注册/登录/刷新 Token
- users: 用户资料 CRUD
- chat: AI 对话（SSE 流式）+ 线程管理
"""
from fastapi import APIRouter

from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(chat_router)
