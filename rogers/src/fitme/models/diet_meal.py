
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DietMeal(Base):
    __tablename__ = "diet_meals"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    custom_food_item_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("custom_food_items.id"), nullable=True, index=True)
    meal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    food_name: Mapped[str] = mapped_column(String(200), nullable=False)
    portion: Mapped[Optional[str]] = mapped_column(String(100))
    calories: Mapped[int] = mapped_column(Integer, default=0)
    protein_g: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))
    carbs_g: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))
    fat_g: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="diet_meals")
    custom_food_item: Mapped[Optional["CustomFoodItem"]] = relationship(back_populates="diet_meals")


class DailyDietSummary(Base):
    __tablename__ = "daily_diet_summaries"
    __table_args__ = (
        UniqueConstraint("user_id", "summary_date", name="uq_daily_diet_summary_user_date"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_calories: Mapped[int] = mapped_column(Integer, default=0)
    total_protein_g: Mapped[float] = mapped_column(Numeric(6, 1), default=0.0)
    total_carbs_g: Mapped[float] = mapped_column(Numeric(6, 1), default=0.0)
    total_fat_g: Mapped[float] = mapped_column(Numeric(6, 1), default=0.0)
    protein_goal_met: Mapped[bool] = mapped_column(default=False)
    carbs_goal_met: Mapped[bool] = mapped_column(default=False)
    fat_goal_met: Mapped[bool] = mapped_column(default=False)
    meal_count: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="daily_diet_summaries")


class CustomFoodItem(Base):
    __tablename__ = "custom_food_items"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    portion: Mapped[str] = mapped_column(String(100))
    calories_per_portion: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_g_per_portion: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))
    carbs_g_per_portion: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))
    fat_g_per_portion: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="custom_food_items")
    diet_meals: Mapped[List["DietMeal"]] = relationship(back_populates="custom_food_item", cascade="all, delete-orphan")
