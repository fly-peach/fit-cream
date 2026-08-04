"""
记忆相关 Schemas

定义语义记忆的输出模型，供 /api/memory/* 路由使用。

注意：SemanticMemory ORM 属于独立 MemoryBase（非 app Base），
使用 Column（legacy 风格）声明，但 Pydantic v2 的 from_attributes 仍可正常读取。
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SemanticMemoryOut(BaseModel):
    """语义记忆输出（三元组 + 元数据）"""

    id: UUID
    subject: str
    predicate: str
    object: str
    category: str
    confidence: float
    version: int
    updated_at: datetime
    source_episodic_id: Optional[UUID] = None

    model_config = {"from_attributes": True}
