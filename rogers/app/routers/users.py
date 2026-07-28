"""
用户路由 /api/users/*

提供当前用户信息查询和资料更新端点。
所有端点需要 JWT 认证（Bearer Token）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import PaginatedResponse, ResponseModel
from src.fitme.schemas.user import (
    HealthMetricCreate,
    HealthMetricOut,
    HealthMetricUpdate,
    UserOut,
    UserSettingsOut,
    UserSettingsUpdate,
    UserUpdate,
)
from src.fitme.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ResponseModel[UserOut])
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取当前用户信息（包含设置）"""
    user = await UserService.get_by_id(db, current_user.id)
    return ResponseModel(data=UserOut.model_validate(user))


@router.put("/me", response_model=ResponseModel[UserOut])
async def update_me(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新当前用户基本资料"""
    user = await UserService.update_profile(db, current_user.id, data)
    return ResponseModel(data=UserOut.model_validate(user))


@router.get("/settings", response_model=ResponseModel[UserSettingsOut])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户设置"""
    settings = await UserService.get_user_settings(db, current_user.id)
    return ResponseModel(data=UserSettingsOut.model_validate(settings))


@router.put("/settings", response_model=ResponseModel[UserSettingsOut])
async def update_settings(
    data: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新当前用户设置"""
    settings = await UserService.update_user_settings(db, current_user.id, data)
    return ResponseModel(data=UserSettingsOut.model_validate(settings))


@router.get("/health-metrics", response_model=ResponseModel[PaginatedResponse[HealthMetricOut]])
async def list_health_metrics(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取健康指标历史记录"""
    metrics, total = await UserService.list_health_metrics(db, current_user.id, page, size)
    return ResponseModel(data=PaginatedResponse(
        items=[HealthMetricOut.model_validate(m) for m in metrics],
        total=total,
        page=page,
        size=size,
    ))


@router.get("/health-metrics/latest", response_model=ResponseModel[Optional[HealthMetricOut]])
async def get_latest_health_metric(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取最新的健康指标记录"""
    metric = await UserService.get_latest_health_metric(db, current_user.id)
    return ResponseModel(data=HealthMetricOut.model_validate(metric) if metric else None)


@router.get("/health-metrics/{metric_id}", response_model=ResponseModel[HealthMetricOut])
async def get_health_metric(
    metric_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单条健康指标记录"""
    from uuid import UUID
    metric = await UserService.get_health_metric(db, current_user.id, UUID(metric_id))
    return ResponseModel(data=HealthMetricOut.model_validate(metric))


@router.post("/health-metrics", response_model=ResponseModel[HealthMetricOut])
async def create_health_metric(
    data: HealthMetricCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建健康指标记录"""
    metric = await UserService.create_health_metric(db, current_user.id, data)
    return ResponseModel(data=HealthMetricOut.model_validate(metric))


@router.put("/health-metrics/{metric_id}", response_model=ResponseModel[HealthMetricOut])
async def update_health_metric(
    metric_id: str,
    data: HealthMetricUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新健康指标记录"""
    from uuid import UUID
    metric = await UserService.update_health_metric(db, current_user.id, UUID(metric_id), data)
    return ResponseModel(data=HealthMetricOut.model_validate(metric))


@router.delete("/health-metrics/{metric_id}", response_model=ResponseModel[None])
async def delete_health_metric(
    metric_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除健康指标记录"""
    from uuid import UUID
    await UserService.delete_health_metric(db, current_user.id, UUID(metric_id))
    return ResponseModel(message="已删除")
