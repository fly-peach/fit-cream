"""
搜索 Service（全文+向量混合检索 + 跨库搜索）
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from src.knowledge_base.embeddings import aget_query_embedding, rerank, semantic_available
from src.knowledge_base.models.chunk import KBChunk
from src.knowledge_base.models.document import KBDocument
from src.knowledge_base.services.knowledge_base_service import KnowledgeBaseService
from utils.exceptions import NotFoundException

logger = logging.getLogger("fitcream")


def _escape_like(query: str) -> str:
    """转义 ILIKE 通配符（\\ % _），避免子串匹配被通配符污染。"""
    return (
        query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )


class KBSearchService:
    @staticmethod
    async def search_documents(
        db: AsyncSession,
        kb_id: UUID,
        query: str,
        limit: int = 20,
        query_embedding: Optional[list] = None,
        profile_hint: Optional[str] = None,
        use_ilike: bool = True,
    ) -> list:
        """语义 + 关键词混合检索（多路召回 + RRF 融合，可选 rerank 精排）。

        全文路：websearch_to_tsquery + ts_rank。
        ILIKE 路：中文子串召回（query 长度 1~32 时启用），补足中文全文路失效的短板。
        向量路：embedding 列可用时按余弦距离 top-K（K = max(limit*3, limit)）。
        融合：RRF（Reciprocal Rank Fusion, k=60）按 chunk_id 去重合并。
        精排：RRF 后 top 候选进 DashScope rerank（query 侧可携带用户画像 profile_hint，
              仅影响排序参考、不影响召回；不可用/异常回退 RRF 顺序）。
        降级：embedding 列缺失 / 服务失败 -> 全文 + ILIKE（纯关键词模式仍保留 ILIKE 路）。

        query_embedding: 跨库搜索时预计算的 query 向量，避免每个 KB 重复调用 embedding。
        profile_hint: 用户画像片段，仅注入 rerank query 侧做排序参考，不影响召回。
        use_ilike: 是否启用 ILIKE 第三路（评测 A/B 对照用）。
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
                "kb_id": str(doc.kb_id),
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

        # ---- ILIKE 路：中文子串召回（短内容密度高优先；1~32 字内执行）----
        ilike: list[dict] = []
        if use_ilike and 0 < len(query) <= 32:
            try:
                pattern = f"%{_escape_like(query)}%"
                ilike_result = await db.execute(
                    select(KBChunk, KBDocument)
                    .join(KBDocument, KBChunk.document_id == KBDocument.id)
                    .where(KBDocument.kb_id == kb_id)
                    .where(KBDocument.archived == False)  # noqa: E712
                    .where(KBChunk.content.ilike(pattern, escape="\\"))
                    .order_by(func.char_length(KBChunk.content).asc())
                    .limit(limit)
                )
                ilike = [
                    _to_dict(chunk, doc, 1.0) for chunk, doc in ilike_result.all()
                ]
            except Exception as e:
                logger.warning("ILIKE 路检索失败（跳过该路）: %s", e)

        if not await semantic_available(db):
            logger.warning(
                "语义检索不可用（embedding 列缺失或 KB_EMBEDDING_ENABLED=false），"
                "KB %s 搜索降级为全文 + ILIKE 关键词匹配",
                str(kb_id)[:8],
            )
            return KBSearchService._rrf_fuse(fulltext, ilike, limit=limit)

        # ---- 向量路：top-K 余弦最近邻 ----
        if query_embedding is None:
            query_embedding = await aget_query_embedding(query)
        if query_embedding is None:
            logger.warning("query embedding 生成失败（回退全文 + ILIKE）")
            return KBSearchService._rrf_fuse(fulltext, ilike, limit=limit)

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

        # ---- RRF 融合（多路） ----
        fused = KBSearchService._rrf_fuse(fulltext, ilike, semantic, limit=limit)
        if not fused:
            return KBSearchService._rrf_fuse(fulltext, ilike, limit=limit)

        # ---- 可选 rerank 精排（候选池扩大；query 侧带画像） ----
        candidates = fused[: min(limit * 2, 40)]
        return await rerank(query, candidates, top_n=limit, profile_hint=profile_hint)

    @staticmethod
    def _rrf_fuse(*ranked_lists: list[dict], limit: int, k: int = 60) -> list[dict]:
        """Reciprocal Rank Fusion：合并多路排名，按 chunk_id 去重。

        每路均按相关度降序，RRF 分数 = 求和 1/(k+rank)。
        """
        scores: dict[str, dict] = {}

        for ranked in ranked_lists:
            for rank, doc in enumerate(ranked, start=1):
                entry = scores.setdefault(doc["chunk_id"], doc)
                entry["_rrf"] = entry.get("_rrf", 0.0) + 1.0 / (k + rank)

        ordered = sorted(scores.values(), key=lambda x: x.get("_rrf", 0.0), reverse=True)
        for doc in ordered:
            # rank 覆盖为融合后的 RRF 分数，供跨库搜索合并排序
            doc["rank"] = doc.pop("_rrf", 0.0)
        return ordered[:limit]

    @staticmethod
    async def _search_one_kb(
        kb_id: UUID,
        query: str,
        limit: int,
        query_embedding: Optional[list],
        profile_hint: Optional[str],
        use_ilike: bool,
    ) -> list:
        """单库搜索（独立 session，供跨库并行调用；异常记日志返回空，不影响其他库）。"""
        try:
            async with async_session_factory() as session:
                return await KBSearchService.search_documents(
                    session,
                    kb_id,
                    query,
                    limit,
                    query_embedding,
                    profile_hint,
                    use_ilike,
                )
        except Exception as e:
            logger.warning("KB %s 搜索失败（跳过该库）: %s", str(kb_id)[:8], e)
            return []

    @staticmethod
    async def search_across_knowledge_bases(
        db: AsyncSession,
        query: str,
        kb_id: Optional[UUID] = None,
        limit: int = 5,
        profile_hint: Optional[str] = None,
        use_ilike: bool = True,
    ) -> list:
        """在全部知识库范围内搜索（多 KB 并行搜索 + rank 排序合并）。

        指定 kb_id 时只搜该 KB；未指定时并行搜索全部 KB，按相关度合并取 top limit。
        """
        if kb_id:
            return await KBSearchService.search_documents(
                db, kb_id, query, limit, profile_hint=profile_hint, use_ilike=use_ilike
            )

        kbs = await KnowledgeBaseService.list_kbs(db)
        if await semantic_available(db):
            query_embedding = await aget_query_embedding(query)
        else:
            query_embedding = None
        tasks = [
            KBSearchService._search_one_kb(
                kb.id, query, limit, query_embedding, profile_hint, use_ilike
            )
            for kb in kbs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_results: list = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("跨库搜索任务异常（跳过）: %s", r)
                continue
            all_results.extend(r)
        all_results.sort(key=lambda x: x.get("rank", 0), reverse=True)
        return all_results[:limit]

    @staticmethod
    async def search_across_subscriptions(
        db: AsyncSession,
        user_id: UUID,
        query: str,
        kb_id: Optional[UUID] = None,
        limit: int = 5,
        profile_hint: Optional[str] = None,
        use_ilike: bool = True,
    ) -> list:
        """在用户可访问范围内搜索（订阅 + 自有 KB，权限校验 + 多 KB 并行搜索 + rank 排序合并）。

        指定 kb_id 但既未订阅也非 owner 时抛 NotFoundException（tool 层转为友好提示）。
        未指定 kb_id 时并行搜索全部已订阅 + 自有的 KB，按相关度合并取 top limit。
        """
        if kb_id:
            accessible_ids = await KnowledgeBaseService.get_accessible_kb_ids(db, user_id)
            if kb_id not in accessible_ids:
                raise NotFoundException(f"未订阅知识库 {kb_id}，请先订阅后再搜索")
            return await KBSearchService.search_documents(
                db, kb_id, query, limit, profile_hint=profile_hint, use_ilike=use_ilike
            )

        kbs = await KnowledgeBaseService.list_my_accessible_kbs(db, user_id)
        if await semantic_available(db):
            query_embedding = await aget_query_embedding(query)
        else:
            query_embedding = None
        tasks = [
            KBSearchService._search_one_kb(
                kb.id, query, limit, query_embedding, profile_hint, use_ilike
            )
            for kb in kbs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_results: list = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("跨库搜索任务异常（跳过）: %s", r)
                continue
            all_results.extend(r)
        all_results.sort(key=lambda x: x.get("rank", 0), reverse=True)
        return all_results[:limit]
