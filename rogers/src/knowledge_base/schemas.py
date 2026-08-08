"""
知识库 Pydantic Schemas

定义知识库 CRUD 的请求/响应模型，遵循现有 fitme/schemas/plan.py 的模式。
输出模型使用 model_config = {"from_attributes": True} 从 ORM 实例转换。
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field


# ============================================================
# 知识库
# ============================================================


class KBCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    schema_config: dict = Field(default_factory=dict)


class KBUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    schema_config: Optional[dict] = None


class KBVisibilityUpdate(BaseModel):
    """设置知识库可见性（private/shared/public）"""
    visibility: str = Field(pattern="^(private|shared|public)$")
    public_slug: Optional[str] = Field(default=None, max_length=80)


class KBOut(BaseModel):
    id: UUID
    name: str
    description: str
    slug: str
    owner_id: UUID
    visibility: str
    public_slug: Optional[str] = None
    share_token: Optional[str] = None
    schema_config: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBListOut(BaseModel):
    """知识库列表摘要（不含 schema_config），含当前用户订阅态"""
    id: UUID
    name: str
    description: str
    slug: str
    owner_id: UUID
    visibility: str
    subscribed: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 文档
# ============================================================


class KBDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    filename: str = Field(min_length=1, max_length=255)
    path: str = Field(default="/", max_length=500)
    source_kind: str = Field(default="wiki", pattern="^(raw|wiki)$")
    file_type: str = Field(default="md")
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
    source_kind: str
    file_type: str
    content_hash: Optional[str] = None
    status: str
    document_number: Optional[int] = None
    sort_order: int = 0
    archived: bool = False
    page_count: Optional[int] = None
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
    source_kind: str
    file_type: str
    content_hash: Optional[str] = None
    status: str
    document_number: Optional[int] = None
    sort_order: int = 0
    archived: bool = False
    page_count: Optional[int] = None
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


# ============================================================
# 搜索
# ============================================================


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


# ============================================================
# 知识图谱
# ============================================================


class KBGraphNode(BaseModel):
    id: str
    title: str
    path: str
    file_type: str
    source_kind: str
    tags: List[str] = Field(default_factory=list)
    stale_since: Optional[str] = None
    uncited: bool = False
    degree: int = 0
    semantic_group: str = "其他"


class KBGraphEdge(BaseModel):
    source: str
    target: str
    type: str  # cites / links_to
    page: Optional[int] = None


class KBGraphData(BaseModel):
    nodes: List[KBGraphNode]
    edges: List[KBGraphEdge]
    stats: dict = Field(default_factory=dict)


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


class KBDocumentReferences(BaseModel):
    """文档的出边 + 入边"""
    document_id: UUID
    cites: List[dict] = Field(default_factory=list)
    links_to: List[dict] = Field(default_factory=list)
    cited_by: List[dict] = Field(default_factory=list)
    linked_by: List[dict] = Field(default_factory=list)


# ============================================================
# 订阅管理
# ============================================================


class KBSubscriptionOut(BaseModel):
    """订阅记录输出（管理员查看某 KB 的订阅者）"""
    id: UUID
    kb_id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    subscribed_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# API 令牌
# ============================================================


class KBTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scope: str = Field(default="read", pattern="^(read|write)$")
    expires_at: Optional[datetime] = None


class KBTokenOut(BaseModel):
    """令牌输出（脱敏，不含 token_hash）"""
    id: UUID
    kb_id: UUID
    token_prefix: str
    name: str
    scope: str
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KBTokenCreated(BaseModel):
    """令牌创建响应（含明文 token，仅此一次）"""
    token: str
    token_out: KBTokenOut


# ============================================================
# Lint
# ============================================================


class KBLintIssue(BaseModel):
    severity: str  # error / warn
    code: str
    path: str
    message: str


class KBLintReport(BaseModel):
    kb_id: UUID
    total: int
    errors: int
    warnings: int
    issues: List[KBLintIssue]


# ============================================================
# 重建索引结果
# ============================================================


class KBReindexResult(BaseModel):
    kb_id: UUID
    documents_processed: int
    chunks_created: int
    references: dict = Field(default_factory=dict)
