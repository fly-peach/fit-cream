"""
知识库 ORM 模型

6 张表（参考 LLM Wiki supabase/migrations 设计）：
- knowledge_bases:    知识库主体（含三档可见性 + 预生成 share_token）
- kb_documents:       文档（raw/wiki 统一，path 区分 /wiki/* 与 /）
- kb_chunks:          文本分块（tsvector 生成列 + GIN 索引）
- kb_references:      知识图谱边（cites / links_to，边冗余 kb_id）
- kb_subscriptions:   用户-知识库订阅关联（用户可订阅多个 KB；两级权限：系统 admin 全权 / 普通用户只读+订阅）
- kb_api_tokens:       外部 MCP 访问令牌（token_prefix 脱敏展示 + revoked_at 软撤销）
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pgvector.sqlalchemy import Vector

from app.config import settings
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
    visibility: Mapped[str] = mapped_column(
        String(20), default="private"
    )  # private/shared/public
    share_token: Mapped[str] = mapped_column(
        String(64), unique=True
    )  # 预生成（去横线 UUID），shared 档「链接即权限」
    public_slug: Mapped[Optional[str]] = mapped_column(
        String(80)
    )  # 仅 public 档设置，全局唯一（部分索引）
    schema_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    owner: Mapped["User"] = relationship(back_populates="knowledge_bases")  # type: ignore[name-defined]
    documents: Mapped[List["KBDocument"]] = relationship(
        back_populates="kb", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[List["KBSubscription"]] = relationship(
        back_populates="kb", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # public 必须有 public_slug（参考 006_kb_sharing）
        CheckConstraint(
            "visibility <> 'public' OR public_slug IS NOT NULL",
            name="kb_public_requires_slug",
        ),
        # public_slug 全局唯一（部分唯一索引）
        Index(
            "idx_kb_public_slug",
            "public_slug",
            unique=True,
            postgresql_where=text("public_slug IS NOT NULL"),
        ),
    )


class KBDocument(Base):
    __tablename__ = "kb_documents"

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
    source_kind: Mapped[str] = mapped_column(String(20), default="wiki")  # raw/wiki
    file_type: Mapped[str] = mapped_column(String(20), default="md")
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA256
    status: Mapped[str] = mapped_column(
        String(20), default="ready"
    )  # pending/processing/ready/failed/archived
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    document_number: Mapped[Optional[int]] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    parser: Mapped[Optional[str]] = mapped_column(String(50))
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
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
    kb: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    chunks: Mapped[List["KBChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "page_count IS NULL OR page_count <= 300", name="kb_doc_page_count_limit"
        ),
        Index("idx_kb_doc_kb_archived", "kb_id", "archived"),
    )


class KBChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
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
    document: Mapped["KBDocument"] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index(
            "idx_kb_chunks_search", "search_vector", postgresql_using="gin"
        ),
        CheckConstraint(
            "length(content) <= 10000", name="kb_chunk_content_length"
        ),
    )


class KBReference(Base):
    __tablename__ = "kb_references"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    source_document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
        index=True,
    )
    target_document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
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


class KBSubscription(Base):
    __tablename__ = "kb_subscriptions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    kb_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 关系
    kb: Mapped["KnowledgeBase"] = relationship(back_populates="subscriptions")
    user: Mapped["User"] = relationship()  # type: ignore[name-defined]

    __table_args__ = (UniqueConstraint("kb_id", "user_id"),)


class KBApiToken(Base):
    __tablename__ = "kb_api_tokens"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    kb_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    token_prefix: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(100))
    scope: Mapped[str] = mapped_column(String(20), default="read")  # read/write
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id")
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_kb_tokens_kb", "kb_id"),)
