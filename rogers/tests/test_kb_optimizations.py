"""知识库优化（FR-1/FR-3）测试：RRF 融合、索引状态、增量更新。

语义向量在测试环境被关闭（conftest KB_EMBEDDING_ENABLED=false），search_documents
退化为纯全文；此处验证融合逻辑为纯函数单测 + 索引可观测性/增量行为。
"""
from tests.util import unwrap

from src.knowledge_base.services.search_service import KBSearchService


def test_rrf_fuse_merges_and_dedupes():
    """RRF 融合：两路结果按 chunk_id 去重合并，命中两路的排前。"""
    fulltext = [
        {"chunk_id": "a", "content": "a"},
        {"chunk_id": "b", "content": "b"},
        {"chunk_id": "c", "content": "c"},
    ]
    semantic = [
        {"chunk_id": "b", "content": "b"},
        {"chunk_id": "d", "content": "d"},
        {"chunk_id": "e", "content": "e"},
    ]
    fused = KBSearchService._rrf_fuse(fulltext, semantic, limit=10)
    ids = [f["chunk_id"] for f in fused]
    # 去重
    assert len(ids) == len(set(ids))
    # 命中两路的 b 应排最前（RRF 分数最高）
    assert ids[0] == "b"
    # 仅一路的按序保留
    assert set(ids) == {"a", "b", "c", "d", "e"}


def test_rrf_fuse_respects_limit():
    fulltext = [{"chunk_id": f"f{i}", "content": str(i)} for i in range(5)]
    semantic = [{"chunk_id": f"s{i}", "content": str(i)} for i in range(5)]
    fused = KBSearchService._rrf_fuse(fulltext, semantic, limit=3)
    assert len(fused) == 3


async def _create_doc(admin_client, kb_id, title, filename, content):
    return unwrap(
        await admin_client.post(
            f"/api/knowledge-bases/{kb_id}/documents",
            json={"title": title, "filename": filename, "content": content},
        )
    )


async def test_index_status_fields(admin_client):
    kb = unwrap(
        await admin_client.post(
            "/api/knowledge-bases", json={"name": "状态库"}
        )
    )
    kb_id = kb["id"]
    await _create_doc(
        admin_client, kb_id, "文档A", "a.md", "# A\n内容 A 内容。"
    )
    # 写文档后为 pending，重建后 indexed
    before = unwrap(await admin_client.get(f"/api/knowledge-bases/{kb_id}/index-status"))
    assert before["pending_documents"] == 1
    assert before["indexed_documents"] == 0

    unwrap(await admin_client.post(f"/api/knowledge-bases/{kb_id}/rebuild-lint"))
    status = unwrap(await admin_client.get(f"/api/knowledge-bases/{kb_id}/index-status"))
    assert status["kb_id"] == kb_id
    assert status["total_documents"] == 1
    assert status["indexed_documents"] == 1
    assert status["pending_documents"] == 0
    assert status["chunks_total"] >= 1
    assert status["last_indexed_at"] is not None
    assert "chunks_pending_embedding" in status


async def test_update_marks_pending_then_rebuild(admin_client):
    kb = unwrap(
        await admin_client.post(
            "/api/knowledge-bases", json={"name": "增量库"}
        )
    )
    kb_id = kb["id"]
    doc_a = await _create_doc(admin_client, kb_id, "文档A", "a.md", "# A\n内容 A。")
    doc_b = await _create_doc(admin_client, kb_id, "文档B", "b.md", "# B\n内容 B。")

    # 更新文档 A -> 置 pending（last_indexed_at 清空），不触发索引
    updated = unwrap(
        await admin_client.put(
            f"/api/knowledge-bases/{kb_id}/documents/{doc_a['id']}/content",
            json={"content": "# A v2\n更新后的内容 A。", "version": doc_a["version"]},
        )
    )
    assert updated["status"] == "pending"
    assert updated["last_indexed_at"] is None
    assert updated["version"] == doc_a["version"] + 1

    # 重建后全部 indexed，文档 B 内容不变
    unwrap(await admin_client.post(f"/api/knowledge-bases/{kb_id}/rebuild-lint"))
    refresh_b = unwrap(
        await admin_client.get(
            f"/api/knowledge-bases/{kb_id}/documents/{doc_b['id']}"
        )
    )
    assert refresh_b["last_indexed_at"] is not None


async def test_search_still_returns_list_when_semantic_disabled(admin_client, user_client):
    kb = unwrap(
        await admin_client.post(
            "/api/knowledge-bases", json={"name": "搜索库"}
        )
    )
    kb_id = kb["id"]
    await _create_doc(
        admin_client, kb_id, "硬拉指南", "deadlift.md", "硬拉锻炼后链肌群。"
    )
    # 索引前不可搜，重建后可搜
    empty = unwrap(
        await user_client.get(
            f"/api/knowledge-bases/{kb_id}/search", params={"query": "硬拉"}
        )
    )
    assert isinstance(empty, list) and len(empty) == 0

    unwrap(await admin_client.post(f"/api/knowledge-bases/{kb_id}/rebuild-lint"))
    results = unwrap(
        await user_client.get(
            f"/api/knowledge-bases/{kb_id}/search", params={"query": "硬拉"}
        )
    )
    assert isinstance(results, list)
    assert all({"chunk_id", "document_id", "content"} <= set(r) for r in results)