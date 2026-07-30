"""
饮食计划路由 /api/diet-plans/*

提供饮食计划的完整 CRUD 端点。
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
from src.fitme.schemas.diet_plan import (
    DietDayCreate,
    DietDayUpdate,
    DietMealCreate,
    DietMealUpdate,
    DietPlanCreate,
    DietPlanListOut,
    DietPlanOut,
    DietPlanUpdate,
)
from src.fitme.services.diet_plan_service import DietPlanService

router = APIRouter(prefix="/diet-plans", tags=["diet-plans"])


@router.get("", response_model=ResponseModel[PaginatedResponse[DietPlanListOut]])
async def list_diet_plans(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(active|archived)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取饮食计划列表"""
    diet_plans, total = await DietPlanService.list_diet_plans(
        db, user.id, page=page, size=size, status=status
    )
    return ResponseModel(
        data=PaginatedResponse(
            items=[DietPlanListOut.model_validate(p) for p in diet_plans],
            total=total,
            page=page,
            size=size,
        )
    )


@router.get("/active", response_model=ResponseModel[Optional[DietPlanOut]])
async def get_active_diet_plan(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前活跃饮食计划"""
    diet_plan = await DietPlanService.get_active_diet_plan(db, user.id)
    return ResponseModel(data=DietPlanOut.model_validate(diet_plan) if diet_plan else None)


@router.get("/{diet_plan_id}", response_model=ResponseModel[DietPlanOut])
async def get_diet_plan(
    diet_plan_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取饮食计划详情（含饮食日和餐食）"""
    diet_plan = await DietPlanService.get_diet_plan_detail(db, diet_plan_id, user.id)
    return ResponseModel(data=DietPlanOut.model_validate(diet_plan))


@router.post("", response_model=ResponseModel[DietPlanOut])
async def create_diet_plan(
    data: DietPlanCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建饮食计划"""
    diet_plan = await DietPlanService.create_diet_plan(db, user.id, data)
    await db.commit()
    await db.refresh(diet_plan)
    return ResponseModel(data=DietPlanOut.model_validate(diet_plan))


@router.put("/{diet_plan_id}", response_model=ResponseModel[DietPlanOut])
async def update_diet_plan(
    diet_plan_id: UUID,
    data: DietPlanUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新饮食计划"""
    diet_plan = await DietPlanService.update_diet_plan(db, diet_plan_id, user.id, data)
    await db.commit()
    await db.refresh(diet_plan)
    return ResponseModel(data=DietPlanOut.model_validate(diet_plan))


@router.delete("/{diet_plan_id}", response_model=ResponseModel[None])
async def delete_diet_plan(
    diet_plan_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """归档饮食计划（软删除）"""
    await DietPlanService.delete_diet_plan(db, diet_plan_id, user.id)
    await db.commit()
    return ResponseModel(message="饮食计划已归档")


@router.post("/{diet_plan_id}/days", response_model=ResponseModel[DietPlanOut])
async def add_diet_day(
    diet_plan_id: UUID,
    data: DietDayCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为饮食计划添加饮食日"""
    await DietPlanService.add_diet_day(db, diet_plan_id, user.id, data)
    await db.commit()
    # 重新获取完整饮食计划
    diet_plan = await DietPlanService.get_diet_plan_detail(db, diet_plan_id, user.id)
    return ResponseModel(data=DietPlanOut.model_validate(diet_plan))


@router.put("/days/{day_id}", response_model=ResponseModel[DietPlanOut])
async def update_diet_day(
    day_id: UUID,
    data: DietDayUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新饮食日（重点、自定义数据）"""
    diet_day = await DietPlanService.update_diet_day(db, day_id, user.id, data)
    await db.commit()
    # 重新获取完整饮食计划
    diet_plan = await DietPlanService.get_diet_plan_detail(db, diet_day.diet_plan_id, user.id)
    return ResponseModel(data=DietPlanOut.model_validate(diet_plan))


@router.post("/days/{day_id}/meals", response_model=ResponseModel[DietPlanOut])
async def add_meal(
    day_id: UUID,
    data: DietMealCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为饮食日添加餐食"""
    _, diet_plan = await DietPlanService.add_meal(db, day_id, user.id, data)
    await db.commit()
    updated = await DietPlanService.get_diet_plan_detail(db, diet_plan.id, user.id)
    return ResponseModel(data=DietPlanOut.model_validate(updated))


@router.put("/meals/{meal_id}", response_model=ResponseModel[DietPlanOut])
async def update_meal(
    meal_id: UUID,
    data: DietMealUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新餐食"""
    _, diet_plan = await DietPlanService.update_meal(db, meal_id, user.id, data)
    await db.commit()
    updated = await DietPlanService.get_diet_plan_detail(db, diet_plan.id, user.id)
    return ResponseModel(data=DietPlanOut.model_validate(updated))


@router.delete("/meals/{meal_id}", response_model=ResponseModel[DietPlanOut])
async def delete_meal(
    meal_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除餐食"""
    _, diet_plan = await DietPlanService.delete_meal(db, meal_id, user.id)
    await db.commit()
    updated = await DietPlanService.get_diet_plan_detail(db, diet_plan.id, user.id)
    return ResponseModel(data=DietPlanOut.model_validate(updated))