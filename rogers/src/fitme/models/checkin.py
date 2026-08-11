"""
打卡模型

- Checkin: 每日打卡记录（日期、时长、强度、心情、备注、估算热量），同一用户同一天只能打卡一次
- CheckinExercise: 打卡中完成的具体动作（组数、次数、重量、RPE、备注）
"""
from datetime import date as date_type
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from utils.uuid7 import uuid7


class Checkin(Base):
    __tablename__ = "checkins"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_checkin_user_date"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    plan_day_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan_days.id", ondelete="SET NULL"),
        nullable=True,
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    # 动作勾选自动建卡时总时长未知，允许为空
    duration_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_intensity: Mapped[Optional[str]] = mapped_column(String(20))
    calories_burned: Mapped[Optional[int]] = mapped_column(Integer)
    mood: Mapped[Optional[int]] = mapped_column(Integer)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="checkins")  # type: ignore[name-defined]
    exercises: Mapped[List["CheckinExercise"]] = relationship(
        back_populates="checkin", cascade="all, delete-orphan", lazy="selectin"
    )


class CheckinExercise(Base):
    __tablename__ = "checkin_exercises"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    checkin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("checkins.id", ondelete="CASCADE"),
        index=True,
    )
    # 自定义动作无 exercise_id，允许为空（与 custom_name 二选一）
    exercise_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("exercises.id"), index=True, nullable=True
    )
    # 关联的计划动作；计划动作被删时保留打卡历史（SET NULL）
    plan_day_exercise_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan_day_exercises.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    custom_name: Mapped[Optional[str]] = mapped_column(String(200))
    sets_done: Mapped[Optional[int]] = mapped_column(Integer)
    reps_done: Mapped[Optional[int]] = mapped_column(Integer)
    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    duration_min: Mapped[Optional[int]] = mapped_column(Integer)  # 有氧实际时长（分钟）
    distance_km: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))  # 有氧实际距离
    rpe: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    checkin: Mapped["Checkin"] = relationship(back_populates="exercises")
    exercise: Mapped["Exercise"] = relationship(lazy="selectin")  # type: ignore[name-defined]