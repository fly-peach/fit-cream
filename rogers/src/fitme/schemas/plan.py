"""
训练计划相关 Schemas

定义训练计划三层结构的请求/响应模型：
- PlanExerciseCreate / Update / Out: 计划中的动作
- PlanDayCreate / Out: 训练日（含动作列表）
- PlanCreate / Update / Out: 训练计划主体（含训练日）
- PlanListOut: 计划列表摘要（不含详细训练日）
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ===== Exercise in Plan =====
class PlanExerciseCreate(BaseModel):
    """计划中动作创建"""
    exercise_id: UUID
    sets: int = Field(ge=1, le=20)
    reps: int = Field(ge=1, le=100)
    weight_kg: Optional[float] = Field(default=None, ge=0)
    sort_order: int = 0


class PlanExerciseUpdate(BaseModel):
    """计划中动作更新"""
    sets: Optional[int] = Field(default=None, ge=1, le=20)
    reps: Optional[int] = Field(default=None, ge=1, le=100)
    weight_kg: Optional[float] = Field(default=None, ge=0)
    sort_order: Optional[int] = None


class PlanExerciseOut(BaseModel):
    """计划中动作输出"""
    id: UUID
    exercise_id: UUID
    exercise_name: Optional[str] = None
    sets: int
    reps: int
    weight_kg: Optional[float] = None
    sort_order: int

    model_config = {"from_attributes": True}


# ===== Plan Day =====
class PlanDayCreate(BaseModel):
    """训练日创建"""
    day_of_week: int = Field(ge=1, le=7, description="1=周一 ... 7=周日")
    focus: Optional[str] = Field(default=None, max_length=100)
    rest_seconds: int = Field(default=60, ge=0)
    exercises: List[PlanExerciseCreate] = Field(default_factory=list)


class PlanDayOut(BaseModel):
    """训练日输出"""
    id: UUID
    day_of_week: int
    focus: Optional[str] = None
    rest_seconds: int
    exercises: List[PlanExerciseOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ===== Plan =====
class PlanCreate(BaseModel):
    """创建训练计划"""
    name: str = Field(min_length=1, max_length=200)
    goal: Optional[str] = Field(
        default=None,
        pattern="^(lose_fat|gain_muscle|maintain|improve_health)$",
    )
    difficulty: Optional[str] = Field(
        default="beginner",
        pattern="^(beginner|intermediate|advanced)$",
    )
    weeks: Optional[int] = Field(default=None, ge=1, le=52)
    days: List[PlanDayCreate] = Field(default_factory=list)


class PlanUpdate(BaseModel):
    """更新训练计划"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    goal: Optional[str] = Field(
        default=None,
        pattern="^(lose_fat|gain_muscle|maintain|improve_health)$",
    )
    difficulty: Optional[str] = Field(
        default=None,
        pattern="^(beginner|intermediate|advanced)$",
    )
    weeks: Optional[int] = Field(default=None, ge=1, le=52)
    status: Optional[str] = Field(
        default=None,
        pattern="^(active|archived|completed)$",
    )


class PlanOut(BaseModel):
    """训练计划输出"""
    id: UUID
    name: str
    goal: Optional[str] = None
    difficulty: Optional[str] = None
    weeks: Optional[int] = None
    status: str
    days: List[PlanDayOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlanListOut(BaseModel):
    """训练计划列表输出（不含详细训练日）"""
    id: UUID
    name: str
    goal: Optional[str] = None
    difficulty: Optional[str] = None
    weeks: Optional[int] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}