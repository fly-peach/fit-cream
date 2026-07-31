"""
训练计划模型

三层结构：
- Plan: 计划主体（目标、难度、周期、状态）
- PlanDay: 训练日（星期几、训练重点、组间休息）
- PlanDayExercise: 训练日中的具体动作（组数、次数、重量、排序、执行要点）
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # lose_fat / gain_muscle / maintain / improve_health
    difficulty: Mapped[Optional[str]] = mapped_column(
        String(20)
    )  # beginner / intermediate / advanced
    weeks: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )  # active / archived / completed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="plans")  # type: ignore[name-defined]
    days: Mapped[List["PlanDay"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )


class PlanDay(Base):
    __tablename__ = "plan_days"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(Integer)  # 1=周一 ... 7=周日
    focus: Mapped[Optional[str]] = mapped_column(String(100))  # 训练重点
    rest_seconds: Mapped[int] = mapped_column(Integer, default=60)
    metadata_: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)  # 自定义扩展数据

    # 关系
    plan: Mapped["Plan"] = relationship(back_populates="days")
    exercises: Mapped[List["PlanDayExercise"]] = relationship(
        back_populates="plan_day", cascade="all, delete-orphan", lazy="selectin"
    )


class PlanDayExercise(Base):
    __tablename__ = "plan_day_exercises"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    plan_day_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plan_days.id", ondelete="CASCADE"),
        index=True,
    )
    exercise_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("exercises.id"), index=True, nullable=True
    )
    custom_name: Mapped[Optional[str]] = mapped_column(String(200))
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)  # 动作执行要点 / 备注
    metadata_: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)  # 自定义扩展数据

    # 关系
    plan_day: Mapped["PlanDay"] = relationship(back_populates="exercises")
    exercise: Mapped["Exercise"] = relationship(lazy="selectin")  # type: ignore[name-defined]