"""饮食计划相关 Schemas"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ===== Meal =====
class DietMealCreate(BaseModel):
    """餐食创建"""
    meal_type: str = Field(pattern="^(breakfast|lunch|dinner|snack)$")
    food_name: str = Field(min_length=1, max_length=200)
    calories: Optional[int] = Field(default=None, ge=0)
    protein_g: Optional[float] = Field(default=None, ge=0)
    carbs_g: Optional[float] = Field(default=None, ge=0)
    fat_g: Optional[float] = Field(default=None, ge=0)
    portion: Optional[str] = Field(default=None, max_length=100)
    sort_order: int = 0


class DietMealUpdate(BaseModel):
    """餐食更新"""
    meal_type: Optional[str] = Field(default=None, pattern="^(breakfast|lunch|dinner|snack)$")
    food_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    calories: Optional[int] = Field(default=None, ge=0)
    protein_g: Optional[float] = Field(default=None, ge=0)
    carbs_g: Optional[float] = Field(default=None, ge=0)
    fat_g: Optional[float] = Field(default=None, ge=0)
    portion: Optional[str] = Field(default=None, max_length=100)
    sort_order: Optional[int] = None


class DietMealOut(BaseModel):
    """餐食输出"""
    id: UUID
    meal_type: str
    food_name: str
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    portion: Optional[str] = None
    sort_order: int

    model_config = {"from_attributes": True}


# ===== DietPlanDay =====
class DietDayCreate(BaseModel):
    """饮食日创建"""
    day_of_week: int = Field(ge=1, le=7, description="1=周一 ... 7=周日")
    focus: Optional[str] = Field(default=None, max_length=100)
    meals: List[DietMealCreate] = Field(default_factory=list)


class DietDayOut(BaseModel):
    """饮食日输出"""
    id: UUID
    day_of_week: int
    focus: Optional[str] = None
    meals: List[DietMealOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ===== DietPlan =====
class DietPlanCreate(BaseModel):
    """创建饮食计划"""
    name: str = Field(min_length=1, max_length=200)
    target_calories: Optional[int] = Field(default=None, ge=0)
    goal: Optional[str] = Field(
        default=None,
        pattern="^(lose_fat|gain_muscle|maintain|improve_health)$",
    )
    days: List[DietDayCreate] = Field(default_factory=list)


class DietPlanUpdate(BaseModel):
    """更新饮食计划"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    target_calories: Optional[int] = Field(default=None, ge=0)
    goal: Optional[str] = Field(
        default=None,
        pattern="^(lose_fat|gain_muscle|maintain|improve_health)$",
    )
    status: Optional[str] = Field(
        default=None,
        pattern="^(active|archived)$",
    )


class DietPlanOut(BaseModel):
    """饮食计划输出"""
    id: UUID
    name: str
    target_calories: Optional[int] = None
    goal: Optional[str] = None
    status: str
    days: List[DietDayOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DietPlanListOut(BaseModel):
    """饮食计划列表输出"""
    id: UUID
    name: str
    target_calories: Optional[int] = None
    goal: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}