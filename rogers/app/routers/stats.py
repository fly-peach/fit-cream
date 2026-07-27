"""
统计数据路由 /api/stats/*

提供训练数据的多维度统计端点。
所有端点需要 JWT 认证（Bearer Token）。
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel
from src.fitme.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/weekly", response_model=ResponseModel[dict])
async def get_weekly_stats(
    week_start: Optional[date] = Query(None, description="周起始日期 (YYYY-MM-DD)，默认本周一"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取周统计（训练次数、时长、每日明细）"""
    data = await StatsService.get_weekly_stats(db, user.id, week_start=week_start)
    return ResponseModel(data=data)


@router.get("/monthly", response_model=ResponseModel[dict])
async def get_monthly_stats(
    year: Optional[int] = Query(None, ge=2020, le=2100, description="年份"),
    month: Optional[int] = Query(None, ge=1, le=12, description="月份"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取月统计（训练趋势、平均心情）"""
    data = await StatsService.get_monthly_trend(db, user.id, year=year, month=month)
    return ResponseModel(data=data)


@router.get("/body", response_model=ResponseModel[dict])
async def get_body_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取身体数据（当前体重、身高、目标）"""
    data = await StatsService.get_body_trend(db, user.id)
    return ResponseModel(data=data)


@router.get("/overview", response_model=ResponseModel[dict])
async def get_overview_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取总览统计（累计训练量、连续打卡天数）"""
    data = await StatsService.get_all_stats(db, user.id)
    return ResponseModel(data=data)