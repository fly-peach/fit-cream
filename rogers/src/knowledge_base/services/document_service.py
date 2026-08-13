"""
文档 Service（文档 CRUD）

创建/更新文档后自动分块索引（chunks/embedding），更新后对引用方传播过期标记；
引用图重建由 admin 的"重建并检查"统一执行。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge_base.graph import (
    propagate_staleness,
    reindex_document_references_for_kb,
)
from src.knowledge_base.indexer import compute_content_hash, index_document, reindex_document
from src.knowledge_base.models.document import KBDocument
from src.knowledge_base.schemas.document import (
    KBDocumentContentUpdate,
    KBDocumentCreate,
    KBDocumentMetadataUpdate,
)
from src.knowledge_base.services.knowledge_base_service import KnowledgeBaseService
from utils.exceptions import BadRequestException, NotFoundException

logger = logging.getLogger("fitcream")


class KBDocumentService:
    @staticmethod
    async def create_document(
        db: AsyncSession, kb_id: UUID, data: KBDocumentCreate, user_id: UUID
    ) -> KBDocument:
        """创建 wiki 文档并自动分块索引（索引失败置 status=failed，不阻断创建）"""
        await KnowledgeBaseService.get_kb(db, kb_id)

        # per-KB 递增序号
        max_num_result = await db.execute(
            select(func.max(KBDocument.document_number)).where(
                KBDocument.kb_id == kb_id
            )
        )
        next_num = (max_num_result.scalar() or 0) + 1

        doc = KBDocument(
            kb_id=kb_id,
            title=data.title,
            filename=data.filename,
            path=data.path,
            content=data.content,
            content_hash=compute_content_hash(data.content),
            status="pending",
            document_number=next_num,
            tags=data.tags,
            entity_type=data.entity_type,
            metadata_=data.metadata_,
            created_by=user_id,
        )
        db.add(doc)
        await db.flush()

        try:
            await index_document(db, doc.id, doc.content or "")
            doc.status = "ready"
            doc.last_indexed_at = datetime.now(timezone.utc)
        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
            logger.warning("创建文档后自动索引失败 %s: %s", str(doc.id)[:8], e)
        try:
            await reindex_document_references_for_kb(db, kb_id, doc)
        except Exception as e:
            logger.warning("创建文档后引用重建失败 %s: %s", str(doc.id)[:8], e)
        await db.flush()
        return doc

    @staticmethod
    async def get_document(db: AsyncSession, doc_id: UUID) -> KBDocument:
        result = await db.execute(select(KBDocument).where(KBDocument.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise NotFoundException("文档不存在")
        return doc

    @staticmethod
    async def get_document_for_user(
        db: AsyncSession, doc_id: UUID, user_id: UUID, role: Optional[str] = None
    ) -> KBDocument:
        """获取文档并校验访问权限（admin 全局放行；否则 KB 所有者或已订阅者）。

        未授权时不暴露文档存在性（统一抛 NotFoundException）。
        """
        doc = await KBDocumentService.get_document(db, doc_id)
        await KnowledgeBaseService.ensure_kb_access(db, doc.kb_id, user_id, role)
        return doc

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        kb_id: UUID,
        entity_type: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[KBDocument]:
        query = select(KBDocument).where(KBDocument.kb_id == kb_id)
        if not include_archived:
            query = query.where(KBDocument.archived == False)  # noqa: E712
        if entity_type:
            query = query.where(KBDocument.entity_type == entity_type)
        query = query.order_by(KBDocument.sort_order, KBDocument.document_number)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_document_content(
        db: AsyncSession, doc_id: UUID, data: KBDocumentContentUpdate, user_id: UUID
    ) -> KBDocument:
        """更新文档内容（乐观锁；自动重新分块索引 + 过期传播，失败置 status=failed）"""
        doc = await KBDocumentService.get_document(db, doc_id)

        if doc.version != data.version:
            raise BadRequestException(
                f"文档版本冲突：期望 {doc.version}，收到 {data.version}"
            )

        doc.content = data.content
        doc.content_hash = compute_content_hash(data.content)
        doc.version += 1
        doc.status = "pending"
        doc.last_indexed_at = None
        doc.stale_since = None
        if data.tags is not None:
            doc.tags = data.tags
        if data.title is not None:
            doc.title = data.title
        await db.flush()

        try:
            await reindex_document(db, doc.id, doc.content or "")
            doc.status = "ready"
            doc.last_indexed_at = datetime.now(timezone.utc)
            doc.stale_since = None
            await propagate_staleness(db, doc.id)
        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
            logger.warning("更新文档后自动索引失败 %s: %s", str(doc.id)[:8], e)
        try:
            await reindex_document_references_for_kb(db, doc.kb_id, doc)
        except Exception as e:
            logger.warning("更新文档后引用重建失败 %s: %s", str(doc.id)[:8], e)
        await db.flush()
        return doc

    @staticmethod
    async def update_document_metadata(
        db: AsyncSession, doc_id: UUID, data: KBDocumentMetadataUpdate
    ) -> KBDocument:
        doc = await KBDocumentService.get_document(db, doc_id)
        if data.title is not None:
            doc.title = data.title
        if data.tags is not None:
            doc.tags = data.tags
        if data.entity_type is not None:
            doc.entity_type = data.entity_type
        if data.metadata_ is not None:
            doc.metadata_ = data.metadata_
        if data.sort_order is not None:
            doc.sort_order = data.sort_order
        await db.flush()
        return doc

    @staticmethod
    async def archive_document(db: AsyncSession, doc_id: UUID) -> KBDocument:
        """软删除（置 archived=true）"""
        doc = await KBDocumentService.get_document(db, doc_id)
        doc.archived = True
        doc.status = "archived"
        await db.flush()
        return doc

    @staticmethod
    async def delete_document(db: AsyncSession, doc_id: UUID) -> None:
        doc = await KBDocumentService.get_document(db, doc_id)
        await db.delete(doc)
        await db.flush()