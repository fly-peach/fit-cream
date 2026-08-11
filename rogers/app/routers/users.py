"""
用户路由 /api/users/*

提供当前用户信息查询、资料更新和 API Key 管理端点。
所有端点需要认证（Bearer Token：JWT 或用户 API Key）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.auth.api_key_service import UserApiKeyService
from src.fitme.models.user import User
from src.fitme.schemas.common import PaginatedResponse, ResponseModel
from src.fitme.schemas.user import (
    HealthMetricCreate,
    HealthMetricOut,
    HealthMetricUpdate,
    UserApiKeyCreate,
    UserApiKeyCreated,
    UserApiKeyOut,
    UserGoalsOut,
    UserGoalsUpdate,
    UserOut,
    UserUpdate,
)
from src.fitme.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ResponseModel[UserOut], operation_id="get_me")
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取当前用户信息（含最新身高体重与健身目标）"""
    user = await UserService.get_by_id(db, current_user.id)
    profile = await UserService.get_profile_summary(db, current_user.id)
    return ResponseModel(data=UserOut.model_validate({
        **UserOut.model_validate(user).model_dump(exclude_none=False),
        "height_cm": profile["height_cm"],
        "weight_kg": profile["weight_kg"],
        "goal": profile["goal"],
        "age": profile["age"],
    }))


@router.put("/me", response_model=ResponseModel[UserOut], operation_id="update_me")
async def update_me(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新当前用户基本资料（身高/体重/目标走 HealthMetric/UserSettings，与 agent 同一写路径）"""
    await UserService.update_profile_consolidated(
        db,
        current_user.id,
        name=data.name,
        birth_date=data.birth_date,
        gender=data.gender,
        height_cm=data.height_cm,
        weight_kg=data.weight_kg,
        goal=data.goal,
    )
    user = await UserService.get_by_id(db, current_user.id)
    profile = await UserService.get_profile_summary(db, current_user.id)
    return ResponseModel(data=UserOut.model_validate({
        **UserOut.model_validate(user).model_dump(exclude_none=False),
        "height_cm": profile["height_cm"],
        "weight_kg": profile["weight_kg"],
        "goal": profile["goal"],
        "age": profile["age"],
    }))


@router.get("/settings", response_model=ResponseModel[UserGoalsOut], operation_id="get_settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户目标（健身目标 + 营养目标 + 通知偏好）"""
    goals = await UserService.get_user_goals(db, current_user.id)
    return ResponseModel(data=UserGoalsOut.model_validate(goals))


@router.put("/settings", response_model=ResponseModel[UserGoalsOut], operation_id="update_settings")
async def update_settings(
    data: UserGoalsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新当前用户目标（部分更新）"""
    goals = await UserService.update_user_goals(db, current_user.id, data)
    return ResponseModel(data=UserGoalsOut.model_validate(goals))


@router.get("/health-metrics", response_model=ResponseModel[PaginatedResponse[HealthMetricOut]], operation_id="list_health_metrics")
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


@router.get("/health-metrics/latest", response_model=ResponseModel[Optional[HealthMetricOut]], operation_id="get_latest_health_metric")
async def get_latest_health_metric(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取最新的健康指标记录"""
    metric = await UserService.get_latest_health_metric(db, current_user.id)
    return ResponseModel(data=HealthMetricOut.model_validate(metric) if metric else None)


@router.get("/health-metrics/{metric_id}", response_model=ResponseModel[HealthMetricOut], operation_id="get_health_metric")
async def get_health_metric(
    metric_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单条健康指标记录"""
    from uuid import UUID
    metric = await UserService.get_health_metric(db, current_user.id, UUID(metric_id))
    return ResponseModel(data=HealthMetricOut.model_validate(metric))


@router.post("/health-metrics", response_model=ResponseModel[HealthMetricOut], operation_id="create_health_metric")
async def create_health_metric(
    data: HealthMetricCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建健康指标记录"""
    metric = await UserService.create_health_metric(db, current_user.id, data)
    return ResponseModel(data=HealthMetricOut.model_validate(metric))


@router.put("/health-metrics/{metric_id}", response_model=ResponseModel[HealthMetricOut], operation_id="update_health_metric")
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


@router.delete("/health-metrics/{metric_id}", response_model=ResponseModel[None], operation_id="delete_health_metric")
async def delete_health_metric(
    metric_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除健康指标记录"""
    from uuid import UUID
    await UserService.delete_health_metric(db, current_user.id, UUID(metric_id))
    return ResponseModel(message="已删除")


@router.get("/me/api-key", response_model=ResponseModel[Optional[UserApiKeyOut]])
async def get_my_api_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的 API Key 元数据"""
    key = await UserApiKeyService.get_by_user(db, current_user.id)
    return ResponseModel(data=UserApiKeyOut.model_validate(key) if key else None)


@router.post("/me/api-key", response_model=ResponseModel[UserApiKeyCreated])
async def create_my_api_key(
    body: Optional[UserApiKeyCreate] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成或替换当前用户的 API Key（明文仅返回一次）"""
    raw_key, api_key = await UserApiKeyService.create_or_replace(
        db, current_user.id, name=body.name if body else None
    )
    return ResponseModel(data=UserApiKeyCreated(
        key=raw_key,
        key_out=UserApiKeyOut.model_validate(api_key),
    ))


@router.delete("/me/api-key", response_model=ResponseModel[None])
async def delete_my_api_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除当前用户的 API Key"""
    await UserApiKeyService.revoke(db, current_user.id)
    return ResponseModel(message="已删除")
