"""
索引 Pydantic Schemas（观测 + 重建结果）
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KBIndexStatus(BaseModel):
    """索引状态（FR-3 可观测性）"""
    kb_id: UUID
    total_documents: int
    indexed_documents: int
    pending_documents: int
    chunks_total: int = 0
    chunks_embedded: int = 0
    chunks_pending_embedding: int = 0
    last_indexed_at: Optional[str] = None
    last_chunk_indexed_at: Optional[str] = None


class KBReindexResult(BaseModel):
    kb_id: UUID
    documents_processed: int
    chunks_created: int
    references: dict = Field(default_factory=dict)