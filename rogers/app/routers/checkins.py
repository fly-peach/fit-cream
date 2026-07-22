"""
打卡记录路由 /api/checkins/*

提供训练打卡的 CRUD 和连续打卡统计端点。
所有端点需要 JWT 认证（Bearer Token）。
"""
from datetime import date as date_type
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.checkin import CheckinCreate, CheckinOut, CheckinUpdate, StreakOut
from app.schemas.common import PaginatedResponse, ResponseModel
from app.services.checkin_service import CheckinService

router = APIRouter(prefix="/checkins", tags=["checkins"])


@router.get("", response_model=ResponseModel[PaginatedResponse[CheckinOut]])
async def list_checkins(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    start: Optional[date_type] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end: Optional[date_type] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取打卡记录列表（支持日期范围筛选）"""
    checkins, total = await CheckinService.list_checkins(
        db, user.id, start=start, end=end, page=page, size=size
    )
    return ResponseModel(
        data=PaginatedResponse(
            items=[CheckinOut.model_validate(c) for c in checkins],
            total=total,
            page=page,
            size=size,
        )
    )


@router.get("/streak", response_model=ResponseModel[StreakOut])
async def get_streak(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取连续打卡天数统计"""
    streak_data = await CheckinService.get_streak(db, user.id)
    return ResponseModel(data=StreakOut(**streak_data))


@router.get("/{checkin_id}", response_model=ResponseModel[CheckinOut])
async def get_checkin(
    checkin_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取打卡详情"""
    checkin = await CheckinService.get_by_id(db, checkin_id, user.id)
    return ResponseModel(data=CheckinOut.model_validate(checkin))


@router.post("", response_model=ResponseModel[CheckinOut])
async def create_checkin(
    data: CheckinCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建打卡记录（同一天只能打卡一次）"""
    checkin = await CheckinService.create_checkin(db, user.id, data)
    await db.commit()
    await db.refresh(checkin)
    return ResponseModel(data=CheckinOut.model_validate(checkin))


@router.put("/{checkin_id}", response_model=ResponseModel[CheckinOut])
async def update_checkin(
    checkin_id: UUID,
    data: CheckinUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新打卡记录"""
    checkin = await CheckinService.update_checkin(db, checkin_id, user.id, data)
    await db.commit()
    await db.refresh(checkin)
    return ResponseModel(data=CheckinOut.model_validate(checkin))