"""
管理后台路由包 /api/admin/*

聚合用户管理、全局统计、知识库管理列表三个子路由。
所有端点均要求管理员权限（get_admin_user）。
"""
from fastapi import APIRouter

from app.routers.admin import knowledge_bases as admin_kb_router_mod
from app.routers.admin import stats as admin_stats_router_mod
from app.routers.admin import users as admin_users_router_mod

router = APIRouter()

router.include_router(admin_users_router_mod.router)
router.include_router(admin_stats_router_mod.router)
router.include_router(admin_kb_router_mod.router)
