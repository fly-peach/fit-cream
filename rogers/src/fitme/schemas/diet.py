"""
饮食记录 Schemas

DietMeal: 实际每餐记录
DailyDietSummary: 每日营养汇总
CustomFoodItem: 用户自定义食物
"""
from datetime import date as date_type
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DietMealCreate(BaseModel):
    """创建餐食记录"""
    meal_date: date_type
    meal_type: str = Field(pattern="^(breakfast|lunch|dinner|snack)$", description="餐次")
    food_name: str = Field(min_length=1, max_length=200)
    portion: Optional[str] = Field(default=None, max_length=100)
    calories: int = Field(default=0, ge=0)
    protein_g: Optional[float] = Field(default=None, ge=0)
    carbs_g: Optional[float] = Field(default=None, ge=0)
    fat_g: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=500)
    custom_food_item_id: Optional[UUID] = None


class DietMealBatchCreate(BaseModel):
    meals: List[DietMealCreate] = Field(min_length=1, max_length=20)


class DietMealUpdate(BaseModel):
    """更新餐食记录"""
    meal_type: Optional[str] = Field(default=None, pattern="^(breakfast|lunch|dinner|snack)$")
    food_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    portion: Optional[str] = Field(default=None, max_length=100)
    calories: Optional[int] = Field(default=None, ge=0)
    protein_g: Optional[float] = Field(default=None, ge=0)
    carbs_g: Optional[float] = Field(default=None, ge=0)
    fat_g: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=500)


class DietMealOut(BaseModel):
    """餐食记录输出"""
    id: UUID
    user_id: UUID
    meal_date: date_type
    meal_type: str
    food_name: str
    portion: Optional[str] = None
    calories: int
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    note: Optional[str] = None
    custom_food_item_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DailyDietSummaryOut(BaseModel):
    """每日营养汇总输出"""
    id: UUID
    user_id: UUID
    summary_date: date_type
    total_calories: int
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    protein_goal_met: bool
    carbs_goal_met: bool
    fat_goal_met: bool
    meal_count: int
    note: Optional[str] = None

    model_config = {"from_attributes": True}


class CustomFoodItemCreate(BaseModel):
    """创建自定义食物"""
    name: str = Field(min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, max_length=50)
    portion: str = Field(default="100g", max_length=100)
    calories_per_portion: int = Field(ge=0)
    protein_g_per_portion: Optional[float] = Field(default=None, ge=0)
    carbs_g_per_portion: Optional[float] = Field(default=None, ge=0)
    fat_g_per_portion: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=500)


class CustomFoodItemUpdate(BaseModel):
    """更新自定义食物"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, max_length=50)
    portion: Optional[str] = Field(default=None, max_length=100)
    calories_per_portion: Optional[int] = Field(default=None, ge=0)
    protein_g_per_portion: Optional[float] = Field(default=None, ge=0)
    carbs_g_per_portion: Optional[float] = Field(default=None, ge=0)
    fat_g_per_portion: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=500)


class CustomFoodItemOut(BaseModel):
    """自定义食物输出"""
    id: UUID
    user_id: UUID
    name: str
    category: Optional[str] = None
    portion: str
    calories_per_portion: int
    protein_g_per_portion: Optional[float] = None
    carbs_g_per_portion: Optional[float] = None
    fat_g_per_portion: Optional[float] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
