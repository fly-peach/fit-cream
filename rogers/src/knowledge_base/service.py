"""
知识库 Service 编排层

遵循现有 fitme/services/plan_service.py 的 @staticmethod 模式。
Service 层只做编排：调用纯逻辑模块 + DB 读写，不包含文本处理算法。
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.knowledge_base.graph import (
    find_stale_pages,
    find_uncited_sources,
    get_backlinks,
    get_forward_references,
    get_graph,
    propagate_staleness,
    rebuild_graph,
)
from src.knowledge_base.indexer import (
    compute_content_hash,
    index_document,
    reindex_document,
    reindex_knowledge_base,
)
from src.knowledge_base.models import (
    KBApiToken,
    KBDocument,
    KBSubscription,
    KnowledgeBase,
)
from src.knowledge_base.parsers import (
    UnsupportedFormatError,
    extract_title,
    parse_document,
    parse_frontmatter,
)
from src.knowledge_base.schemas import (
    KBDocumentCreate,
    KBDocumentContentUpdate,
    KBDocumentMetadataUpdate,
    KBTokenCreate,
)
from utils.exceptions import BadRequestException, NotFoundException

logger = logging.getLogger("fitcream")


class KnowledgeBaseService:
    # ============================================================
    # 知识库管理
    # ============================================================

    @staticmethod
    async def create_kb(
        db: AsyncSession, owner_id: UUID, name: str, description: str = "", schema_config: Optional[dict] = None
    ) -> KnowledgeBase:
        """创建知识库（含碰撞安全 slug + 预生成 share_token）"""
        slug = await KnowledgeBaseService._generate_unique_slug(db, name, owner_id)
        kb = KnowledgeBase(
            name=name,
            description=description,
            slug=slug,
            owner_id=owner_id,
            visibility="private",
            share_token=secrets.token_hex(16),
            schema_config=schema_config or {},
        )
        db.add(kb)
        await db.flush()
        return kb

    @staticmethod
    async def _generate_unique_slug(db: AsyncSession, name: str, owner_id: UUID) -> str:
        """碰撞安全 slug 生成（参考 LLM Wiki generate_slug）"""
        base = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
        if not base:
            base = "untitled"

        candidate = base
        counter = 0
        while True:
            result = await db.execute(
                select(KnowledgeBase).where(KnowledgeBase.slug == candidate)
            )
            if not result.scalar_one_or_none():
                return candidate
            counter += 1
            candidate = f"{base}-{counter}"

    @staticmethod
    async def list_kbs(db: AsyncSession) -> List[KnowledgeBase]:
        """返回全部知识库（内部全可见：登录用户可读任意 KB）。"""
        result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_kb(db: AsyncSession, kb_id: UUID) -> KnowledgeBase:
        result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        kb = result.scalar_one_or_none()
        if not kb:
            raise NotFoundException("知识库不存在")
        return kb

    @staticmethod
    async def get_kb_by_share_token(db: AsyncSession, token: str) -> KnowledgeBase:
        result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.share_token == token)
        )
        kb = result.scalar_one_or_none()
        if not kb or kb.visibility == "private":
            raise NotFoundException("知识库不存在或未分享")
        return kb

    @staticmethod
    async def get_kb_by_public_slug(db: AsyncSession, slug: str) -> KnowledgeBase:
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.public_slug == slug,
                KnowledgeBase.visibility == "public",
            )
        )
        kb = result.scalar_one_or_none()
        if not kb:
            raise NotFoundException("公开知识库不存在")
        return kb

    @staticmethod
    async def update_kb(
        db: AsyncSession, kb_id: UUID, name: Optional[str] = None,
        description: Optional[str] = None, schema_config: Optional[dict] = None,
    ) -> KnowledgeBase:
        kb = await KnowledgeBaseService.get_kb(db, kb_id)
        if name is not None:
            kb.name = name
        if description is not None:
            kb.description = description
        if schema_config is not None:
            kb.schema_config = schema_config
        await db.flush()
        return kb

    @staticmethod
    async def set_visibility(
        db: AsyncSession, kb_id: UUID, visibility: str, public_slug: Optional[str] = None
    ) -> KnowledgeBase:
        kb = await KnowledgeBaseService.get_kb(db, kb_id)
        kb.visibility = visibility
        if visibility == "public":
            if not public_slug:
                raise BadRequestException("公开知识库需要 public_slug")
            kb.public_slug = public_slug
        await db.flush()
        return kb

    @staticmethod
    async def delete_kb(db: AsyncSession, kb_id: UUID) -> None:
        kb = await KnowledgeBaseService.get_kb(db, kb_id)
        await db.delete(kb)
        await db.flush()

    # ============================================================
    # 文档 CRUD
    # ============================================================

    @staticmethod
    async def create_document(
        db: AsyncSession, kb_id: UUID, data: KBDocumentCreate, user_id: UUID
    ) -> KBDocument:
        """创建文档 + 自动分块索引"""
        kb = await KnowledgeBaseService.get_kb(db, kb_id)

        content = data.content
        metadata, clean_content = parse_frontmatter(content)
        title = extract_title(
            {**metadata, **({"title": data.title} if data.title else {})},
            clean_content,
            data.filename,
        )

        # per-KB 递增序号
        max_num_result = await db.execute(
            select(func.max(KBDocument.document_number)).where(
                KBDocument.kb_id == kb_id
            )
        )
        next_num = (max_num_result.scalar() or 0) + 1

        doc = KBDocument(
            kb_id=kb_id,
            title=title,
            filename=data.filename,
            path=data.path,
            source_kind=data.source_kind,
            file_type=data.file_type,
            content=content,
            content_hash=compute_content_hash(content),
            status="ready",
            document_number=next_num,
            tags=data.tags,
            entity_type=data.entity_type,
            metadata_=data.metadata_,
            created_by=user_id,
        )
        db.add(doc)
        await db.flush()

        await index_document(db, doc.id, content)
        doc.last_indexed_at = datetime.now(timezone.utc)
        await db.flush()
        return doc

    @staticmethod
    async def create_document_from_file(
        db: AsyncSession,
        kb_id: UUID,
        content_bytes: bytes,
        filename: str,
        user_id: UUID,
        path: str = "/",
        source_kind: str = "raw",
        tags: Optional[list[str]] = None,
        entity_type: Optional[str] = None,
        content_type: Optional[str] = None,
        languages: Optional[list[str]] = None,
    ) -> KBDocument:
        """从上传文件创建文档（unstructured 多格式解析 + 元素感知分块）。

        流程: parse_document(任意格式 -> 元素 + Markdown)
              -> 存 content -> index_document(elements)
        """
        await KnowledgeBaseService.get_kb(db, kb_id)

        try:
            parsed = parse_document(
                content_bytes, filename, content_type=content_type, languages=languages
            )
        except UnsupportedFormatError:
            raise

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "md"

        max_num_result = await db.execute(
            select(func.max(KBDocument.document_number)).where(
                KBDocument.kb_id == kb_id
            )
        )
        next_num = (max_num_result.scalar() or 0) + 1

        fm_tags = parsed.metadata.get("tags") if isinstance(parsed.metadata, dict) else None
        final_tags = tags or (fm_tags if isinstance(fm_tags, list) else [])

        doc = KBDocument(
            kb_id=kb_id,
            title=parsed.title,
            filename=filename,
            path=path,
            source_kind=source_kind,
            file_type=ext,
            content=parsed.content,
            content_hash=compute_content_hash(parsed.content),
            status="ready",
            document_number=next_num,
            page_count=parsed.page_count or None,
            parser="unstructured",
            tags=final_tags,
            entity_type=entity_type,
            metadata_=parsed.metadata,
            created_by=user_id,
        )
        db.add(doc)
        await db.flush()

        elements_dicts = [
            {"type": e.type, "text": e.text, "page": e.page}
            for e in parsed.elements
        ]
        await index_document(db, doc.id, parsed.content, elements=elements_dicts)
        doc.last_indexed_at = datetime.now(timezone.utc)
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
        db: AsyncSession, doc_id: UUID, user_id: UUID
    ) -> KBDocument:
        """获取文档并校验访问权限（KB 所有者或已订阅者）。

        未授权时不暴露文档存在性（统一抛 NotFoundException）。
        """
        doc = await KnowledgeBaseService.get_document(db, doc_id)
        kb = await KnowledgeBaseService.get_kb(db, doc.kb_id)
        if kb.owner_id == user_id:
            return doc
        subscribed = await KnowledgeBaseService.get_subscribed_kb_ids(db, user_id)
        if doc.kb_id not in subscribed:
            raise NotFoundException("文档不存在")
        return doc

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        kb_id: UUID,
        source_kind: Optional[str] = None,
        entity_type: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[KBDocument]:
        query = select(KBDocument).where(KBDocument.kb_id == kb_id)
        if not include_archived:
            query = query.where(KBDocument.archived == False)  # noqa: E712
        if source_kind:
            query = query.where(KBDocument.source_kind == source_kind)
        if entity_type:
            query = query.where(KBDocument.entity_type == entity_type)
        query = query.order_by(KBDocument.sort_order, KBDocument.document_number)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_document_content(
        db: AsyncSession, doc_id: UUID, data: KBDocumentContentUpdate, user_id: UUID
    ) -> KBDocument:
        """更新文档内容（乐观锁 + 触发重新分块 + 过期传播）"""
        doc = await KnowledgeBaseService.get_document(db, doc_id)

        if doc.version != data.version:
            raise BadRequestException(
                f"文档版本冲突：期望 {doc.version}，收到 {data.version}"
            )

        doc.content = data.content
        doc.content_hash = compute_content_hash(data.content)
        doc.version += 1
        if data.tags is not None:
            doc.tags = data.tags
        if data.title is not None:
            doc.title = data.title

        await reindex_document(db, doc.id, data.content)
        doc.last_indexed_at = datetime.now(timezone.utc)
        doc.stale_since = None
        await db.flush()

        # 过期传播：通知引用本文档的 wiki 页
        await propagate_staleness(db, doc.id)
        return doc

    @staticmethod
    async def update_document_metadata(
        db: AsyncSession, doc_id: UUID, data: KBDocumentMetadataUpdate
    ) -> KBDocument:
        doc = await KnowledgeBaseService.get_document(db, doc_id)
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
        doc = await KnowledgeBaseService.get_document(db, doc_id)
        doc.archived = True
        doc.status = "archived"
        await db.flush()
        return doc

    @staticmethod
    async def delete_document(db: AsyncSession, doc_id: UUID) -> None:
        doc = await KnowledgeBaseService.get_document(db, doc_id)
        await db.delete(doc)
        await db.flush()

    # ============================================================
    # 搜索 + 图谱
    # ============================================================

    @staticmethod
    async def search_documents(
        db: AsyncSession, kb_id: UUID, query: str, limit: int = 20
    ) -> list:
        """PostgreSQL 全文搜索（websearch_to_tsquery）"""
        from src.knowledge_base.models import KBChunk

        tsquery = func.websearch_to_tsquery("simple", query)
        result = await db.execute(
            select(KBChunk, func.ts_rank(KBChunk.search_vector, tsquery).label("rank"))
            .join(KBDocument, KBChunk.document_id == KBDocument.id)
            .where(KBDocument.kb_id == kb_id)
            .where(KBDocument.archived == False)  # noqa: E712
            .where(KBChunk.search_vector.op("@@")(tsquery))
            .order_by(func.ts_rank(KBChunk.search_vector, tsquery).desc())
            .limit(limit)
        )
        rows = result.all()
        return [
            {
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "document_title": doc.title,
                "filename": doc.filename,
                "path": doc.path,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "header_breadcrumb": chunk.header_breadcrumb,
                "token_count": chunk.token_count,
                "rank": float(rank) if rank else 0.0,
            }
            for chunk, doc, rank in rows
        ]

    @staticmethod
    async def get_document_references(db: AsyncSession, doc_id: UUID) -> dict:
        forward = await get_forward_references(db, doc_id)
        backlinks = await get_backlinks(db, doc_id)
        return {
            "document_id": str(doc_id),
            "cites": [r for r in forward if r["reference_type"] == "cites"],
            "links_to": [r for r in forward if r["reference_type"] == "links_to"],
            "cited_by": [r for r in backlinks if r["reference_type"] == "cites"],
            "linked_by": [r for r in backlinks if r["reference_type"] == "links_to"],
        }

    @staticmethod
    async def get_graph(db: AsyncSession, kb_id: UUID) -> dict:
        return await get_graph(db, kb_id)

    @staticmethod
    async def rebuild_graph(db: AsyncSession, kb_id: UUID) -> dict:
        return await rebuild_graph(db, kb_id)

    @staticmethod
    async def reindex_knowledge_base(db: AsyncSession, kb_id: UUID) -> dict:
        return await reindex_knowledge_base(db, kb_id)

    @staticmethod
    async def find_uncited_sources(db: AsyncSession, kb_id: UUID) -> list:
        return await find_uncited_sources(db, kb_id)

    @staticmethod
    async def find_stale_pages(db: AsyncSession, kb_id: UUID) -> list:
        return await find_stale_pages(db, kb_id)

    # ============================================================
    # 订阅管理（两级权限：用户自助订阅 + admin 管理订阅者）
    # ============================================================

    @staticmethod
    async def subscribe(
        db: AsyncSession, kb_id: UUID, user_id: UUID
    ) -> KBSubscription:
        """用户自助订阅知识库（幂等：已订阅则返回现有记录）"""
        await KnowledgeBaseService.get_kb(db, kb_id)
        existing = await db.execute(
            select(KBSubscription).where(
                KBSubscription.kb_id == kb_id, KBSubscription.user_id == user_id
            )
        )
        sub = existing.scalar_one_or_none()
        if sub:
            return sub
        sub = KBSubscription(kb_id=kb_id, user_id=user_id)
        db.add(sub)
        await db.flush()
        return sub

    @staticmethod
    async def unsubscribe(db: AsyncSession, kb_id: UUID, user_id: UUID) -> None:
        """取消订阅（幂等：未订阅也不报错）"""
        result = await db.execute(
            select(KBSubscription).where(
                KBSubscription.kb_id == kb_id, KBSubscription.user_id == user_id
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            await db.delete(sub)
            await db.flush()

    @staticmethod
    async def get_subscribed_kb_ids(db: AsyncSession, user_id: UUID) -> set[UUID]:
        """返回用户已订阅的 KB ID 集合（供 list 标记 subscribed 态 + Agent 搜索范围）"""
        result = await db.execute(
            select(KBSubscription.kb_id).where(KBSubscription.user_id == user_id)
        )
        return {row[0] for row in result.all()}

    @staticmethod
    async def list_my_subscriptions(
        db: AsyncSession, user_id: UUID
    ) -> List[KnowledgeBase]:
        """返回用户已订阅的知识库列表"""
        subscribed_ids = await KnowledgeBaseService.get_subscribed_kb_ids(db, user_id)
        if not subscribed_ids:
            return []
        result = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.id.in_(subscribed_ids))
            .order_by(KnowledgeBase.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def search_across_subscriptions(
        db: AsyncSession,
        user_id: UUID,
        query: str,
        kb_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> list:
        """在用户已订阅范围内搜索（订阅校验 + 多 KB 搜索 + rank 排序合并）。

        指定 kb_id 但未订阅时抛 NotFoundException（tool 层转为友好提示）。
        未指定 kb_id 时搜索全部已订阅 KB，按相关度合并取 top limit。
        """
        if kb_id:
            subscribed_ids = await KnowledgeBaseService.get_subscribed_kb_ids(db, user_id)
            if kb_id not in subscribed_ids:
                raise NotFoundException(f"未订阅知识库 {kb_id}，请先订阅后再搜索")
            return await KnowledgeBaseService.search_documents(db, kb_id, query, limit)

        kbs = await KnowledgeBaseService.list_my_subscriptions(db, user_id)
        all_results: list = []
        for kb in kbs:
            all_results.extend(
                await KnowledgeBaseService.search_documents(db, kb.id, query, limit)
            )
        all_results.sort(key=lambda x: x.get("rank", 0), reverse=True)
        return all_results[:limit]

    @staticmethod
    async def list_subscribers(
        db: AsyncSession, kb_id: UUID
    ) -> List[KBSubscription]:
        """列出某 KB 的全部订阅者（admin，含用户信息）"""
        result = await db.execute(
            select(KBSubscription)
            .options(selectinload(KBSubscription.user))
            .where(KBSubscription.kb_id == kb_id)
            .order_by(KBSubscription.subscribed_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def remove_subscriber(
        db: AsyncSession, kb_id: UUID, user_id: UUID
    ) -> None:
        """admin 踢出某订阅者（幂等）"""
        await KnowledgeBaseService.unsubscribe(db, kb_id, user_id)

    # ============================================================
    # API 令牌
    # ============================================================

    @staticmethod
    async def create_token(
        db: AsyncSession, kb_id: UUID, data: KBTokenCreate, user_id: UUID
    ) -> tuple[str, KBApiToken]:
        """创建令牌，返回 (明文 token, token 记录)。明文仅此一次返回。"""
        raw_token = "fc_kt_" + secrets.token_hex(24)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        prefix = raw_token[:12]

        token = KBApiToken(
            kb_id=kb_id,
            token_hash=token_hash,
            token_prefix=prefix,
            name=data.name,
            scope=data.scope,
            created_by=user_id,
            expires_at=data.expires_at,
        )
        db.add(token)
        await db.flush()
        return raw_token, token

    @staticmethod
    async def verify_token(
        db: AsyncSession, kb_id: UUID, raw_token: str
    ) -> Optional[KBApiToken]:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        result = await db.execute(
            select(KBApiToken).where(
                KBApiToken.kb_id == kb_id,
                KBApiToken.token_hash == token_hash,
                KBApiToken.revoked_at.is_(None),
            )
        )
        token = result.scalar_one_or_none()
        if not token:
            return None
        if token.expires_at and token.expires_at < datetime.now(timezone.utc):
            return None
        token.last_used_at = datetime.now(timezone.utc)
        await db.flush()
        return token

    @staticmethod
    async def list_tokens(db: AsyncSession, kb_id: UUID) -> List[KBApiToken]:
        result = await db.execute(
            select(KBApiToken).where(KBApiToken.kb_id == kb_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def revoke_token(db: AsyncSession, token_id: UUID) -> KBApiToken:
        result = await db.execute(
            select(KBApiToken).where(KBApiToken.id == token_id)
        )
        token = result.scalar_one_or_none()
        if not token:
            raise NotFoundException("令牌不存在")
        token.revoked_at = datetime.now(timezone.utc)
        await db.flush()
        return token
