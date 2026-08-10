"""
搜索 Pydantic Schema（KBSearchResult）
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class KBSearchResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    filename: str
    path: str
    chunk_index: int
    content: str
    header_breadcrumb: Optional[str] = None
    token_count: int = 0
    rank: float = 0.0