"""
成就模型

记录用户解锁的成就徽章（连续打卡 7/30/100 天、首次创建计划、累计训练 50/100 次等）。
同一用户同一类型成就只能解锁一次（唯一约束）。
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "type", name="uq_achievement_user_type"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(50)
    )  # streak_7 / streak_30 / streak_100 / first_plan / total_50_workouts / total_100_workouts
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="achievements")  # type: ignore[name-defined]