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
    """计划中动作创建（动作库动作二选一：exercise_id 或 custom_name）

    力量型需 sets+reps；有氧型（exercise_type=cardio）需 duration_min，无组次。
    """
    exercise_id: Optional[UUID] = None
    custom_name: Optional[str] = Field(default=None, max_length=200)
    exercise_type: Optional[str] = Field(
        default="strength", pattern="^(strength|cardio)$", description="动作类型"
    )
    sets: Optional[int] = Field(default=None, ge=1, le=20)
    reps: Optional[int] = Field(default=None, ge=1, le=100)
    weight_kg: Optional[float] = Field(default=None, ge=0)
    duration_min: Optional[int] = Field(default=None, ge=1, description="有氧时长(分钟)")
    distance_km: Optional[float] = Field(default=None, ge=0, description="有氧距离(km)")
    calories_per_min: Optional[float] = Field(
        default=None, ge=0, description="每分钟消耗(kcal)"
    )
    sort_order: int = 0
    notes: Optional[str] = Field(default=None, max_length=500)
    metadata_: Optional[dict[str, Any]] = Field(default=None, description="自定义扩展数据")

    @model_validator(mode="after")
    def _require_exercise_source(self):
        if not self.exercise_id and not (self.custom_name and self.custom_name.strip()):
            raise ValueError("需提供 exercise_id 或 custom_name")
        if self.custom_name:
            self.custom_name = self.custom_name.strip()
        if self.exercise_type == "cardio":
            if not self.duration_min:
                raise ValueError("有氧动作需提供 duration_min")
        else:
            if not self.sets or not self.reps:
                raise ValueError("力量动作需提供 sets 与 reps")
        return self


class PlanExerciseUpdate(BaseModel):
    """计划中动作更新（均可选，允许 strength/cardio 切换）"""
    exercise_id: Optional[UUID] = Field(default=None, description="关联动作库动作 ID（更换动作）")
    exercise_type: Optional[str] = Field(
        default=None, pattern="^(strength|cardio)$", description="动作类型"
    )
    sets: Optional[int] = Field(default=None, ge=1, le=20)
    reps: Optional[int] = Field(default=None, ge=1, le=100)
    weight_kg: Optional[float] = Field(default=None, ge=0)
    duration_min: Optional[int] = Field(default=None, ge=1, description="有氧时长(分钟)")
    distance_km: Optional[float] = Field(default=None, ge=0, description="有氧距离(km)")
    calories_per_min: Optional[float] = Field(
        default=None, ge=0, description="每分钟消耗(kcal)"
    )
    sort_order: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    metadata_: Optional[dict[str, Any]] = Field(default=None, description="自定义扩展数据")


class PlanExerciseOut(BaseModel):
    """计划中动作输出"""
    id: UUID
    exercise_id: Optional[UUID] = None
    custom_name: Optional[str] = None
    exercise_name: Optional[str] = None
    exercise_type: Optional[str] = None
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_min: Optional[int] = None
    distance_km: Optional[float] = None
    calories_per_min: Optional[float] = None
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


class PlanDaySync(BaseModel):
    """训练日同步（把源星期训练日复制到目标星期）"""
    source_day_of_week: int = Field(ge=1, le=7, description="源训练日星期，1=周一...7=周日")
    target_day_of_week: int = Field(ge=1, le=7, description="目标训练日星期，1=周一...7=周日")


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