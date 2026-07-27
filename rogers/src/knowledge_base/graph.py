"""
知识图谱编排（DB 编排层）

参考 LLM Wiki api/services/graph.py：
- rebuild_graph: 全量重建引用边（只扫 wiki 页面，事务内 DELETE+INSERT 原子）
- get_graph: 返回 {nodes, edges} 供可视化
- propagate_staleness: 文档更新后给引用方打 stale_since
- get_backlinks / get_forward_references: 入边/出边查询
- find_uncited_sources / find_stale_pages: 供 lint 调用
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge_base.models import KBDocument, KBReference
from src.knowledge_base.references import build_lookup_maps, extract_references

logger = logging.getLogger("fitcream")


def _doc_path(doc: KBDocument) -> str:
    return f"{doc.path}{doc.filename}"


async def rebuild_graph(db: AsyncSession, kb_id: UUID) -> dict:
    """全量重建知识图谱（原子操作）。

    流程: 获取所有文档 -> 构建 3 层查找映射 -> 只扫描 wiki 页面
          (path LIKE '/wiki/%' AND file_type='md') -> 解析引用
          -> 原子 DELETE 旧边 + INSERT 新边（单事务，失败 rollback）
    返回: {"citations": N, "links": N, "errors": N}
    """
    result = await db.execute(
        select(KBDocument).where(
            KBDocument.kb_id == kb_id, KBDocument.archived == False  # noqa: E712
        )
    )
    all_docs = list(result.scalars().all())

    doc_dicts = [
        {
            "id": str(d.id),
            "filename": d.filename,
            "title": d.title,
            "path": d.path,
            "file_type": d.file_type,
        }
        for d in all_docs
    ]
    filename_map, base_map, wiki_map = build_lookup_maps(doc_dicts)

    wiki_pages = [d for d in all_docs if d.path.startswith("/wiki/") and d.file_type == "md" and (d.content or "")]

    await db.execute(delete(KBReference).where(KBReference.kb_id == kb_id))
    await db.flush()

    total_cites = 0
    total_links = 0
    errors = 0
    doc_by_id = {str(d.id): d for d in all_docs}

    for page in wiki_pages:
        content = page.content or ""
        if not content:
            continue
        wiki_dir = page.path.replace("/wiki/", "", 1) if page.path.startswith("/wiki/") else ""
        try:
            edges = extract_references(
                content, str(page.id), wiki_dir, filename_map, base_map, wiki_map
            )
        except Exception:
            errors += 1
            continue

        for edge in edges:
            target = doc_by_id.get(edge["target_id"])
            if not target:
                continue
            ref = KBReference(
                source_document_id=page.id,
                target_document_id=target.id,
                kb_id=kb_id,
                reference_type=edge["type"],
                page=edge.get("page"),
            )
            db.add(ref)
            if edge["type"] == "cites":
                total_cites += 1
            else:
                total_links += 1

    await db.flush()
    logger.info(
        "重建图谱 KB %s: %d cites, %d links", str(kb_id)[:8], total_cites, total_links
    )
    return {"citations": total_cites, "links": total_links, "errors": errors}


async def get_graph(db: AsyncSession, kb_id: UUID) -> dict:
    """返回 {nodes, edges, stats} 供可视化"""
    doc_result = await db.execute(
        select(KBDocument).where(
            KBDocument.kb_id == kb_id,
            KBDocument.archived == False,  # noqa: E712
            KBDocument.status != "failed",
        )
    )
    docs = list(doc_result.scalars().all())

    ref_result = await db.execute(
        select(KBReference).where(KBReference.kb_id == kb_id)
    )
    refs = list(ref_result.scalars().all())

    doc_ids = {str(d.id) for d in docs}

    nodes = [
        {
            "id": str(d.id),
            "title": d.title or d.filename,
            "path": _doc_path(d),
            "file_type": d.file_type,
            "source_kind": "wiki" if d.path.startswith("/wiki/") else "raw",
            "tags": d.tags or [],
        }
        for d in docs
    ]
    edges = [
        {
            "source": str(r.source_document_id),
            "target": str(r.target_document_id),
            "type": r.reference_type,
            "page": r.page,
        }
        for r in refs
        if str(r.source_document_id) in doc_ids and str(r.target_document_id) in doc_ids
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "documents": len(docs),
            "references": len(edges),
            "citations": sum(1 for e in edges if e["type"] == "cites"),
            "links": sum(1 for e in edges if e["type"] == "links_to"),
        },
    }


async def propagate_staleness(db: AsyncSession, doc_id: UUID) -> int:
    """文档更新后，把引用它的 wiki 页标记为过期（参考 VaultFS.propagate_staleness）。

    返回被标记的页数。
    """
    result = await db.execute(
        update(KBDocument)
        .where(
            KBDocument.id.in_(
                select(KBReference.source_document_id).where(
                    KBReference.target_document_id == doc_id,
                    KBReference.reference_type == "links_to",
                )
            ),
            KBDocument.archived == False,  # noqa: E712
        )
        .values(stale_since=datetime.now(timezone.utc))
    )
    await db.flush()
    return result.rowcount or 0


async def get_backlinks(db: AsyncSession, doc_id: UUID) -> list[dict]:
    """入边：谁引用了我（cites + links_to）"""
    result = await db.execute(
        select(KBReference, KBDocument)
        .join(KBDocument, KBReference.source_document_id == KBDocument.id)
        .where(KBReference.target_document_id == doc_id)
    )
    rows = result.all()
    return [
        {
            "id": str(r.id),
            "reference_type": r.reference_type,
            "page": r.page,
            "path": _doc_path(d),
            "filename": d.filename,
            "title": d.title,
        }
        for r, d in rows
    ]


async def get_forward_references(db: AsyncSession, doc_id: UUID) -> list[dict]:
    """出边：我引用了谁（分 cites / links_to）"""
    result = await db.execute(
        select(KBReference, KBDocument)
        .join(KBDocument, KBReference.target_document_id == KBDocument.id)
        .where(KBReference.source_document_id == doc_id)
    )
    rows = result.all()
    return [
        {
            "id": str(r.id),
            "reference_type": r.reference_type,
            "page": r.page,
            "path": _doc_path(d),
            "filename": d.filename,
            "title": d.title,
        }
        for r, d in rows
    ]


async def find_uncited_sources(db: AsyncSession, kb_id: UUID) -> list[dict]:
    """未被任何 wiki 页引用的源文档（供 lint uncited-source）"""
    result = await db.execute(
        select(KBDocument)
        .where(
            KBDocument.kb_id == kb_id,
            KBDocument.archived == False,  # noqa: E712
            ~KBDocument.path.startswith("/wiki/"),
            ~KBDocument.id.in_(
                select(KBReference.target_document_id).where(
                    KBReference.kb_id == kb_id,
                    KBReference.reference_type == "cites",
                )
            ),
        )
    )
    docs = list(result.scalars().all())
    return [{"path": d.path, "filename": d.filename, "file_type": d.file_type} for d in docs]


async def find_stale_pages(db: AsyncSession, kb_id: UUID) -> list[dict]:
    """stale_since 非空的 wiki 页（供 lint stale-page）"""
    result = await db.execute(
        select(KBDocument).where(
            KBDocument.kb_id == kb_id,
            KBDocument.stale_since.is_not(None),
        )
    )
    docs = list(result.scalars().all())
    return [
        {
            "path": d.path,
            "filename": d.filename,
            "title": d.title,
            "stale_since": d.stale_since.isoformat() if d.stale_since else None,
        }
        for d in docs
    ]
