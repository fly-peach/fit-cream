"""
健康指标历史记录模型

记录用户的身体数据变化历史（体重、体脂、BMI等）。
"""
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HealthMetric(Base):
    __tablename__ = "health_metrics"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    measure_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # 身体数据
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    body_fat_pct: Mapped[float | None] = mapped_column(Numeric(4, 2))
    muscle_mass_kg: Mapped[float | None] = mapped_column(Numeric(5, 2))
    bmi: Mapped[float | None] = mapped_column(Numeric(4, 2))
    bmi_status: Mapped[str | None] = mapped_column(String(20))

    # 身体围度（可选）
    chest_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    waist_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    hip_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    arm_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    thigh_cm: Mapped[float | None] = mapped_column(Numeric(5, 2))

    note: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="health_metrics")  # type: ignore[name-defined]

    __table_args__ = (
        {"sqlite_autoincrement": True}
    )
