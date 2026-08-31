"""
目标闯关系统模型

两层结构：
- 知识层（种子数据，由 goal_knowledge_seed 幂等灌入）：
  - GoalArchetype: 身材原型库（薄肌/倒三角/力量型/大维度/匀称/紧致线条）
  - StrengthStandard: 力量标准表（按性别×动作×档位的体重倍数）
  - ProgressRate: 进度速率表（按经验层级×指标的月度变化区间）
  - GoalSafetyLimit: 安全限值表（体脂下限/月度体重变化上限等）
- 业务层：
  - GoalRoadmap: 闯关路线图主体
  - GoalMilestone: 路线图中的关卡（出口条件/预期周数/状态）
  - PerformanceTest: 力量/围度基线或复测记录
"""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from utils.uuid7 import uuid7


# ===== 知识层（种子表） =====


class GoalArchetype(Base):
    """身材原型库（v2）：一行 = 一个 (key, gender) 组合，指标/叙事扁平化。"""

    __tablename__ = "goal_archetypes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)  # male / female
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    tagline: Mapped[Optional[str]] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    image: Mapped[Optional[str]] = mapped_column(String(300))  # /static/goals/<key>_<gender>.webp
    target_metrics: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )  # [{metric,min,max,core}]；core=true 参与末关比对
    target_exercise_goal: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )  # [{metric,display}] 达成兜底指标（人群参考，非承诺）
    target_exercises: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )  # [{group,exercises[]}]，末组固定「拉伸」
    training_bias: Mapped[Optional[str]] = mapped_column(String(50))
    diet_bias: Mapped[Optional[str]] = mapped_column(String(50))
    stage_hint: Mapped[Optional[str]] = mapped_column(String(50))
    stage_narrative_hint: Mapped[Optional[str]] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("key", "gender", name="uq_goal_archetypes_key_gender"),
    )


class StrengthStandard(Base):
    __tablename__ = "strength_standards"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    lift: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    bw_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint("gender", "lift", "level", name="uq_strength_standards"),
    )


class ProgressRate(Base):
    __tablename__ = "progress_rates"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    experience_level: Mapped[str] = mapped_column(String(20), nullable=False)
    metric: Mapped[str] = mapped_column(String(30), nullable=False)
    monthly_min: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    monthly_max: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint(
            "experience_level", "metric", name="uq_progress_rates"
        ),
    )


class GoalSafetyLimit(Base):
    __tablename__ = "goal_safety_limits"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    metric: Mapped[str] = mapped_column(String(30), nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    floor_value: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    ceiling_value: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    note: Mapped[Optional[str]] = mapped_column(String(200))

    __table_args__ = (
        UniqueConstraint("metric", "gender", name="uq_goal_safety_limits"),
    )


# ===== 业务层 =====


class GoalRoadmap(Base):
    __tablename__ = "goal_roadmaps"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    archetype_key: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    target_metrics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    horizon_months: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    milestones: Mapped[List["GoalMilestone"]] = relationship(
        back_populates="roadmap",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="GoalMilestone.stage_index",
    )


class GoalMilestone(Base):
    __tablename__ = "goal_milestones"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    roadmap_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("goal_roadmaps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    exit_criteria: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    expected_weeks: Mapped[Optional[int]] = mapped_column(Integer)
    training_focus: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="locked")
    achieved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    roadmap: Mapped["GoalRoadmap"] = relationship(back_populates="milestones")


class PerformanceTest(Base):
    __tablename__ = "performance_tests"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    lift: Mapped[str] = mapped_column(String(20), nullable=False)
    test_type: Mapped[str] = mapped_column(String(20), nullable=False, default="1rm")
    value: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    bodyweight_kg: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    tested_at: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="chat")
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_performance_tests_user", "user_id", "lift", "tested_at"),
    )
