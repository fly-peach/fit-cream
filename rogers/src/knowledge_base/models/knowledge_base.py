"""
知识库主体 ORM 模型（knowledge_bases 表）

所有登录用户可读，admin 可写。
"""
from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    schema_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    owner: Mapped["User"] = relationship(back_populates="knowledge_bases")  # type: ignore[name-defined]  # noqa: F821
    documents: Mapped[List["KBDocument"]] = relationship(  # noqa: F821
        back_populates="kb", cascade="all, delete-orphan"
    )