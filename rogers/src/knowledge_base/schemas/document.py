"""
文档 Pydantic Schemas

文档 CRUD 请求/响应模型 + 引用关系。
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field


class KBDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    filename: str = Field(min_length=1, max_length=255)
    path: str = Field(default="/", max_length=500)
    content: str = ""
    tags: List[str] = Field(default_factory=list)
    entity_type: Optional[str] = Field(default=None, max_length=50)
    metadata_: dict = Field(default_factory=dict, alias="metadata")


class KBDocumentContentUpdate(BaseModel):
    """更新文档内容（触发重新分块索引）"""
    content: str = ""
    tags: Optional[List[str]] = None
    title: Optional[str] = None
    version: int = Field(description="乐观锁：当前版本号，必须匹配")


class KBDocumentMetadataUpdate(BaseModel):
    """更新文档元数据（不触发重新分块）"""
    title: Optional[str] = Field(default=None, max_length=500)
    tags: Optional[List[str]] = None
    entity_type: Optional[str] = Field(default=None, max_length=50)
    metadata_: Optional[dict] = Field(default=None, alias="metadata")
    sort_order: Optional[int] = None


class KBDocumentOut(BaseModel):
    id: UUID
    kb_id: UUID
    title: str
    filename: str
    path: str
    content_hash: Optional[str] = None
    status: str
    document_number: Optional[int] = None
    sort_order: int = 0
    archived: bool = False
    last_indexed_at: Optional[datetime] = None
    stale_since: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    entity_type: Optional[str] = None
    # ORM 属性名为 metadata_（列名 metadata），而 "metadata" 会撞到 SQLAlchemy 的
    # Base.metadata；from_attributes 校验时优先读 metadata_，序列化仍输出 "metadata"
    metadata_: dict = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata_", "metadata"),
        serialization_alias="metadata",
    )
    version: int = 0
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBDocumentListOut(BaseModel):
    """文档列表摘要（不含 content）"""
    id: UUID
    kb_id: UUID
    title: str
    filename: str
    path: str
    content_hash: Optional[str] = None
    status: str
    document_number: Optional[int] = None
    sort_order: int = 0
    archived: bool = False
    stale_since: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    entity_type: Optional[str] = None
    version: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBDocumentContent(BaseModel):
    """文档完整内容"""
    id: UUID
    title: str
    filename: str
    path: str
    content: str
    content_hash: Optional[str] = None
    version: int = 0
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBDocumentReferences(BaseModel):
    """文档的出边 + 入边"""
    document_id: UUID
    cites: List[dict] = Field(default_factory=list)
    links_to: List[dict] = Field(default_factory=list)
    cited_by: List[dict] = Field(default_factory=list)
    linked_by: List[dict] = Field(default_factory=list)