"""
知识库主体 Pydantic Schemas

CRUD 请求/响应模型。
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KBCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    schema_config: dict = Field(default_factory=dict)


class KBUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    schema_config: Optional[dict] = None


class KBOut(BaseModel):
    id: UUID
    name: str
    description: str
    slug: str
    owner_id: UUID
    schema_config: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBListOut(BaseModel):
    """知识库列表摘要（不含 schema_config）"""
    id: UUID
    name: str
    description: str
    slug: str
    owner_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}