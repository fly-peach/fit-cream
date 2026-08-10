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

from src.knowledge_base.models.document import KBDocument
from src.knowledge_base.models.reference import KBReference
from src.knowledge_base.references import build_lookup_maps, extract_references

logger = logging.getLogger("fitcream")


def _doc_path(doc: KBDocument) -> str:
    return f"{doc.path}{doc.filename}"


# 语义着色分组：按 tags 关键词归 5 大类，无法归类回退"其他"
_GROUP_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("训练动作", ("动作", "训练", "exercise", "workout", "力量", "有氧", "hiit")),
    ("饮食营养", ("饮食", "营养", "蛋白", "碳水", "热量", "diet", "nutrition", "食谱")),
    ("康复拉伸", ("康复", "拉伸", "放松", "按摩", "rehab", "stretch", "损伤")),
    ("装备选购", ("装备", "器械", "器材", "选购", "gear", "equipment", "购买")),
    ("计划", ("计划", "program", "plan", "方案", "周期")),
]


def _semantic_group(tags: list[str]) -> str:
    """按 tags 归语义分组（训练动作/饮食营养/康复拉伸/装备选购/计划）。"""
    tag_text = " | ".join(tags or []).lower()
    for group, keywords in _GROUP_RULES:
        if any(kw in tag_text for kw in keywords):
            return group
    return "其他"


async def _load_docs(db: AsyncSession, kb_id: UUID) -> tuple[list[KBDocument], dict, dict, dict]:
    """加载知识库全部文档 + 构建引用查找映射。"""
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
        }
        for d in all_docs
    ]
    filename_map, base_map, wiki_map = build_lookup_maps(doc_dicts)
    return all_docs, filename_map, base_map, wiki_map


async def reindex_document_references(
    db: AsyncSession,
    doc: KBDocument,
    kb_id: UUID,
    filename_map: dict,
    base_map: dict,
    wiki_map: dict,
) -> dict:
    """增量重建单文档的出边（DELETE 旧边 + 重提取，同事务）。

    仅 wiki 页面会产生引用边；raw 文档仅清空其出边。返回 {"citations", "links", "errors"}。
    """
    await db.execute(
        delete(KBReference).where(KBReference.source_document_id == doc.id)
    )
    await db.flush()

    if not (doc.path.startswith("/wiki/") and (doc.content or "")):
        return {"citations": 0, "links": 0, "errors": 0}

    wiki_dir = doc.path.replace("/wiki/", "", 1) if doc.path.startswith("/wiki/") else ""
    try:
        edges = extract_references(
            doc.content or "", str(doc.id), wiki_dir, filename_map, base_map, wiki_map
        )
    except Exception:
        return {"citations": 0, "links": 0, "errors": 1}

    cites = 0
    links = 0
    for edge in edges:
        ref = KBReference(
            source_document_id=doc.id,
            target_document_id=edge["target_id"],
            kb_id=kb_id,
            reference_type=edge["type"],
            page=edge.get("page"),
        )
        db.add(ref)
        if edge["type"] == "cites":
            cites += 1
        else:
            links += 1
    await db.flush()
    return {"citations": cites, "links": links, "errors": 0}


async def rebuild_graph(db: AsyncSession, kb_id: UUID) -> dict:
    """全量重建知识图谱（原子操作）。

    流程: 获取所有文档 -> 构建 3 层查找映射 -> 只扫描 wiki 页面
          (path 以 /wiki/ 开头) -> 解析引用
          -> 原子 DELETE 旧边 + INSERT 新边（单事务，失败 rollback）
    返回: {"citations": N, "links": N, "errors": N}
    """
    all_docs, filename_map, base_map, wiki_map = await _load_docs(db, kb_id)

    await db.execute(delete(KBReference).where(KBReference.kb_id == kb_id))
    await db.flush()

    total_cites = 0
    total_links = 0
    errors = 0

    for page in all_docs:
        if not page.path.startswith("/wiki/"):
            continue
        res = await reindex_document_references(
            db, page, kb_id, filename_map, base_map, wiki_map
        )
        total_cites += res["citations"]
        total_links += res["links"]
        errors += res["errors"]

    await db.flush()
    logger.info(
        "重建图谱 KB %s: %d cites, %d links", str(kb_id)[:8], total_cites, total_links
    )
    return {"citations": total_cites, "links": total_links, "errors": errors}


async def get_graph(
    db: AsyncSession,
    kb_id: UUID,
    mode: str = "full",
    overview_threshold: int = 200,
    overview_limit: int = 300,
) -> dict:
    """返回 {nodes, edges, stats} 供可视化。

    mode:
      - full: 返回全部节点/边
      - overview: 节点数达到 overview_threshold 时，按节点度数降序取前 overview_limit 个
        （边仅保留两端均在选定节点内的）；未达阈值时等价于 full。
    节点含 stale / uncited / degree / semantic_group 供前端着色与降采样。
    """
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
    refs = [
        r for r in refs
        if str(r.source_document_id) in doc_ids and str(r.target_document_id) in doc_ids
    ]

    # 度数统计（出入度合计）
    degree: dict[str, int] = {}
    for r in refs:
        degree[str(r.source_document_id)] = degree.get(str(r.source_document_id), 0) + 1
        degree[str(r.target_document_id)] = degree.get(str(r.target_document_id), 0) + 1

    # 被 cites 引用集合（用于 uncited 标记）
    cited_ids = {
        str(r.target_document_id)
        for r in refs
        if r.reference_type == "cites"
    }

    nodes = [
        {
            "id": str(d.id),
            "title": d.title or d.filename,
            "path": _doc_path(d),
            "tags": d.tags or [],
            "stale_since": d.stale_since.isoformat() if d.stale_since else None,
            "uncited": str(d.id) not in cited_ids,
            "degree": degree.get(str(d.id), 0),
            "semantic_group": _semantic_group(d.tags or []),
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
    ]

    # overview 降采样
    show_nodes = nodes
    show_edges = edges
    if mode == "overview" and len(nodes) >= overview_threshold:
        top = sorted(nodes, key=lambda x: x["degree"], reverse=True)[:overview_limit]
        top_ids = {n["id"] for n in top}
        show_nodes = top
        show_edges = [
            e for e in edges
            if e["source"] in top_ids and e["target"] in top_ids
        ]

    return {
        "nodes": show_nodes,
        "edges": show_edges,
        "stats": {
            "documents": len(docs),
            "references": len(refs),
            "citations": sum(1 for e in refs if e.reference_type == "cites"),
            "links": sum(1 for e in refs if e.reference_type == "links_to"),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "mode": mode,
            "downsampled": mode == "overview" and len(show_nodes) != len(nodes),
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
            "document_id": str(r.source_document_id),
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
            "document_id": str(r.target_document_id),
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
    return [{"path": d.path, "filename": d.filename} for d in docs]


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
