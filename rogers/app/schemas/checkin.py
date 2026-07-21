"""打卡相关 Schema"""

from datetime import date as date_type
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CheckinExerciseCreate(BaseModel):
    """打卡动作记录"""

    exercise_id: UUID
    sets_done: Optional[int] = Field(None, ge=1, description="完成组数")
    reps_done: Optional[int] = Field(None, ge=1, description="每组次数")
    weight_kg: Optional[float] = Field(None, ge=0, description="重量(kg)")


class CheckinCreate(BaseModel):
    """创建打卡请求"""

    date: date_type = Field(description="打卡日期")
    plan_day_id: Optional[UUID] = Field(None, description="关联的训练日ID")
    duration_min: int = Field(gt=0, description="训练时长(分钟)")
    mood: Optional[int] = Field(None, ge=1, le=5, description="心情评分 1-5")
    note: Optional[str] = Field(None, max_length=1000, description="备注")
    exercises: List[CheckinExerciseCreate] = Field(
        default_factory=list, description="完成的动作列表"
    )


class CheckinUpdate(BaseModel):
    """更新打卡请求"""

    duration_min: Optional[int] = Field(None, gt=0)
    mood: Optional[int] = Field(None, ge=1, le=5)
    note: Optional[str] = Field(None, max_length=1000)
    exercises: Optional[List[CheckinExerciseCreate]] = None


class CheckinExerciseOut(BaseModel):
    """打卡动作输出"""

    id: UUID
    exercise_id: UUID
    exercise_name: Optional[str] = None
    sets_done: Optional[int] = None
    reps_done: Optional[int] = None
    weight_kg: Optional[float] = None

    model_config = {"from_attributes": True}


class CheckinOut(BaseModel):
    """打卡输出"""

    id: UUID
    user_id: UUID
    plan_day_id: Optional[UUID] = None
    date: date_type
    duration_min: int
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