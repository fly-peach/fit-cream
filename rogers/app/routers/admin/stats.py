"""
管理端统计路由 /api/admin/stats/*

提供管理员专用的全局运营统计（四维度 KPI）与近 N 天趋势。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user
from src.fitme.models.user import User
from src.fitme.schemas.admin import AdminOverviewStats, AdminTrends
from src.fitme.schemas.common import ResponseModel
from src.fitme.services.admin_service import AdminService

router = APIRouter(prefix="/stats", tags=["admin-stats"])


@router.get(
    "/overview",
    response_model=ResponseModel[AdminOverviewStats],
    operation_id="admin_overview_stats",
)
async def admin_overview_stats(
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """总览 KPI（用户/训练/知识库/对话 四维度）（admin）"""
    stats = await AdminService.get_overview_stats(db)
    return ResponseModel(data=stats)


@router.get(
    "/trends",
    response_model=ResponseModel[AdminTrends],
    operation_id="admin_trends_stats",
)
async def admin_trends_stats(
    days: int = Query(30, ge=7, le=90, description="统计天数"),
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """近 N 天每日趋势（注册/打卡/对话/活跃用户）（admin）"""
    trends = await AdminService.get_trends(db, days=days)
    return ResponseModel(data=trends)
