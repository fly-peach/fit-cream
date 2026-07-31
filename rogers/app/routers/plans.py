"""
训练计划路由 /api/plans/*

提供训练计划的完整 CRUD 端点。
所有端点需要 JWT 认证（Bearer Token）。
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import PaginatedResponse, ResponseModel
from src.fitme.schemas.plan import (
    PlanCreate,
    PlanDayCreate,
    PlanDayUpdate,
    PlanExerciseCreate,
    PlanExerciseUpdate,
    PlanListOut,
    PlanOut,
    PlanUpdate,
)
from src.fitme.services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=ResponseModel[PaginatedResponse[PlanListOut]], operation_id="list_plans")
async def list_plans(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(active|archived|completed)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取训练计划列表"""
    plans, total = await PlanService.list_plans(
        db, user.id, page=page, size=size, status=status
    )
    return ResponseModel(
        data=PaginatedResponse(
            items=[PlanListOut.model_validate(p) for p in plans],
            total=total,
            page=page,
            size=size,
        )
    )


@router.get("/active", response_model=ResponseModel[Optional[PlanOut]], operation_id="get_active_plan")
async def get_active_plan(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前活跃计划"""
    plan = await PlanService.get_active_plan(db, user.id)
    return ResponseModel(data=PlanOut.model_validate(plan) if plan else None)


@router.get("/{plan_id}", response_model=ResponseModel[PlanOut], operation_id="get_plan")
async def get_plan(
    plan_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取计划详情（含训练日和动作）"""
    plan = await PlanService.get_plan_detail(db, plan_id, user.id)
    return ResponseModel(data=PlanOut.model_validate(plan))


@router.post("", response_model=ResponseModel[PlanOut], operation_id="create_plan")
async def create_plan(
    data: PlanCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建训练计划"""
    plan = await PlanService.create_plan(db, user.id, data)
    await db.commit()
    await db.refresh(plan)
    return ResponseModel(data=PlanOut.model_validate(plan))


@router.put("/{plan_id}", response_model=ResponseModel[PlanOut], operation_id="update_plan")
async def update_plan(
    plan_id: UUID,
    data: PlanUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新训练计划"""
    plan = await PlanService.update_plan(db, plan_id, user.id, data)
    await db.commit()
    await db.refresh(plan)
    return ResponseModel(data=PlanOut.model_validate(plan))


@router.delete("/{plan_id}", response_model=ResponseModel[None], operation_id="delete_plan")
async def delete_plan(
    plan_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除训练计划（物理删除）"""
    await PlanService.delete_plan(db, plan_id, user.id)
    await db.commit()
    return ResponseModel(message="计划已删除")


@router.post("/{plan_id}/days", response_model=ResponseModel[PlanOut], operation_id="add_plan_day")
async def add_plan_day(
    plan_id: UUID,
    data: PlanDayCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为计划添加训练日"""
    await PlanService.add_plan_day(db, plan_id, user.id, data)
    await db.commit()
    # 重新获取完整计划
    plan = await PlanService.get_plan_detail(db, plan_id, user.id)
    return ResponseModel(data=PlanOut.model_validate(plan))


@router.delete("/days/{day_id}", response_model=ResponseModel[PlanOut], operation_id="delete_plan_day")
async def delete_plan_day(
    day_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除训练日"""
    _, plan = await PlanService.delete_plan_day(db, day_id, user.id)
    await db.commit()
    updated = await PlanService.get_plan_detail(db, plan.id, user.id)
    return ResponseModel(data=PlanOut.model_validate(updated))


@router.put("/days/{day_id}", response_model=ResponseModel[PlanOut], operation_id="update_plan_day")
async def update_plan_day(
    day_id: UUID,
    data: PlanDayUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新训练日（重点、休息时长、自定义数据）"""
    plan_day = await PlanService.update_plan_day(db, day_id, user.id, data)
    await db.commit()
    # 重新获取完整计划
    plan = await PlanService.get_plan_detail(db, plan_day.plan_id, user.id)
    return ResponseModel(data=PlanOut.model_validate(plan))


@router.post("/days/{day_id}/exercises", response_model=ResponseModel[PlanOut], operation_id="add_plan_exercise")
async def add_exercise_to_day(
    day_id: UUID,
    data: PlanExerciseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为训练日添加动作"""
    _, plan = await PlanService.add_exercise_to_day(db, day_id, user.id, data)
    await db.commit()
    updated = await PlanService.get_plan_detail(db, plan.id, user.id)
    return ResponseModel(data=PlanOut.model_validate(updated))


@router.put("/exercises/{exercise_id}", response_model=ResponseModel[PlanOut], operation_id="update_plan_exercise")
async def update_exercise(
    exercise_id: UUID,
    data: PlanExerciseUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新训练动作（组数、次数、重量）"""
    _, plan = await PlanService.update_exercise(db, exercise_id, user.id, data)
    await db.commit()
    updated = await PlanService.get_plan_detail(db, plan.id, user.id)
    return ResponseModel(data=PlanOut.model_validate(updated))


@router.delete("/exercises/{exercise_id}", response_model=ResponseModel[PlanOut], operation_id="delete_plan_exercise")
async def delete_exercise(
    exercise_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除训练动作"""
    _, plan = await PlanService.delete_exercise(db, exercise_id, user.id)
    await db.commit()
    updated = await PlanService.get_plan_detail(db, plan.id, user.id)
    return ResponseModel(data=PlanOut.model_validate(updated))
