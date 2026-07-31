"""动作库 Schemas"""
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExerciseCreate(BaseModel):
    """创建动作请求（admin）"""
    name: str = Field(min_length=1, max_length=200)
    name_en: Optional[str] = Field(default=None, max_length=200)
    muscle_group: Optional[str] = Field(default=None, max_length=50)
    muscle_subgroup: Optional[str] = Field(default=None, max_length=50)
    muscle_subgroup_zh: Optional[str] = Field(default=None, max_length=50)
    category: Optional[str] = Field(default=None, max_length=50)
    is_compound: bool = False
    equipment: Optional[str] = Field(default=None, max_length=100)
    equipment_zh: Optional[str] = Field(default=None, max_length=100)
    difficulty: Optional[str] = Field(default=None, max_length=20)
    calories_per_min: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = None
    instructions: Optional[str] = None
    tips: Optional[str] = None
    body_part: Optional[str] = Field(default=None, max_length=50)
    body_part_zh: Optional[str] = Field(default=None, max_length=50)
    target: Optional[str] = Field(default=None, max_length=50)
    target_zh: Optional[str] = Field(default=None, max_length=50)
    secondary_muscles: Optional[List[str]] = None
    secondary_muscles_zh: Optional[List[str]] = None
    instruction_steps: Optional[List[str]] = None
    instruction_steps_en: Optional[List[str]] = None
    instructions_en: Optional[str] = None
    media_id: Optional[str] = Field(default=None, max_length=100)
    image: Optional[str] = Field(default=None, max_length=255)
    gif_url: Optional[str] = Field(default=None, max_length=255)
    attribution: Optional[str] = Field(default=None, max_length=255)


class ExerciseUpdate(BaseModel):
    """更新动作请求（admin）"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    name_en: Optional[str] = Field(default=None, max_length=200)
    muscle_group: Optional[str] = Field(default=None, max_length=50)
    muscle_subgroup: Optional[str] = Field(default=None, max_length=50)
    muscle_subgroup_zh: Optional[str] = Field(default=None, max_length=50)
    category: Optional[str] = Field(default=None, max_length=50)
    is_compound: Optional[bool] = None
    equipment: Optional[str] = Field(default=None, max_length=100)
    equipment_zh: Optional[str] = Field(default=None, max_length=100)
    difficulty: Optional[str] = Field(default=None, max_length=20)
    calories_per_min: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = None
    instructions: Optional[str] = None
    tips: Optional[str] = None
    body_part: Optional[str] = Field(default=None, max_length=50)
    body_part_zh: Optional[str] = Field(default=None, max_length=50)
    target: Optional[str] = Field(default=None, max_length=50)
    target_zh: Optional[str] = Field(default=None, max_length=50)
    secondary_muscles: Optional[List[str]] = None
    secondary_muscles_zh: Optional[List[str]] = None
    instruction_steps: Optional[List[str]] = None
    instruction_steps_en: Optional[List[str]] = None
    instructions_en: Optional[str] = None
    media_id: Optional[str] = Field(default=None, max_length=100)
    image: Optional[str] = Field(default=None, max_length=255)
    gif_url: Optional[str] = Field(default=None, max_length=255)
    attribution: Optional[str] = Field(default=None, max_length=255)


class ExerciseOut(BaseModel):
    """动作输出"""
    id: UUID
    name: str
    name_en: Optional[str] = None
    muscle_group: Optional[str] = None
    muscle_subgroup: Optional[str] = None
    muscle_subgroup_zh: Optional[str] = None
    category: Optional[str] = None
    is_compound: bool = False
    equipment: Optional[str] = None
    equipment_zh: Optional[str] = None
    difficulty: Optional[str] = None
    calories_per_min: Optional[float] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    instructions: Optional[str] = None
    tips: Optional[str] = None
    body_part: Optional[str] = None
    body_part_zh: Optional[str] = None
    target: Optional[str] = None
    target_zh: Optional[str] = None
    secondary_muscles: Optional[List[str]] = None
    secondary_muscles_zh: Optional[List[str]] = None
    instruction_steps: Optional[List[str]] = None
    instruction_steps_en: Optional[List[str]] = None
    instructions_en: Optional[str] = None
    media_id: Optional[str] = None
    image: Optional[str] = None
    gif_url: Optional[str] = None
    attribution: Optional[str] = None

    model_config = {"from_attributes": True}


class ExerciseBrief(BaseModel):
    """动作库摘要（嵌入计划动作输出）"""
    name: str
    name_en: Optional[str] = None
    muscle_group: Optional[str] = None
    muscle_subgroup: Optional[str] = None
    muscle_subgroup_zh: Optional[str] = None
    category: Optional[str] = None
    is_compound: bool = False
    equipment: Optional[str] = None
    equipment_zh: Optional[str] = None
    difficulty: Optional[str] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    body_part: Optional[str] = None
    body_part_zh: Optional[str] = None
    target: Optional[str] = None
    target_zh: Optional[str] = None
    image: Optional[str] = None

    model_config = {"from_attributes": True}


class CategoryStats(BaseModel):
    """分类统计"""
    name: str
    count: int


class MuscleGroupStats(BaseModel):
    """肌群统计"""
    name: str
    count: int


class EquipmentStats(BaseModel):
    """器械统计"""
    name: str
    count: int
