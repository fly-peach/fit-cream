"""
知识库路由 /api/knowledge-bases/*

两级权限模型：
- 系统管理员（admin）：全部写操作（创建/编辑/删除 KB、文档 CRUD、索引/图谱/lint、订阅者管理）
- 普通用户（登录）：可浏览全部 KB 目录并自助订阅；订阅某 KB 后（或 owner）可读其文档/搜索/图谱/引用/索引状态
- 无公开/匿名读路径

所有端点带 operation_id（供 fastapi-mcp 复用为 MCP tool）。
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel
from src.knowledge_base.schemas.document import (
    KBDocumentContent,
    KBDocumentContentUpdate,
    KBDocumentCreate,
    KBDocumentListOut,
    KBDocumentMetadataUpdate,
    KBDocumentOut,
    KBDocumentReferences,
)
from src.knowledge_base.schemas.graph import KBGraphData
from src.knowledge_base.schemas.index import KBIndexStatus, KBReindexResult
from src.knowledge_base.schemas.knowledge_base import KBCreate, KBListOut, KBOut, KBUpdate
from src.knowledge_base.schemas.search import KBSearchResult
from src.knowledge_base.schemas.subscription import KBSubscriptionOut
from src.knowledge_base.services.document_service import KBDocumentService
from src.knowledge_base.services.graph_service import KBGraphService
from src.knowledge_base.services.knowledge_base_service import KnowledgeBaseService
from src.knowledge_base.services.search_service import KBSearchService

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


# ============================================================
# 知识库管理
# ============================================================


@router.post("", response_model=ResponseModel[KBOut], operation_id="create_knowledge_base")
async def create_knowledge_base(
    data: KBCreate,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """创建知识库（admin）"""
    kb = await KnowledgeBaseService.create_kb(
        db, user.id, data.name, data.description, data.schema_config
    )
    await db.commit()
    await db.refresh(kb)
    return ResponseModel(data=KBOut.model_validate(kb))


@router.get("", response_model=ResponseModel[list[KBListOut]], operation_id="list_knowledge_bases")
async def list_knowledge_bases(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出全部知识库（登录用户可读），每条附当前用户是否已订阅"""
    kbs = await KnowledgeBaseService.list_kbs(db)
    subscribed_ids = await KnowledgeBaseService.get_subscribed_kb_ids(db, user.id)
    data: list[KBListOut] = []
    for kb in kbs:
        out = KBListOut.model_validate(kb)
        out.subscribed = kb.id in subscribed_ids
        data.append(out)
    return ResponseModel(data=data)


@router.get("/subscriptions", response_model=ResponseModel[list[KBListOut]], operation_id="list_my_subscriptions")
async def list_my_subscriptions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户已订阅的知识库"""
    kbs = await KnowledgeBaseService.list_my_subscriptions(db, user.id)
    data: list[KBListOut] = []
    for kb in kbs:
        out = KBListOut.model_validate(kb)
        out.subscribed = True
        data.append(out)
    return ResponseModel(data=data)


@router.get("/{kb_id}", response_model=ResponseModel[KBOut], operation_id="get_knowledge_base")
async def get_knowledge_base(
    kb_id: UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库详情（登录用户可读）"""
    kb = await KnowledgeBaseService.get_kb(db, kb_id)
    return ResponseModel(data=KBOut.model_validate(kb))


@router.put("/{kb_id}", response_model=ResponseModel[KBOut], operation_id="update_knowledge_base")
async def update_knowledge_base(
    kb_id: UUID,
    data: KBUpdate,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新知识库（admin）"""
    kb = await KnowledgeBaseService.update_kb(
        db, kb_id, data.name, data.description, data.schema_config
    )
    await db.commit()
    await db.refresh(kb)
    return ResponseModel(data=KBOut.model_validate(kb))


@router.delete("/{kb_id}", response_model=ResponseModel[None], operation_id="delete_knowledge_base")
async def delete_knowledge_base(
    kb_id: UUID,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除知识库（admin）"""
    await KnowledgeBaseService.delete_kb(db, kb_id)
    await db.commit()
    return ResponseModel(message="知识库已删除")


# ============================================================
# 订阅管理（用户自助 + admin 查看/移除）
# ============================================================


@router.post("/{kb_id}/subscribe", response_model=ResponseModel[KBSubscriptionOut], operation_id="subscribe_kb")
async def subscribe_kb(
    kb_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自助订阅知识库（幂等）"""
    sub = await KnowledgeBaseService.subscribe(db, kb_id, user.id)
    await db.commit()
    await db.refresh(sub)
    return ResponseModel(data=KBSubscriptionOut(
        id=sub.id, kb_id=sub.kb_id, user_id=sub.user_id,
        user_name=user.name, user_phone=user.phone,
        subscribed_at=sub.subscribed_at,
    ))


@router.delete("/{kb_id}/subscribe", response_model=ResponseModel[None], operation_id="unsubscribe_kb")
async def unsubscribe_kb(
    kb_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消订阅（幂等）"""
    await KnowledgeBaseService.unsubscribe(db, kb_id, user.id)
    await db.commit()
    return ResponseModel(message="已取消订阅")


@router.get("/{kb_id}/subscribers", response_model=ResponseModel[list[KBSubscriptionOut]], operation_id="list_subscribers")
async def list_subscribers(
    kb_id: UUID,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """列出某 KB 的全部订阅者（admin）"""
    subs = await KnowledgeBaseService.list_subscribers(db, kb_id)
    data = [
        KBSubscriptionOut(
            id=s.id, kb_id=s.kb_id, user_id=s.user_id,
            user_name=s.user.name if s.user else None,
            user_phone=s.user.phone if s.user else None,
            subscribed_at=s.subscribed_at,
        )
        for s in subs
    ]
    return ResponseModel(data=data)


@router.delete("/{kb_id}/subscribers/{user_id}", response_model=ResponseModel[None], operation_id="remove_subscriber")
async def remove_subscriber(
    kb_id: UUID,
    user_id: UUID,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """移除订阅者（admin，幂等）"""
    await KnowledgeBaseService.remove_subscriber(db, kb_id, user_id)
    await db.commit()
    return ResponseModel(message="订阅者已移除")


# ============================================================
# 文档 CRUD
# ============================================================


@router.post(
    "/{kb_id}/documents",
    response_model=ResponseModel[KBDocumentOut],
    operation_id="create_document",
)
async def create_document(
    kb_id: UUID,
    data: KBDocumentCreate,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """创建文档（自动分块索引）（admin）"""
    doc = await KBDocumentService.create_document(db, kb_id, data, user.id)
    await db.commit()
    await db.refresh(doc)
    return ResponseModel(data=KBDocumentOut.model_validate(doc))


@router.get(
    "/{kb_id}/documents",
    response_model=ResponseModel[list[KBDocumentListOut]],
    operation_id="list_documents",
)
async def list_documents(
    kb_id: UUID,
    entity_type: Optional[str] = None,
    include_archived: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出文档（owner 或已订阅者可读）"""
    await KnowledgeBaseService.ensure_kb_access(db, kb_id, user.id)
    docs = await KBDocumentService.list_documents(
        db, kb_id, entity_type, include_archived
    )
    return ResponseModel(data=[KBDocumentListOut.model_validate(d) for d in docs])


@router.get(
    "/{kb_id}/documents/{doc_id}",
    response_model=ResponseModel[KBDocumentOut],
    operation_id="get_document",
)
async def get_document(
    kb_id: UUID,
    doc_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取文档元数据（owner 或已订阅者可读）"""
    doc = await KBDocumentService.get_document_for_user(db, doc_id, user.id)
    return ResponseModel(data=KBDocumentOut.model_validate(doc))


@router.get(
    "/{kb_id}/documents/{doc_id}/content",
    response_model=ResponseModel[KBDocumentContent],
    operation_id="read_document",
)
async def read_document(
    kb_id: UUID,
    doc_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """读取文档完整内容（owner 或已订阅者可读）"""
    doc = await KBDocumentService.get_document_for_user(db, doc_id, user.id)
    return ResponseModel(data=KBDocumentContent.model_validate(doc))


@router.put(
    "/{kb_id}/documents/{doc_id}/content",
    response_model=ResponseModel[KBDocumentOut],
    operation_id="update_document_content",
)
async def update_document_content(
    kb_id: UUID,
    doc_id: UUID,
    data: KBDocumentContentUpdate,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新文档内容（乐观锁 + 自动重新分块 + 过期传播）（admin）"""
    doc = await KBDocumentService.update_document_content(db, doc_id, data, user.id)
    await db.commit()
    await db.refresh(doc)
    return ResponseModel(data=KBDocumentOut.model_validate(doc))


@router.patch(
    "/{kb_id}/documents/{doc_id}",
    response_model=ResponseModel[KBDocumentOut],
    operation_id="update_document_metadata",
)
async def update_document_metadata(
    kb_id: UUID,
    doc_id: UUID,
    data: KBDocumentMetadataUpdate,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新文档元数据（不触发重新分块）（admin）"""
    doc = await KBDocumentService.update_document_metadata(db, doc_id, data)
    await db.commit()
    await db.refresh(doc)
    return ResponseModel(data=KBDocumentOut.model_validate(doc))


@router.delete(
    "/{kb_id}/documents/{doc_id}",
    response_model=ResponseModel[None],
    operation_id="delete_document",
)
async def delete_document(
    kb_id: UUID,
    doc_id: UUID,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """删除文档（admin）"""
    await KBDocumentService.delete_document(db, doc_id)
    await db.commit()
    return ResponseModel(message="文档已删除")


# ============================================================
# 搜索 + 图谱
# ============================================================


@router.get(
    "/{kb_id}/search",
    response_model=ResponseModel[list[KBSearchResult]],
    operation_id="search_documents",
)
async def search_documents(
    kb_id: UUID,
    query: str = Query(min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """全文搜索（owner 或已订阅者可读）"""
    await KnowledgeBaseService.ensure_kb_access(db, kb_id, user.id)
    results = await KBSearchService.search_documents(db, kb_id, query, limit)
    return ResponseModel(data=[KBSearchResult(**r) for r in results])


@router.get(
    "/{kb_id}/graph",
    response_model=ResponseModel[KBGraphData],
    operation_id="get_graph",
)
async def get_graph(
    kb_id: UUID,
    mode: str = Query("full", pattern="^(full|overview)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """知识图谱数据（owner 或已订阅者可读）；mode=overview 时大数据降采样"""
    await KnowledgeBaseService.ensure_kb_access(db, kb_id, user.id)
    graph = await KBGraphService.get_graph(db, kb_id, mode=mode)
    return ResponseModel(data=KBGraphData(**graph))


@router.get(
    "/{kb_id}/index-status",
    response_model=ResponseModel[KBIndexStatus],
    operation_id="get_index_status",
)
async def get_index_status(
    kb_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """索引状态（文档/分块/向量回填进度）（owner 或已订阅者可读）"""
    await KnowledgeBaseService.ensure_kb_access(db, kb_id, user.id)
    status = await KBGraphService.get_index_status(db, kb_id)
    return ResponseModel(data=KBIndexStatus(**status))


@router.get(
    "/{kb_id}/documents/{doc_id}/references",
    response_model=ResponseModel[KBDocumentReferences],
    operation_id="get_document_references",
)
async def get_document_references(
    kb_id: UUID,
    doc_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """文档引用关系（出边 + 入边）（owner 或已订阅者可读）"""
    await KnowledgeBaseService.ensure_kb_access(db, kb_id, user.id)
    refs = await KBGraphService.get_document_references(db, doc_id)
    return ResponseModel(data=KBDocumentReferences(**refs))


@router.post(
    "/{kb_id}/reindex",
    response_model=ResponseModel[KBReindexResult],
    operation_id="reindex_knowledge_base",
)
async def reindex_knowledge_base(
    kb_id: UUID,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """重建索引（admin）"""
    result = await KBGraphService.reindex_knowledge_base(db, kb_id)
    return ResponseModel(data=KBReindexResult(kb_id=kb_id, **result))


@router.post(
    "/{kb_id}/rebuild-graph",
    response_model=ResponseModel[dict],
    operation_id="rebuild_graph",
)
async def rebuild_graph(
    kb_id: UUID,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """重建知识图谱（admin）"""
    result = await KBGraphService.rebuild_graph(db, kb_id)
    await db.commit()
    return ResponseModel(data=result)


@router.get(
    "/{kb_id}/lint",
    response_model=ResponseModel[dict],
    operation_id="lint_knowledge_base",
)
async def lint_knowledge_base(
    kb_id: UUID,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """知识库健康检查（admin）"""
    report = await KBGraphService.run_lint(db, kb_id)
    return ResponseModel(data=report)


@router.post(
    "/{kb_id}/rebuild-lint",
    response_model=ResponseModel[dict],
    operation_id="rebuild_lint",
)
async def rebuild_lint(
    kb_id: UUID,
    _user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """重建并检查（admin）：重建搜索索引 + 重建引用图 + 运行 lint，返回索引状态与 lint 报告"""
    result = await KBGraphService.rebuild_lint(db, kb_id)
    await db.commit()
    return ResponseModel(data=result)

