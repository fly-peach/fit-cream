"""
知识库语义检索辅助（向量化 + rerank）

复用现有记忆系统的 DashScope embedding 基建（src/agents/harness/runtime/memory/embeddings.py），
提供知识库 chunk 级别的：
- semantic_available: 探测 kb_chunks.embedding 向量列是否存在（进程级缓存）
- embed_chunks: 批量生成文本向量（失败降级为 None，不阻断入库）
- rerank: 基于 llama-index-postprocessor-dashscope-rerank 对候选精排（不可用/异常时原样返回）

降级链：embedding 列缺失 / 服务失败 -> 纯全文；rerank 不可用 -> 回退 RRF。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger("fitcream")

EMBED_CONCURRENCY = 8

# semantic_available 探测结果的 TTL 缓存（秒）：部署后补列/回填无需重启进程即可生效
SEMANTIC_CACHE_TTL = 300.0


def _get_setting(key: str, default: str) -> str:
    try:
        return str(getattr(get_settings(), key, default))
    except Exception:
        return default


RERANK_ENABLED = _get_setting("RERANK_ENABLED", "True").lower() in ("1", "true", "yes")
RERANK_MODEL = _get_setting("RERANK_MODEL", "gte-rerank-v2")
RERANK_TOP_N = int(_get_setting("RERANK_TOP_N", "20"))

# 知识库语义向量整体开关（运营/测试可关闭，关闭后检索退化为纯全文）
KB_EMBEDDING_ENABLED = _get_setting("KB_EMBEDDING_ENABLED", "True").lower() in (
    "1",
    "true",
    "yes",
)


# kb_chunks.embedding 向量列是否可用（进程级缓存，TTL 后重新探测）
_embedding_col_available: Optional[bool] = None
_embedding_col_probed_at: Optional[float] = None


async def semantic_available(db: AsyncSession) -> bool:
    """语义检索是否可用（kb_chunks.embedding 向量列存在）。

    KB_EMBEDDING_ENABLED=false 时整体关闭；pgvector 扩展不可用时 init_db 不会创建该列，
    语义检索整体关闭（不做降级）：本方法返回 False，调用方自行回退纯全文检索。
    探测结果按 TTL 缓存，避免每个请求重复查询 information_schema。
    """
    global _embedding_col_available, _embedding_col_probed_at
    if not KB_EMBEDDING_ENABLED:
        return False
    now = time.monotonic()
    if (
        _embedding_col_available is None
        or _embedding_col_probed_at is None
        or now - _embedding_col_probed_at > SEMANTIC_CACHE_TTL
    ):
        result = await db.execute(
            text(
                "SELECT 1 FROM information_schema.columns"
                " WHERE table_name = 'kb_chunks' AND column_name = 'embedding'"
                " AND udt_name = 'vector'"
            )
        )
        _embedding_col_available = result.scalar() is not None
        _embedding_col_probed_at = now
    return _embedding_col_available


async def embed_chunks(contents: list[str]) -> list[Optional[list[float]]]:
    """批量生成 chunk 文本向量。

    返回与输入等长的列表；单条失败或整体异常时对应位置为 None（调用方置 NULL，不阻断）。
    """
    if not contents:
        return []
    try:
        # 延迟导入：避免在仅导入知识库模块时触发 src.agents 的 agent graph 构建
        from src.agents.harness.runtime.memory.embeddings import get_embedding_model

        model = get_embedding_model()
    except Exception as e:
        logger.warning("embedding 模型不可用，跳过向量化: %s", e)
        return [None] * len(contents)

    sem = asyncio.Semaphore(EMBED_CONCURRENCY)
    results: list[Optional[list[float]]] = [None] * len(contents)

    async def embed_one(i: int, content: str) -> None:
        async with sem:
            try:
                results[i] = await model.aget_text_embedding(content)
            except Exception as e:
                logger.warning("chunk 向量化失败: %s", e)

    await asyncio.gather(*(embed_one(i, c) for i, c in enumerate(contents)))
    return results


# rerank 后处理器（进程级缓存，避免每次搜索重建）
_reranker = None


def _load_reranker():
    """懒加载 rerank 后处理器；未启用/缺失依赖时返回 None（进程内只加载一次）。"""
    global _reranker
    if _reranker is not None:
        return _reranker
    if not RERANK_ENABLED:
        return None
    try:
        from llama_index.postprocessor.dashscope_rerank import DashScopeRerank

        _reranker = DashScopeRerank(
            model=RERANK_MODEL,
            top_n=RERANK_TOP_N,
        )
        return _reranker
    except Exception as e:
        logger.warning("rerank 后处理器加载失败（回退 RRF）: %s", e)
        return None


async def rerank(query: str, results: list[dict], top_n: int = RERANK_TOP_N) -> list[dict]:
    """对候选结果精排。

    results 为 search_documents 产出的 dict 列表（含 content），返回按 rerank 分重排的列表。
    不可用/异常时原样返回（调用方保留 RRF 顺序）。
    """
    if not results:
        return results
    postprocessor = _load_reranker()
    if postprocessor is None:
        return results

    from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

    try:
        query_bundle = QueryBundle(query_str=query)
        nodes = [
            NodeWithScore(node=TextNode(text=r["content"], metadata={"index": i}), score=0.0)
            for i, r in enumerate(results)
        ]
        reranked = postprocessor.postprocess_nodes(nodes, query_bundle)

        # 依据 metadata.index 映射回原结果；任一缺失则视为不可用，回退原顺序
        ordered: list[dict] = []
        for n in reranked:
            node = getattr(n, "node", n)
            metadata = getattr(node, "metadata", {}) or {}
            idx = metadata.get("index", None)
            if not isinstance(idx, int) or not (0 <= idx < len(results)):
                return results
            ordered.append(results[idx])
        chosen = {id(r) for r in ordered}
        ordered.extend(r for r in results if id(r) not in chosen)
        return ordered[:top_n]
    except Exception as e:
        logger.warning("rerank 执行失败（回退 RRF）: %s", e)
        return results