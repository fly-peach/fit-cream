"""
用户目标模型

存储用户健身目标与营养目标（与 user_settings 基础信息表拆分）。
每用户一条，与 User 一对一。
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from utils.uuid7 import uuid7


class UserGoals(Base):
    __tablename__ = "user_goals"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True
    )

    # 健身目标
    goal: Mapped[str | None] = mapped_column(String(50))

    # 目标身体数据
    target_weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    target_body_fat_pct: Mapped[float | None] = mapped_column(Numeric(4, 2))

    # 训练目标
    weekly_training_goal: Mapped[int] = mapped_column(Integer, default=5)

    # 营养目标
    calorie_goal: Mapped[int] = mapped_column(Integer, default=2000)
    protein_goal_g: Mapped[int] = mapped_column(Integer, default=150)
    carbs_goal_g: Mapped[int] = mapped_column(Integer, default=250)
    fat_goal_g: Mapped[int] = mapped_column(Integer, default=65)

    # 通知设置（偏好）
    notification_enabled: Mapped[bool] = mapped_column(default=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="goals")  # type: ignore[name-defined]