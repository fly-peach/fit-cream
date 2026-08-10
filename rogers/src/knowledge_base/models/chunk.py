"""
文本分块 ORM 模型（kb_chunks 表）

tsvector 生成列 + GIN 索引；语义向量列（pgvector）。
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector

from app.config import settings
from app.database import Base


class KBChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("wiki_documents.id", ondelete="CASCADE"),
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_content: Mapped[Optional[str]] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    start_char: Mapped[Optional[int]] = mapped_column(Integer)
    header_breadcrumb: Mapped[Optional[str]] = mapped_column(String(500))
    # 生成列：content 写入/更新时自动重算（等价于 LLM Wiki 的 FTS5 触发器）
    search_vector = mapped_column(
        TSVECTOR(),
        Computed("to_tsvector('simple', content)", persisted=True),
    )
    # 语义向量列（text-embedding-v3，供向量路检索）。deferred：常规查询不加载。
    # 存量由 scripts/backfill_kb_chunk_embeddings.py 回填；新块由 indexer 摄入时打点。
    # pgvector 扩展不可用时 init_db 不会创建该列，语义检索降级为纯全文（不报错）。
    embedding = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION), nullable=True, deferred=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 关系
    document: Mapped["KBDocument"] = relationship(back_populates="chunks")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index(
            "idx_kb_chunks_search", "search_vector", postgresql_using="gin"
        ),
        CheckConstraint(
            "length(content) <= 10000", name="kb_chunk_content_length"
        ),
    )