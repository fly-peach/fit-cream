"""
训练计划相关 Schemas

定义训练计划三层结构的请求/响应模型：
- PlanExerciseCreate / Update / Out: 计划中的动作
- PlanDayCreate / Out: 训练日（含动作列表）
- PlanCreate / Update / Out: 训练计划主体（含训练日）
- PlanListOut: 计划列表摘要（不含详细训练日）
"""
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ===== Exercise in Plan =====
from src.fitme.schemas.exercise import ExerciseBrief  # noqa: F401


class PlanExerciseCreate(BaseModel):
    """计划中动作创建（动作库动作二选一：exercise_id 或 custom_name）"""
    exercise_id: Optional[UUID] = None
    custom_name: Optional[str] = Field(default=None, max_length=200)
    sets: int = Field(ge=1, le=20)
    reps: int = Field(ge=1, le=100)
    weight_kg: Optional[float] = Field(default=None, ge=0)
    sort_order: int = 0
    notes: Optional[str] = Field(default=None, max_length=500)
    metadata_: Optional[dict[str, Any]] = Field(default=None, description="自定义扩展数据")

    @model_validator(mode="after")
    def _require_exercise_source(self):
        if not self.exercise_id and not (self.custom_name and self.custom_name.strip()):
            raise ValueError("需提供 exercise_id 或 custom_name")
        if self.custom_name:
            self.custom_name = self.custom_name.strip()
        return self


class PlanExerciseUpdate(BaseModel):
    """计划中动作更新"""
    sets: Optional[int] = Field(default=None, ge=1, le=20)
    reps: Optional[int] = Field(default=None, ge=1, le=100)
    weight_kg: Optional[float] = Field(default=None, ge=0)
    sort_order: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    metadata_: Optional[dict[str, Any]] = Field(default=None, description="自定义扩展数据")


class PlanExerciseOut(BaseModel):
    """计划中动作输出"""
    id: UUID
    exercise_id: Optional[UUID] = None
    custom_name: Optional[str] = None
    exercise_name: Optional[str] = None
    sets: int
    reps: int
    weight_kg: Optional[float] = None
    sort_order: int
    notes: Optional[str] = None
    metadata_: Optional[dict[str, Any]] = None
    exercise: Optional[ExerciseBrief] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _fill_exercise_name(self):
        # 模型无 exercise_name 列，从关联动作或自定义名称回填，保证前端可直接展示名称
        if not self.exercise_name:
            if self.exercise is not None:
                self.exercise_name = self.exercise.name
            elif self.custom_name:
                self.exercise_name = self.custom_name
        return self


# ===== Plan Day =====
class PlanDayCreate(BaseModel):
    """训练日创建"""
    day_of_week: int = Field(ge=1, le=7, description="1=周一 ... 7=周日")
    focus: Optional[str] = Field(default=None, max_length=100)
    rest_seconds: int = Field(default=60, ge=0)
    metadata_: Optional[dict[str, Any]] = Field(default=None, description="自定义扩展数据")
    exercises: List[PlanExerciseCreate] = Field(default_factory=list)


class PlanDayUpdate(BaseModel):
    """训练日更新"""
    focus: Optional[str] = Field(default=None, max_length=100)
    rest_seconds: Optional[int] = Field(default=None, ge=0)
    metadata_: Optional[dict[str, Any]] = Field(default=None, description="自定义扩展数据")


class PlanDayOut(BaseModel):
    """训练日输出"""
    id: UUID
    day_of_week: int
    focus: Optional[str] = None
    rest_seconds: int
    metadata_: Optional[dict[str, Any]] = None
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