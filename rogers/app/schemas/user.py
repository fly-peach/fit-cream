"""
用户相关 Schemas

定义用户信息输出和更新的请求/响应模型。
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    """用户信息输出（不含密码）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    goal: Optional[str] = None
    created_at: datetime


class UserUpdate(BaseModel):
    """用户资料更新（部分更新，仅传需要修改的字段）"""

    name: Optional[str] = Field(default=None, max_length=100)
    height_cm: Optional[float] = Field(default=None, gt=0, le=300)
    weight_kg: Optional[float] = Field(default=None, gt=0, le=500)
    age: Optional[int] = Field(default=None, gt=0, le=150)
    gender: Optional[str] = Field(default=None, pattern="^(male|female|other)$")
    goal: Optional[str] = Field(
        default=None, pattern="^(lose_fat|gain_muscle|maintain|improve_health)$"
    )