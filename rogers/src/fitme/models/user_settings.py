"""
用户设置模型

存储用户的个性化设置（健身目标等），与用户一对一关系。
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
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

    # 通知设置
    notification_enabled: Mapped[bool] = mapped_column(default=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="settings")  # type: ignore[name-defined]
