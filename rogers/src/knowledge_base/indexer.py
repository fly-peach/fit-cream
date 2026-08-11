"""
分块 + 索引编排（DB 编排层）

参考 LLM Wiki chunker.store_chunks 的原子写策略：
chunk_text(content) -> 批量 INSERT chunks -> 重建引用（单事务原子操作）。
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge_base.chunker import chunk_text
from src.knowledge_base.embeddings import embed_chunks, semantic_available
from src.knowledge_base.models.chunk import KBChunk
from src.knowledge_base.models.document import KBDocument

logger = logging.getLogger("fitcream")


def compute_content_hash(content: str) -> str:
    """计算内容的 SHA256 哈希（用于增量索引）"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def index_document(
    db: AsyncSession,
    doc_id: UUID,
    content: str,
) -> int:
    """分块 + 写入 kb_chunks（单事务原子操作）。

    按纯文本/Markdown 标题段落边界分块（wiki 文档无结构化元素）。
    返回: chunk 数量
    """
    chunks = chunk_text(content)
    if not chunks:
        return 0

    # kb_chunks.embedding 是条件创建的向量列（pgvector 不可用时不存在）。
    # 语义可用时才打向量；否则 INSERT 省略 embedding 列，避免引用不存在列导致 UndefinedColumnError。
    semantic = await semantic_available(db)
    if semantic:
        embeddings = await embed_chunks([c.content for c in chunks])

    rows = [
        {
            "document_id": doc_id,
            "chunk_index": c.index,
            "content": c.content,
            "source_content": c.content,
            "token_count": c.token_count,
            "start_char": c.start_char,
            "header_breadcrumb": c.header_breadcrumb,
        }
        for c in chunks
    ]
    if semantic:
        for i, row in enumerate(rows):
            row["embedding"] = embeddings[i]

    await db.execute(insert(KBChunk), rows)
    logger.info("索引文档 %s: %d chunks", str(doc_id)[:8], len(chunks))
    return len(chunks)


async def reindex_document(
    db: AsyncSession, doc_id: UUID, content: str
) -> int:
    """增量重建：先 DELETE 旧 chunks -> 再 index_document（同事务）"""
    await db.execute(delete(KBChunk).where(KBChunk.document_id == doc_id))
    await db.flush()
    return await index_document(db, doc_id, content)


async def reindex_knowledge_base(db: AsyncSession, kb_id: UUID) -> dict:
    """全量重建：仅处理 content_hash 变化或 last_indexed_at IS NULL 的文档"""
    result = await db.execute(
        select(KBDocument).where(
            KBDocument.kb_id == kb_id,
            KBDocument.archived == False,  # noqa: E712
            KBDocument.status.in_(["ready", "pending", "processing", "failed"]),
        )
    )
    docs = list(result.scalars().all())

    processed = 0
    chunks_created = 0
    for doc in docs:
        current_hash = compute_content_hash(doc.content or "")
        if doc.content_hash == current_hash and doc.last_indexed_at:
            continue

        n = await reindex_document(db, doc.id, doc.content or "")
        doc.content_hash = current_hash
        doc.last_indexed_at = datetime.now(timezone.utc)
        doc.status = "ready"
        doc.stale_since = None
        processed += 1
        chunks_created += n

    # 全量重建即确认本 KB 全部文档为当前状态，复位引用方过期标记
    # （propagate_staleness 只打标不清除，重建后应一并复位，避免整库误标过期）
    await db.execute(
        update(KBDocument)
        .where(
            KBDocument.kb_id == kb_id,
            KBDocument.archived == False,  # noqa: E712
        )
        .values(stale_since=None)
    )

    await db.flush()
    logger.info(
        "全量重建 KB %s: %d docs, %d chunks", str(kb_id)[:8], processed, chunks_created
    )
    return {"documents_processed": processed, "chunks_created": chunks_created}
