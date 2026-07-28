"""
饮食计划模型

三层结构：
- DietPlan: 饮食计划主体（目标卡路里、状态）
- DietPlanDay: 饮食计划日（星期几、重点）
- DietPlanMeal: 具体餐食（餐次类型、食物名称、热量、宏量素）
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DietPlan(Base):
    __tablename__ = "diet_plans"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_calories: Mapped[Optional[int]] = mapped_column(Integer)  # 每日目标卡路里
    goal: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # lose_fat / gain_muscle / maintain / improve_health
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )  # active / archived
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="diet_plans")  # type: ignore[name-defined]
    days: Mapped[List["DietPlanDay"]] = relationship(
        back_populates="diet_plan", cascade="all, delete-orphan", lazy="selectin"
    )


class DietPlanDay(Base):
    __tablename__ = "diet_plan_days"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    diet_plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("diet_plans.id", ondelete="CASCADE"),
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(Integer)  # 1=周一 ... 7=周日
    focus: Mapped[Optional[str]] = mapped_column(String(100))  # 当日饮食重点
    metadata_: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)  # 自定义扩展数据

    # 关系
    diet_plan: Mapped["DietPlan"] = relationship(back_populates="days")
    meals: Mapped[List["DietPlanMeal"]] = relationship(
        back_populates="diet_plan_day", cascade="all, delete-orphan", lazy="selectin"
    )


class DietPlanMeal(Base):
    __tablename__ = "diet_plan_meals"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    diet_plan_day_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("diet_plan_days.id", ondelete="CASCADE"),
        index=True,
    )
    meal_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # breakfast / lunch / dinner / snack
    food_name: Mapped[str] = mapped_column(String(200), nullable=False)
    calories: Mapped[Optional[int]] = mapped_column(Integer)  # 千卡
    protein_g: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))  # 蛋白质(克)
    carbs_g: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))  # 碳水(克)
    fat_g: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))  # 脂肪(克)
    portion: Mapped[Optional[str]] = mapped_column(String(100))  # 份量描述
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)  # 自定义扩展数据

    # 关系
    diet_plan_day: Mapped["DietPlanDay"] = relationship(back_populates="meals")