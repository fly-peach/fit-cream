"""
知识图谱边 ORM 模型（kb_references 表）

cites / links_to，边冗余 kb_id。
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KBReference(Base):
    __tablename__ = "kb_references"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    source_document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("wiki_documents.id", ondelete="CASCADE"),
        index=True,
    )
    target_document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("wiki_documents.id", ondelete="CASCADE"),
        index=True,
    )
    kb_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    reference_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # cites / links_to
    page: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "source_document_id", "target_document_id", "reference_type"
        ),
        Index("idx_kb_refs_kb", "kb_id"),
    )