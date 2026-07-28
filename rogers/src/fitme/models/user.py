
"""
用户模型

存储用户账号信息。
身体数据和设置已迁移到 HealthMetric 和 UserSettings。
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100))

    age: Mapped[Optional[int]] = mapped_column(Integer)
    gender: Mapped[Optional[str]] = mapped_column(String(10))

    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    plans: Mapped[List["Plan"]] = relationship(back_populates="user", lazy="selectin")
    diet_plans: Mapped[List["DietPlan"]] = relationship(back_populates="user", lazy="selectin")
    checkins: Mapped[List["Checkin"]] = relationship(back_populates="user", lazy="selectin")
    knowledge_bases: Mapped[List["KnowledgeBase"]] = relationship(back_populates="owner")
    settings: Mapped["UserSettings"] = relationship(back_populates="user", uselist=False, lazy="selectin")
    health_metrics: Mapped[List["HealthMetric"]] = relationship(back_populates="user", lazy="selectin")
    diet_meals: Mapped[List["DietMeal"]] = relationship(back_populates="user", lazy="selectin")
    daily_diet_summaries: Mapped[List["DailyDietSummary"]] = relationship(back_populates="user", lazy="selectin")
    custom_food_items: Mapped[List["CustomFoodItem"]] = relationship(back_populates="user", lazy="selectin")
