"""动作库 Schemas"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExerciseCreate(BaseModel):
    """创建动作请求（admin）"""
    name: str = Field(min_length=1, max_length=200)
    name_en: Optional[str] = Field(default=None, max_length=200)
    muscle_group: Optional[str] = Field(default=None, max_length=50)
    muscle_subgroup: Optional[str] = Field(default=None, max_length=50)
    category: Optional[str] = Field(default=None, max_length=50)
    is_compound: bool = False
    equipment: Optional[str] = Field(default=None, max_length=100)
    difficulty: Optional[str] = Field(default=None, max_length=20)
    calories_per_min: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = None
    instructions: Optional[str] = None
    tips: Optional[str] = None


class ExerciseUpdate(BaseModel):
    """更新动作请求（admin）"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    name_en: Optional[str] = Field(default=None, max_length=200)
    muscle_group: Optional[str] = Field(default=None, max_length=50)
    muscle_subgroup: Optional[str] = Field(default=None, max_length=50)
    category: Optional[str] = Field(default=None, max_length=50)
    is_compound: Optional[bool] = None
    equipment: Optional[str] = Field(default=None, max_length=100)
    difficulty: Optional[str] = Field(default=None, max_length=20)
    calories_per_min: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = None
    instructions: Optional[str] = None
    tips: Optional[str] = None


class ExerciseOut(BaseModel):
    """动作输出"""
    id: UUID
    name: str
    name_en: Optional[str] = None
    muscle_group: Optional[str] = None
    muscle_subgroup: Optional[str] = None
    category: Optional[str] = None
    is_compound: bool = False
    equipment: Optional[str] = None
    difficulty: Optional[str] = None
    calories_per_min: Optional[float] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    tips: Optional[str] = None

    model_config = {"from_attributes": True}


class ExerciseBrief(BaseModel):
    """动作库摘要（嵌入计划动作输出）"""
    name: str
    name_en: Optional[str] = None
    muscle_group: Optional[str] = None
    muscle_subgroup: Optional[str] = None
    category: Optional[str] = None
    is_compound: bool = False
    equipment: Optional[str] = None
    difficulty: Optional[str] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class CategoryStats(BaseModel):
    """分类统计"""
    name: str
    count: int


class MuscleGroupStats(BaseModel):
    """肌群统计"""
    name: str
    count: int
