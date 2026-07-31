"""
用户相关 Schemas

定义用户信息输出和更新的请求/响应模型。
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserSettingsOut(BaseModel):
    """用户设置输出"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    goal: Optional[str] = None
    target_weight_kg: Optional[float] = None
    target_body_fat_pct: Optional[float] = None
    weekly_training_goal: int = 5
    calorie_goal: int = 2000
    protein_goal_g: int = 150
    carbs_goal_g: int = 250
    fat_goal_g: int = 65
    notification_enabled: bool = True
    updated_at: datetime


class UserSettingsUpdate(BaseModel):
    """用户设置更新（部分更新）"""

    goal: Optional[str] = Field(
        default=None, pattern="^(lose_fat|gain_muscle|maintain|improve_health)$"
    )
    target_weight_kg: Optional[float] = Field(default=None, gt=0, le=500)
    target_body_fat_pct: Optional[float] = Field(default=None, ge=0, le=100)
    weekly_training_goal: Optional[int] = Field(default=None, ge=1, le=14)
    calorie_goal: Optional[int] = Field(default=None, ge=500, le=10000)
    protein_goal_g: Optional[int] = Field(default=None, ge=0, le=500)
    carbs_goal_g: Optional[int] = Field(default=None, ge=0, le=1000)
    fat_goal_g: Optional[int] = Field(default=None, ge=0, le=300)
    notification_enabled: Optional[bool] = None


class HealthMetricOut(BaseModel):
    """健康指标输出"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    measure_date: date
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    bmi: Optional[float] = None
    bmi_status: Optional[str] = None
    chest_cm: Optional[float] = None
    waist_cm: Optional[float] = None
    hip_cm: Optional[float] = None
    arm_cm: Optional[float] = None
    thigh_cm: Optional[float] = None
    note: Optional[str] = None
    created_at: datetime


class HealthMetricCreate(BaseModel):
    """健康指标创建"""

    measure_date: date
    height_cm: Optional[float] = Field(default=None, gt=0, le=300)
    weight_kg: Optional[float] = Field(default=None, gt=0, le=500)
    body_fat_pct: Optional[float] = Field(default=None, ge=0, le=100)
    muscle_mass_kg: Optional[float] = Field(default=None, ge=0, le=500)
    chest_cm: Optional[float] = Field(default=None, ge=0, le=500)
    waist_cm: Optional[float] = Field(default=None, ge=0, le=500)
    hip_cm: Optional[float] = Field(default=None, ge=0, le=500)
    arm_cm: Optional[float] = Field(default=None, ge=0, le=500)
    thigh_cm: Optional[float] = Field(default=None, ge=0, le=500)
    note: Optional[str] = Field(default=None, max_length=500)


class HealthMetricUpdate(BaseModel):
    """健康指标更新（部分更新）"""

    measure_date: Optional[date] = None
    height_cm: Optional[float] = Field(default=None, gt=0, le=300)
    weight_kg: Optional[float] = Field(default=None, gt=0, le=500)
    body_fat_pct: Optional[float] = Field(default=None, ge=0, le=100)
    muscle_mass_kg: Optional[float] = Field(default=None, ge=0, le=500)
    chest_cm: Optional[float] = Field(default=None, ge=0, le=500)
    waist_cm: Optional[float] = Field(default=None, ge=0, le=500)
    hip_cm: Optional[float] = Field(default=None, ge=0, le=500)
    arm_cm: Optional[float] = Field(default=None, ge=0, le=500)
    thigh_cm: Optional[float] = Field(default=None, ge=0, le=500)
    note: Optional[str] = Field(default=None, max_length=500)


class UserOut(BaseModel):
    """用户信息输出（不含密码）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    role: str = "user"
    age: Optional[int] = None
    gender: Optional[str] = None
    created_at: datetime
    settings: Optional[UserSettingsOut] = None


class UserUpdate(BaseModel):
    """用户资料更新（部分更新，仅传需要修改的字段）"""

    name: Optional[str] = Field(default=None, max_length=100)
    age: Optional[int] = Field(default=None, gt=0, le=150)
    gender: Optional[str] = Field(default=None, pattern="^(male|female|other)$")


class UserApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    key_prefix: str
    name: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class UserApiKeyCreated(BaseModel):
    key: str
    key_out: UserApiKeyOut


class UserApiKeyCreate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
