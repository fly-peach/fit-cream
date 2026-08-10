"""
文档 ORM 模型（wiki_documents 表）

仅 wiki Markdown 文档，path 位于 /wiki/*。
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KBDocument(Base):
    __tablename__ = "wiki_documents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    kb_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(500), default="/")
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA256
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending/processing/ready/failed/archived
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    document_number: Mapped[Optional[int]] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    stale_since: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    kb: Mapped["KnowledgeBase"] = relationship(back_populates="documents")  # noqa: F821
    chunks: Mapped[List["KBChunk"]] = relationship(  # noqa: F821
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_kb_doc_kb_archived", "kb_id", "archived"),)