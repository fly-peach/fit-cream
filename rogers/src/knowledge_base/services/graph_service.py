"""
图谱 / 索引 / 引用 Service
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge_base.graph import (
    find_stale_pages,
    find_uncited_sources,
    get_backlinks,
    get_forward_references,
    get_graph,
    rebuild_graph,
)
from src.knowledge_base.embeddings import semantic_available
from src.knowledge_base.indexer import reindex_knowledge_base
from src.knowledge_base.lint import run_all_lint
from src.knowledge_base.models.chunk import KBChunk
from src.knowledge_base.models.document import KBDocument


class KBGraphService:
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
    async def get_graph(
        db: AsyncSession, kb_id: UUID, mode: str = "full"
    ) -> dict:
        return await get_graph(db, kb_id, mode=mode)

    @staticmethod
    async def get_index_status(db: AsyncSession, kb_id: UUID) -> dict:
        """索引状态（从 kb_documents / kb_chunks 派生，不新增表）。

        返回总/已索引/待索引文档数、chunk 总数与未回填向量数、最后索引时间。
        """
        doc_result = await db.execute(
            select(
                func.count(KBDocument.id),
                func.count(KBDocument.id).filter(
                    KBDocument.last_indexed_at.isnot(None)
                ),
                func.count(KBDocument.id).filter(
                    (KBDocument.last_indexed_at.is_(None))
                    | (KBDocument.status == "failed")
                ),
                func.max(KBDocument.last_indexed_at),
            ).where(
                KBDocument.kb_id == kb_id,
                KBDocument.archived == False,  # noqa: E712
            )
        )
        total, indexed, pending, last_indexed = doc_result.one()

        # kb_chunks.embedding 是条件创建的向量列（pgvector 不可用时不存在）。
        # 语义不可用时跳过 embedding 统计，避免引用不存在列导致 UndefinedColumnError。
        if await semantic_available(db):
            chunk_result = await db.execute(
                select(
                    func.count(KBChunk.id),
                    func.count(KBChunk.id).filter(KBChunk.embedding.is_(None)),
                    func.max(KBChunk.created_at),
                )
                .join(KBDocument, KBChunk.document_id == KBDocument.id)
                .where(
                    KBDocument.kb_id == kb_id,
                    KBDocument.archived == False,  # noqa: E712
                )
            )
            chunks_total, chunks_no_embedding, last_chunk_indexed = chunk_result.one()
        else:
            chunk_result = await db.execute(
                select(func.count(KBChunk.id), func.max(KBChunk.created_at))
                .join(KBDocument, KBChunk.document_id == KBDocument.id)
                .where(
                    KBDocument.kb_id == kb_id,
                    KBDocument.archived == False,  # noqa: E712
                )
            )
            chunks_total, last_chunk_indexed = chunk_result.one()
            chunks_no_embedding = None

        return {
            "kb_id": str(kb_id),
            "total_documents": total,
            "indexed_documents": indexed,
            "pending_documents": pending,
            "chunks_total": chunks_total,
            "chunks_embedded": chunks_total - (chunks_no_embedding or 0),
            "chunks_pending_embedding": chunks_no_embedding,
            "last_indexed_at": last_indexed.isoformat() if last_indexed else None,
            "last_chunk_indexed_at": (
                last_chunk_indexed.isoformat() if last_chunk_indexed else None
            ),
        }

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

    @staticmethod
    async def run_lint(db: AsyncSession, kb_id: UUID) -> dict:
        """知识库健康检查（复用 lint.py 规则）"""
        result = await db.execute(select(KBDocument).where(KBDocument.kb_id == kb_id))
        docs = list(result.scalars().all())
        doc_dicts = [
            {
                "id": str(d.id), "filename": d.filename, "title": d.title,
                "path": d.path, "content": d.content, "tags": d.tags or [],
            }
            for d in docs
        ]

        backlinks_map: dict[str, list[dict]] = {}
        forward_map: dict[str, list[dict]] = {}
        for d in docs:
            did = str(d.id)
            backlinks_map[did] = await get_backlinks(db, d.id)
            forward_map[did] = await get_forward_references(db, d.id)

        uncited = await KBGraphService.find_uncited_sources(db, kb_id)
        stale = await KBGraphService.find_stale_pages(db, kb_id)

        report = run_all_lint(doc_dicts, uncited, stale, backlinks_map, forward_map)
        return {"kb_id": str(kb_id), **report}

    @staticmethod
    async def rebuild_lint(db: AsyncSession, kb_id: UUID) -> dict:
        """重建 lint：重建搜索索引 + 重建引用图 + 运行 lint，返回索引状态与 lint 报告。"""
        rebuilt = await KBGraphService.reindex_knowledge_base(db, kb_id)
        await KBGraphService.rebuild_graph(db, kb_id)
        lint_report = await KBGraphService.run_lint(db, kb_id)
        index_status = await KBGraphService.get_index_status(db, kb_id)
        return {"index": index_status, "rebuilt": rebuilt, "lint": lint_report}