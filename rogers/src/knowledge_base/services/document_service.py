"""
文档 Service（文档 CRUD）

写文档不自动索引（chunks/embedding/引用图统一由重建步骤构建）。
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge_base.indexer import compute_content_hash
from src.knowledge_base.models.document import KBDocument
from src.knowledge_base.schemas.document import (
    KBDocumentContentUpdate,
    KBDocumentCreate,
    KBDocumentMetadataUpdate,
)
from src.knowledge_base.services.knowledge_base_service import KnowledgeBaseService
from utils.exceptions import BadRequestException, NotFoundException


class KBDocumentService:
    @staticmethod
    async def create_document(
        db: AsyncSession, kb_id: UUID, data: KBDocumentCreate, user_id: UUID
    ) -> KBDocument:
        """创建 wiki 文档（只写行，status=pending，待重建时索引）"""
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
        return doc

    @staticmethod
    async def get_document(db: AsyncSession, doc_id: UUID) -> KBDocument:
        result = await db.execute(select(KBDocument).where(KBDocument.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise NotFoundException("文档不存在")
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
        """更新文档内容（乐观锁；只写行，置 status=pending，待重建时重索引）"""
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