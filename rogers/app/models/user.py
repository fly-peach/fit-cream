"""
用户模型

存储用户账号信息、身体数据和健身目标。
身体数据（身高/体重/年龄/性别）用于 Agent 生成个性化训练计划。
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    phone: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100))

    # 身体数据
    height_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    gender: Mapped[Optional[str]] = mapped_column(String(10))  # male/female/other

    # 健身目标: lose_fat / gain_muscle / maintain / improve_health
    goal: Mapped[Optional[str]] = mapped_column(String(50))

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    plans: Mapped[List["Plan"]] = relationship(back_populates="user", lazy="selectin")  # type: ignore[name-defined]
    checkins: Mapped[List["Checkin"]] = relationship(back_populates="user", lazy="selectin")  # type: ignore[name-defined]
    achievements: Mapped[List["Achievement"]] = relationship(back_populates="user")  # type: ignore[name-defined]
