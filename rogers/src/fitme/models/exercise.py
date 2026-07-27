"""
动作库模型

存储健身动作的基础数据（名称、肌群、器械、难度、描述），
供训练计划编排和 Agent 动作推荐查询使用。
"""
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    name_en: Mapped[Optional[str]] = mapped_column(String(200))
    muscle_group: Mapped[Optional[str]] = mapped_column(
        String(50), index=True
    )  # chest / back / legs / shoulders / arms / core / full_body
    equipment: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # barbell / dumbbell / machine / bodyweight / cable / kettlebell
    difficulty: Mapped[Optional[str]] = mapped_column(
        String(20)
    )  # beginner / intermediate / advanced
    description: Mapped[Optional[str]] = mapped_column(Text)