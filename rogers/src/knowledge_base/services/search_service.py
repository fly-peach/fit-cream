"""
搜索 Service（全文+向量混合检索 + 跨库搜索）
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge_base.embeddings import rerank, semantic_available
from src.knowledge_base.models.chunk import KBChunk
from src.knowledge_base.models.document import KBDocument
from src.knowledge_base.services.knowledge_base_service import KnowledgeBaseService
from utils.exceptions import NotFoundException

logger = logging.getLogger("fitcream")


class KBSearchService:
    @staticmethod
    async def search_documents(
        db: AsyncSession,
        kb_id: UUID,
        query: str,
        limit: int = 20,
        query_embedding: Optional[list] = None,
    ) -> list:
        """语义 + 关键词混合检索（双路召回 + RRF 融合，可选 rerank 精排）。

        全文路：websearch_to_tsquery + ts_rank（现状）。
        向量路：embedding 列可用时按余弦距离 top-K（K = max(limit*3, limit)）。
        融合：RRF（Reciprocal Rank Fusion, k=60）按 chunk_id 去重合并。
        精排：RRF 后 top-N 进 DashScope rerank（不可用/异常回退 RRF）。
        降级：embedding 列缺失 / 服务失败 -> 纯全文（返回现状行为，并记录日志）。

        query_embedding: 跨库搜索时预计算的 query 向量，避免每个 KB 重复调用 embedding。
        """
        tsquery = func.websearch_to_tsquery("simple", query)
        result = await db.execute(
            select(KBChunk, KBDocument, func.ts_rank(KBChunk.search_vector, tsquery).label("rank"))
            .join(KBDocument, KBChunk.document_id == KBDocument.id)
            .where(KBDocument.kb_id == kb_id)
            .where(KBDocument.archived == False)  # noqa: E712
            .where(KBChunk.search_vector.op("@@")(tsquery))
            .order_by(func.ts_rank(KBChunk.search_vector, tsquery).desc())
            .limit(limit)
        )
        rows = result.all()

        def _to_dict(chunk, doc, rank) -> dict:
            return {
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

        fulltext = [_to_dict(chunk, doc, rank) for chunk, doc, rank in rows]

        if not await semantic_available(db):
            logger.warning(
                "语义检索不可用（embedding 列缺失或 KB_EMBEDDING_ENABLED=false），"
                "KB %s 搜索降级为纯全文",
                str(kb_id)[:8],
            )
            return fulltext[:limit]

        # ---- 向量路：top-K 余弦最近邻 ----
        try:
            if query_embedding is None:
                from src.agents.harness.runtime.memory.embeddings import get_embedding_model

                embed_model = get_embedding_model()
                query_embedding = await embed_model.aget_text_embedding(query)
        except Exception as e:
            logger.warning("向量路 query embedding 生成失败（回退纯全文）: %s", e)
            return fulltext[:limit]

        vector_k = max(limit * 3, limit)
        dist = KBChunk.embedding.cosine_distance(query_embedding)
        vec_result = await db.execute(
            select(KBChunk, KBDocument, dist.label("distance"))
            .join(KBDocument, KBChunk.document_id == KBDocument.id)
            .where(KBDocument.kb_id == kb_id)
            .where(KBDocument.archived == False)  # noqa: E712
            .where(KBChunk.embedding.isnot(None))
            .order_by(dist)
            .limit(vector_k)
        )
        semantic = [
            _to_dict(chunk, doc, 1.0 - float(distance))
            for chunk, doc, distance in vec_result.all()
        ]

        # ---- RRF 融合 ----
        fused = KBSearchService._rrf_fuse(fulltext, semantic, limit)
        if not fused:
            return fulltext[:limit]

        # ---- 可选 rerank 精排 ----
        return await rerank(query, fused[:limit], top_n=min(limit, 20))

    @staticmethod
    def _rrf_fuse(
        fulltext: list[dict], semantic: list[dict], limit: int, k: int = 60
    ) -> list[dict]:
        """Reciprocal Rank Fusion：合并两路排名，按 chunk_id 去重。

        fulltext / semantic 均按相关度降序，RRF 分数 = 求和 1/(k+rank)。
        """
        scores: dict[str, dict] = {}

        for rank, doc in enumerate(fulltext, start=1):
            entry = scores.setdefault(doc["chunk_id"], doc)
            entry["_rrf"] = entry.get("_rrf", 0.0) + 1.0 / (k + rank)
        for rank, doc in enumerate(semantic, start=1):
            entry = scores.setdefault(doc["chunk_id"], doc)
            entry["_rrf"] = entry.get("_rrf", 0.0) + 1.0 / (k + rank)

        ordered = sorted(scores.values(), key=lambda x: x.get("_rrf", 0.0), reverse=True)
        for doc in ordered:
            # rank 覆盖为融合后的 RRF 分数，供跨库搜索合并排序
            doc["rank"] = doc.pop("_rrf", 0.0)
        return ordered[:limit]

    @staticmethod
    async def _compute_query_embedding(query: str) -> Optional[list]:
        """跨库搜索时只生成一次 query 向量（失败返回 None，调用方逐库兜底）。"""
        try:
            from src.agents.harness.runtime.memory.embeddings import get_embedding_model

            model = get_embedding_model()
            return await model.aget_text_embedding(query)
        except Exception as e:
            logger.warning("跨库搜索 query embedding 生成失败: %s", e)
            return None

    @staticmethod
    async def search_across_knowledge_bases(
        db: AsyncSession,
        query: str,
        kb_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> list:
        """在全部知识库范围内搜索（多 KB 搜索 + rank 排序合并）。

        指定 kb_id 时只搜该 KB；未指定时搜索全部 KB，按相关度合并取 top limit。
        """
        if kb_id:
            return await KBSearchService.search_documents(db, kb_id, query, limit)

        kbs = await KnowledgeBaseService.list_kbs(db)
        if await semantic_available(db):
            query_embedding = await KBSearchService._compute_query_embedding(query)
        else:
            query_embedding = None
        all_results: list = []
        for kb in kbs:
            all_results.extend(
                await KBSearchService.search_documents(
                    db, kb.id, query, limit, query_embedding
                )
            )
        all_results.sort(key=lambda x: x.get("rank", 0), reverse=True)
        return all_results[:limit]

    @staticmethod
    async def search_across_subscriptions(
        db: AsyncSession,
        user_id: UUID,
        query: str,
        kb_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> list:
        """在用户可访问范围内搜索（订阅 + 自有 KB，权限校验 + 多 KB 搜索 + rank 排序合并）。

        指定 kb_id 但既未订阅也非 owner 时抛 NotFoundException（tool 层转为友好提示）。
        未指定 kb_id 时搜索全部已订阅 + 自有的 KB，按相关度合并取 top limit。
        """
        if kb_id:
            accessible_ids = await KnowledgeBaseService.get_accessible_kb_ids(db, user_id)
            if kb_id not in accessible_ids:
                raise NotFoundException(f"未订阅知识库 {kb_id}，请先订阅后再搜索")
            return await KBSearchService.search_documents(db, kb_id, query, limit)

        kbs = await KnowledgeBaseService.list_my_accessible_kbs(db, user_id)
        if await semantic_available(db):
            query_embedding = await KBSearchService._compute_query_embedding(query)
        else:
            query_embedding = None
        all_results: list = []
        for kb in kbs:
            all_results.extend(
                await KBSearchService.search_documents(
                    db, kb.id, query, limit, query_embedding
                )
            )
        all_results.sort(key=lambda x: x.get("rank", 0), reverse=True)
        return all_results[:limit]