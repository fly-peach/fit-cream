"""
打卡相关 Schemas

定义训练打卡的请求/响应模型：
- CheckinExerciseCreate: 打卡中的单个动作记录
- CheckinCreate / CheckinUpdate: 创建/更新打卡请求
- CheckinExerciseOut / CheckinOut: 打卡输出（含动作详情）
- StreakOut: 连续打卡天数统计输出
"""

from datetime import date as date_type
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.fitme.schemas.exercise import ExerciseBrief


class CheckinExerciseCreate(BaseModel):
    """打卡动作记录（exercise_id 与 custom_name 至少一个）"""

    exercise_id: Optional[UUID] = None
    custom_name: Optional[str] = Field(None, max_length=200, description="自定义动作名称")
    plan_day_exercise_id: Optional[UUID] = Field(None, description="关联的计划动作ID")
    sets_done: Optional[int] = Field(None, ge=1, description="完成组数")
    reps_done: Optional[int] = Field(None, ge=1, description="每组次数")
    weight_kg: Optional[float] = Field(None, ge=0, description="重量(kg)")
    duration_min: Optional[int] = Field(None, ge=1, description="有氧实际时长(分钟)")
    distance_km: Optional[float] = Field(None, ge=0, description="有氧实际距离(km)")
    rpe: Optional[int] = Field(None, ge=1, le=10, description="自感用力等级 1-10")
    notes: Optional[str] = Field(None, max_length=500, description="动作备注")

    @model_validator(mode="after")
    def _require_exercise_source(self):
        if not self.exercise_id and not (self.custom_name and self.custom_name.strip()):
            raise ValueError("需提供 exercise_id 或 custom_name")
        if self.custom_name:
            self.custom_name = self.custom_name.strip()
        return self


class CheckinCreate(BaseModel):
    """创建打卡请求"""

    date: date_type = Field(description="打卡日期")
    plan_day_id: Optional[UUID] = Field(None, description="关联的训练日ID")
    duration_min: Optional[int] = Field(None, gt=0, description="训练时长(分钟)，动作勾选建卡可为空")
    actual_intensity: Optional[str] = Field(None, pattern="^(low|medium|high)$", description="实际强度")
    calories_burned: Optional[int] = Field(None, ge=0, description="估算消耗热量(kcal)")
    mood: Optional[int] = Field(None, ge=1, le=5, description="心情评分 1-5")
    note: Optional[str] = Field(None, max_length=1000, description="备注")
    exercises: List[CheckinExerciseCreate] = Field(
        default_factory=list, description="完成的动作列表"
    )


class CheckinUpdate(BaseModel):
    """更新打卡请求"""

    duration_min: Optional[int] = Field(None, gt=0)
    actual_intensity: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    calories_burned: Optional[int] = Field(None, ge=0)
    mood: Optional[int] = Field(None, ge=1, le=5)
    note: Optional[str] = Field(None, max_length=1000)
    exercises: Optional[List[CheckinExerciseCreate]] = None


class CheckinExerciseOut(BaseModel):
    """打卡动作输出"""

    id: UUID
    exercise_id: Optional[UUID] = None
    custom_name: Optional[str] = None
    plan_day_exercise_id: Optional[UUID] = None
    exercise_name: Optional[str] = None
    sets_done: Optional[int] = None
    reps_done: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_min: Optional[int] = None
    distance_km: Optional[float] = None
    rpe: Optional[int] = None
    notes: Optional[str] = None
    exercise: Optional[ExerciseBrief] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _fill_exercise_name(self):
        if not self.exercise_name:
            if self.exercise is not None:
                self.exercise_name = self.exercise.name
            elif self.custom_name:
                self.exercise_name = self.custom_name
        return self


class CheckinOut(BaseModel):
    """打卡输出"""

    id: UUID
    user_id: UUID
    plan_day_id: Optional[UUID] = None
    date: date_type
    duration_min: Optional[int] = None
    actual_intensity: Optional[str] = None
    calories_burned: Optional[int] = None
    mood: Optional[int] = None
    note: Optional[str] = None
    created_at: datetime
    exercises: List[CheckinExerciseOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class StreakOut(BaseModel):
    """连续打卡天数"""

    current_streak: int = Field(description="当前连续天数")
    longest_streak: int = Field(description="最长连续天数")
    last_checkin_date: Optional[date_type] = Field(None, description="最后打卡日期")