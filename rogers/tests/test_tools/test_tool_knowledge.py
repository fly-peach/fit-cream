"""
知识库工具测试（管理员账户）

覆盖：list_my_knowledge_bases / search_knowledge_base / read_kb_document。
知识库由管理员通过 HTTP 路由创建（复用现有测试的 admin_client 种子方式），
随后直接调用工具验证检索链路与权限开关。
"""
from tests.util import unwrap

from src.agents.harness.tools.knowledge.knowledge_tools import (
    list_my_knowledge_bases,
    read_kb_document,
    search_knowledge_base,
)


async def _seed_kb_with_doc(admin_client, title="深蹲指南", content=None, name="健身知识库"):
    if content is None:
        content = (
            "深蹲是一项基础力量训练动作，主要锻炼股四头肌、臀大肌与核心肌群。"
            "动作要点：双脚与肩同宽站立，脚尖微微外展，保持背部挺直，"
            "下蹲时膝盖与脚尖方向一致，下蹲到大腿平行地面后起身。"
            "深蹲对提升下肢力量、改善髋膝踝灵活性与日常生活活动能力都有显著帮助，"
            "建议从自重深蹲开始，逐步增加负重。"
        )
    kb = unwrap(
        await admin_client.post("/api/knowledge-bases", json={"name": name, "description": "测试知识库"})
    )
    kbid = kb["id"]
    doc = unwrap(
        await admin_client.post(
            f"/api/knowledge-bases/{kbid}/documents",
            json={"title": title, "filename": "doc.md", "content": content},
        )
    )
    unwrap(await admin_client.post(f"/api/knowledge-bases/{kbid}/rebuild-lint"))
    return kbid, doc["id"]


async def test_list_my_knowledge_bases(admin_client, kb_enabled_config):
    await _seed_kb_with_doc(admin_client)
    res = await list_my_knowledge_bases.ainvoke({}, config=kb_enabled_config)
    assert res["success"] is True
    assert res["total"] >= 1
    assert any(kb["is_owner"] for kb in res["knowledge_bases"])


async def test_list_my_knowledge_bases_empty(kb_enabled_config):
    res = await list_my_knowledge_bases.ainvoke({}, config=kb_enabled_config)
    assert res["success"] is True
    assert res["total"] == 0


async def test_search_knowledge_base(admin_client, kb_enabled_config):
    kbid, doc_id = await _seed_kb_with_doc(admin_client)
    res = await search_knowledge_base.ainvoke(
        {"query": "深蹲", "kb_id": kbid, "limit": 5},
        config=kb_enabled_config,
    )
    assert res["success"] is True, res
    assert res["total"] >= 1, res
    assert any("深蹲" in (r["content"] or "") or "深蹲" in r["document_title"] for r in res["results"])


async def test_read_kb_document(admin_client, kb_enabled_config):
    kbid, doc_id = await _seed_kb_with_doc(admin_client)
    res = await read_kb_document.ainvoke(
        {"document_id": doc_id, "kb_id": kbid},
        config=kb_enabled_config,
    )
    assert res["success"] is True, res
    assert res["document"]["title"] == "深蹲指南"
    assert "深蹲" in res["document"]["content"]
    assert res["document"]["url"].startswith("/knowledge-bases/")


async def test_kb_disabled_without_switch(agent_config):
    """未开启「知识库回答」开关时，工具应返回明确的禁用提示（防绕过兜底）。"""
    res = await search_knowledge_base.ainvoke({"query": "深蹲"}, config=agent_config)
    assert res["success"] is False
    assert "知识库回答未开启" in res["error"]


async def test_read_kb_document_not_found(kb_enabled_config):
    import uuid

    res = await read_kb_document.ainvoke(
        {"document_id": str(uuid.uuid4())},
        config=kb_enabled_config,
    )
    assert res["success"] is False
