"""
用户相关 Schemas

定义用户信息输出和更新的请求/响应模型。
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserGoalsOut(BaseModel):
    """用户目标输出（健身目标 + 营养目标 + 通知偏好）"""

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


class UserFitnessProfileOut(BaseModel):
    """用户健身画像输出（Intake 五维数据全字段）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    # health_safety 健康与安全基线
    medical_history: Optional[str] = None
    injuries: Optional[str] = None
    allergies: Optional[str] = None
    pregnancy: Optional[str] = None
    medication: Optional[str] = None
    parq_result: Optional[str] = None
    doctor_advice: Optional[str] = None
    # fitness_level 当前体能水平
    training_experience: Optional[str] = None
    cardio_level: Optional[str] = None
    strength_level: Optional[str] = None
    flexibility: Optional[str] = None
    body_fat_pct: Optional[float] = None
    # exercise_history 运动经历与习惯
    weekly_frequency: Optional[str] = None
    session_duration: Optional[str] = None
    preferred_types: Optional[str] = None
    past_results: Optional[str] = None
    # lifestyle 生活方式与客观环境
    occupation_schedule: Optional[str] = None
    diet_habits: Optional[str] = None
    sleep_quality: Optional[str] = None
    stress_level: Optional[str] = None
    equipment: Optional[str] = None
    preferred_time: Optional[str] = None
    # diet_profile 饮食偏好与结构
    diet_preferences: Optional[str] = None
    food_allergies: Optional[str] = None
    cooking_condition: Optional[str] = None
    meals_per_day: Optional[str] = None
    eating_out_ratio: Optional[str] = None
    budget: Optional[str] = None
    updated_at: datetime


class UserFitnessProfileUpdate(BaseModel):
    """用户健身画像更新（部分更新，仅传需要修改的字段）"""

    # health_safety 健康与安全基线
    medical_history: Optional[str] = Field(default=None, max_length=2000)
    injuries: Optional[str] = Field(default=None, max_length=2000)
    allergies: Optional[str] = Field(default=None, max_length=500)
    pregnancy: Optional[str] = Field(default=None, max_length=200)
    medication: Optional[str] = Field(default=None, max_length=500)
    parq_result: Optional[str] = Field(
        default=None, pattern="^(low|uncertain|high)$"
    )
    doctor_advice: Optional[str] = Field(default=None, max_length=500)
    # fitness_level 当前体能水平
    training_experience: Optional[str] = Field(
        default=None, pattern="^(never|beginner|intermediate|advanced)$"
    )
    cardio_level: Optional[str] = Field(
        default=None, pattern="^(beginner|intermediate|advanced)$"
    )
    strength_level: Optional[str] = Field(
        default=None, pattern="^(beginner|intermediate|advanced)$"
    )
    flexibility: Optional[str] = Field(
        default=None, pattern="^(limited|normal|good)$"
    )
    body_fat_pct: Optional[float] = Field(default=None, ge=0, le=100)
    # exercise_history 运动经历与习惯
    weekly_frequency: Optional[str] = Field(
        default=None, pattern="^(0|1-2|3-4|5\\+)$"
    )
    session_duration: Optional[str] = Field(
        default=None, pattern="^(<30|30-60|>60)$"
    )
    preferred_types: Optional[str] = Field(default=None, max_length=500)
    past_results: Optional[str] = Field(default=None, max_length=2000)
    # lifestyle 生活方式与客观环境
    occupation_schedule: Optional[str] = Field(default=None, max_length=500)
    diet_habits: Optional[str] = Field(default=None, max_length=2000)
    sleep_quality: Optional[str] = Field(
        default=None, pattern="^(poor|normal|good)$"
    )
    stress_level: Optional[str] = Field(
        default=None, pattern="^(low|medium|high)$"
    )
    equipment: Optional[str] = Field(default=None, max_length=500)
    preferred_time: Optional[str] = Field(
        default=None, pattern="^(morning|noon|evening|flexible)$"
    )
    # diet_profile 饮食偏好与结构
    diet_preferences: Optional[str] = Field(default=None, max_length=500)
    food_allergies: Optional[str] = Field(default=None, max_length=500)
    cooking_condition: Optional[str] = Field(default=None, max_length=500)
    meals_per_day: Optional[str] = Field(
        default=None, pattern="^(2|3|4|5\\+)$"
    )
    eating_out_ratio: Optional[str] = Field(
        default=None, pattern="^(mostly_out|half|mostly_home)$"
    )
    budget: Optional[str] = Field(default=None, max_length=100)


class UserGoalsUpdate(BaseModel):
    """用户目标更新（部分更新）"""

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
    name: Optional[str] = None
    role: str = "user"
    birth_date: Optional[date] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    bmi: Optional[float] = None
    goal: Optional[str] = None
    created_at: datetime
    goals: Optional[UserGoalsOut] = None


class UserUpdate(BaseModel):
    """用户资料更新（部分更新，仅传需要修改的字段）"""

    name: Optional[str] = Field(default=None, max_length=100)
    birth_date: Optional[date] = None
    gender: Optional[str] = Field(default=None, pattern="^(male|female|other)$")
    height_cm: Optional[float] = Field(default=None, gt=0, le=300)
    weight_kg: Optional[float] = Field(default=None, gt=0, le=500)
    goal: Optional[str] = Field(
        default=None, pattern="^(lose_fat|gain_muscle|maintain|improve_health)$"
    )


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
