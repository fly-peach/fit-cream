"""
饮食记录路由 /api/diet-meals/*

提供每餐记录的CRUD和每日营养汇总查询。
所有端点需要JWT认证。
"""
from datetime import date as date_type
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import PaginatedResponse, ResponseModel
from src.fitme.schemas.diet import (
    CustomFoodItemCreate,
    CustomFoodItemOut,
    CustomFoodItemUpdate,
    DailyDietSummaryOut,
    DietMealBatchCreate,
    DietMealCreate,
    DietMealOut,
    DietMealUpdate,
)
from src.fitme.services.diet_meal_service import CustomFoodItemService, DietMealService

router = APIRouter(prefix="/diet-meals", tags=["diet-meals"])


# ---- DietMeal list / create endpoints ----
@router.get("", response_model=ResponseModel[PaginatedResponse[DietMealOut]])
async def list_meals(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    start: Optional[date_type] = Query(None),
    end: Optional[date_type] = Query(None),
    meal_type: Optional[str] = Query(None, description="breakfast/lunch/dinner/snack"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meals, total = await DietMealService.list_meals(
        db, user.id, start=start, end=end, meal_type=meal_type, page=page, size=size
    )
    return ResponseModel(
        data=PaginatedResponse(
            items=[DietMealOut.model_validate(m) for m in meals],
            total=total,
            page=page,
            size=size,
        )
    )


@router.post("", response_model=ResponseModel[DietMealOut])
async def create_meal(
    data: DietMealCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meal = await DietMealService.create_meal(db, user.id, data.model_dump())
    await db.commit()
    await db.refresh(meal)
    return ResponseModel(data=DietMealOut.model_validate(meal))


# ---- Daily summary endpoints ----
@router.get("/summary", response_model=ResponseModel[DailyDietSummaryOut])
async def get_daily_summary(
    date: date_type = Query(description="查询日期 YYYY-MM-DD"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await DietMealService.get_summary(db, user.id, date)
    return ResponseModel(data=DailyDietSummaryOut.model_validate(summary))


@router.get("/summaries", response_model=ResponseModel[list[DailyDietSummaryOut]])
async def list_daily_summaries(
    start: Optional[date_type] = Query(None),
    end: Optional[date_type] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summaries = await DietMealService.list_summaries(db, user.id, start=start, end=end)
    return ResponseModel(data=[DailyDietSummaryOut.model_validate(s) for s in summaries])


# ---- Custom Food Item endpoints (before /{meal_id} to avoid path conflicts) ----
@router.get("/foods/list", response_model=ResponseModel[list[CustomFoodItemOut]])
async def list_custom_foods(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await CustomFoodItemService.list_by_user(db, user.id, category=category, keyword=keyword)
    return ResponseModel(data=[CustomFoodItemOut.model_validate(i) for i in items])


@router.post("/foods", response_model=ResponseModel[CustomFoodItemOut])
async def create_custom_food(
    data: CustomFoodItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await CustomFoodItemService.create(db, user.id, data.model_dump())
    await db.commit()
    await db.refresh(item)
    return ResponseModel(data=CustomFoodItemOut.model_validate(item))


@router.put("/foods/{food_id}", response_model=ResponseModel[CustomFoodItemOut])
async def update_custom_food(
    food_id: UUID,
    data: CustomFoodItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await CustomFoodItemService.update(
        db, food_id, user.id, data.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ResponseModel(data=CustomFoodItemOut.model_validate(item))


@router.delete("/foods/{food_id}", response_model=ResponseModel[None])
async def delete_custom_food(
    food_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await CustomFoodItemService.delete(db, food_id, user.id)
    await db.commit()
    return ResponseModel(message="食物已删除")


# ---- Batch create (before /{meal_id} to avoid path conflicts) ----
@router.post("/batch", response_model=ResponseModel[list[DietMealOut]])
async def batch_create_meals(
    data: DietMealBatchCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meals = await DietMealService.batch_create_meals(
        db, user.id, [m.model_dump() for m in data.meals]
    )
    await db.commit()
    return ResponseModel(data=[DietMealOut.model_validate(m) for m in meals])


# ---- DietMeal by ID endpoints (after static/named routes) ----
@router.get("/{meal_id}", response_model=ResponseModel[DietMealOut])
async def get_meal(
    meal_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meal = await DietMealService.get_by_id(db, meal_id, user.id)
    return ResponseModel(data=DietMealOut.model_validate(meal))


@router.put("/{meal_id}", response_model=ResponseModel[DietMealOut])
async def update_meal(
    meal_id: UUID,
    data: DietMealUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meal = await DietMealService.update_meal(
        db, meal_id, user.id, data.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ResponseModel(data=DietMealOut.model_validate(meal))


@router.delete("/{meal_id}", response_model=ResponseModel[None])
async def delete_meal(
    meal_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await DietMealService.delete_meal(db, meal_id, user.id)
    await db.commit()
    return ResponseModel(message="饮食记录已删除")
