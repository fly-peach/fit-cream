"""
用户健身画像模型

存储 Intake 信息采集的 5 个非落库维度（health_safety / fitness_level /
exercise_history / lifestyle / diet_profile），改为 typed columns 持久化。
每用户一条，与 User 一对一。列名与前端 form-templates.ts 字段 key 全链路统一。
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from utils.uuid7 import uuid7


class UserFitnessProfile(Base):
    __tablename__ = "user_fitness_profiles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True
    )

    # health_safety 健康与安全基线
    medical_history: Mapped[str | None] = mapped_column(Text)
    injuries: Mapped[str | None] = mapped_column(Text)
    allergies: Mapped[str | None] = mapped_column(String(500))
    pregnancy: Mapped[str | None] = mapped_column(String(200))
    medication: Mapped[str | None] = mapped_column(String(500))
    parq_result: Mapped[str | None] = mapped_column(String(20))
    doctor_advice: Mapped[str | None] = mapped_column(String(500))

    # fitness_level 当前体能水平
    training_experience: Mapped[str | None] = mapped_column(String(20))
    cardio_level: Mapped[str | None] = mapped_column(String(20))
    strength_level: Mapped[str | None] = mapped_column(String(20))
    flexibility: Mapped[str | None] = mapped_column(String(20))
    body_fat_pct: Mapped[float | None] = mapped_column(Numeric(4, 1))

    # exercise_history 运动经历与习惯
    weekly_frequency: Mapped[str | None] = mapped_column(String(10))
    session_duration: Mapped[str | None] = mapped_column(String(10))
    preferred_types: Mapped[str | None] = mapped_column(String(500))
    past_results: Mapped[str | None] = mapped_column(Text)

    # lifestyle 生活方式与客观环境
    occupation_schedule: Mapped[str | None] = mapped_column(String(500))
    diet_habits: Mapped[str | None] = mapped_column(Text)
    sleep_quality: Mapped[str | None] = mapped_column(String(10))
    stress_level: Mapped[str | None] = mapped_column(String(10))
    equipment: Mapped[str | None] = mapped_column(String(500))
    preferred_time: Mapped[str | None] = mapped_column(String(10))

    # diet_profile 饮食偏好与结构
    diet_preferences: Mapped[str | None] = mapped_column(String(500))
    food_allergies: Mapped[str | None] = mapped_column(String(500))
    cooking_condition: Mapped[str | None] = mapped_column(String(500))
    meals_per_day: Mapped[str | None] = mapped_column(String(10))
    eating_out_ratio: Mapped[str | None] = mapped_column(String(20))
    budget: Mapped[str | None] = mapped_column(String(100))

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
