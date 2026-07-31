"""知识库路由 /api/knowledge-bases/* 测试（两级权限：admin 写 / 用户读+订阅）"""
from tests.util import biz_code, unwrap


async def _create_kb(admin_client, name="健身知识库"):
    return unwrap(
        await admin_client.post(
            "/api/knowledge-bases", json={"name": name, "description": "测试知识库"}
        )
    )


async def test_admin_create_kb(admin_client):
    data = await _create_kb(admin_client)
    assert data["name"] == "健身知识库"
    assert data["visibility"] == "private"


async def test_user_cannot_create_kb(user_client):
    resp = await user_client.post("/api/knowledge-bases", json={"name": "x"})
    assert biz_code(resp) == 40300


async def test_list_and_get_kb(user_client, admin_client):
    kb = await _create_kb(admin_client)
    lst = unwrap(await user_client.get("/api/knowledge-bases"))
    assert any(k["id"] == kb["id"] for k in lst)
    got = unwrap(await user_client.get(f"/api/knowledge-bases/{kb['id']}"))
    assert got["id"] == kb["id"]


async def test_update_kb_permissions(user_client, admin_client):
    kb = await _create_kb(admin_client)
    updated = unwrap(
        await admin_client.put(f"/api/knowledge-bases/{kb['id']}", json={"name": "新名"})
    )
    assert updated["name"] == "新名"
    assert biz_code(await user_client.put(f"/api/knowledge-bases/{kb['id']}", json={"name": "y"})) == 40300


async def test_subscription_flow(user_client, admin_client, user):
    kb = await _create_kb(admin_client)
    kbid = kb["id"]

    # 订阅（幂等）
    unwrap(await user_client.post(f"/api/knowledge-bases/{kbid}/subscribe"))
    unwrap(await user_client.post(f"/api/knowledge-bases/{kbid}/subscribe"))

    subs = unwrap(await user_client.get("/api/knowledge-bases/subscriptions"))
    assert any(k["id"] == kbid for k in subs)

    # admin 查看订阅者
    subscribers = unwrap(await admin_client.get(f"/api/knowledge-bases/{kbid}/subscribers"))
    assert any(s["user_id"] == str(user.id) for s in subscribers)

    # 取消订阅
    unwrap(await user_client.delete(f"/api/knowledge-bases/{kbid}/subscribe"))
    subs_after = unwrap(await user_client.get("/api/knowledge-bases/subscriptions"))
    assert not any(k["id"] == kbid for k in subs_after)


async def test_remove_subscriber(user_client, admin_client, user):
    kb = await _create_kb(admin_client)
    kbid = kb["id"]
    unwrap(await user_client.post(f"/api/knowledge-bases/{kbid}/subscribe"))
    unwrap(await admin_client.delete(f"/api/knowledge-bases/{kbid}/subscribers/{user.id}"))
    subs = unwrap(await user_client.get("/api/knowledge-bases/subscriptions"))
    assert not any(k["id"] == kbid for k in subs)


async def test_public_share_read(admin_client, client):
    kb = await _create_kb(admin_client)
    kbid = kb["id"]
    unwrap(
        await admin_client.post(
            f"/api/knowledge-bases/{kbid}/share",
            json={"visibility": "public", "public_slug": "fitkb"},
        )
    )
    # 公开端点无需认证
    data = unwrap(await client.get("/api/knowledge-bases/public/fitkb"))
    assert data["id"] == kbid


async def test_document_crud(user_client, admin_client):
    kb = await _create_kb(admin_client)
    kbid = kb["id"]

    doc = unwrap(
        await admin_client.post(
            f"/api/knowledge-bases/{kbid}/documents",
            json={
                "title": "深蹲指南",
                "filename": "squat.md",
                "content": "# 深蹲\n深蹲是一项基础力量训练动作。",
            },
        )
    )
    doc_id = doc["id"]

    # 用户可读
    lst = unwrap(await user_client.get(f"/api/knowledge-bases/{kbid}/documents"))
    assert any(d["id"] == doc_id for d in lst)

    content = unwrap(
        await user_client.get(f"/api/knowledge-bases/{kbid}/documents/{doc_id}/content")
    )
    assert "深蹲" in content["content"]

    # 用户不可写
    assert biz_code(
        await user_client.post(
            f"/api/knowledge-bases/{kbid}/documents",
            json={"title": "t", "filename": "f.md"},
        )
    ) == 40300

    # admin 更新内容（乐观锁 version）
    updated = unwrap(
        await admin_client.put(
            f"/api/knowledge-bases/{kbid}/documents/{doc_id}/content",
            json={"content": "# 深蹲 v2\n更新后的内容。", "version": doc["version"]},
        )
    )
    assert updated["version"] == doc["version"] + 1

    # admin 更新元数据
    patched = unwrap(
        await admin_client.patch(
            f"/api/knowledge-bases/{kbid}/documents/{doc_id}",
            json={"tags": ["力量", "腿部"]},
        )
    )
    assert patched["tags"] == ["力量", "腿部"]

    # admin 删除
    unwrap(await admin_client.delete(f"/api/knowledge-bases/{kbid}/documents/{doc_id}"))


async def test_search_documents(user_client, admin_client):
    kb = await _create_kb(admin_client)
    kbid = kb["id"]
    unwrap(
        await admin_client.post(
            f"/api/knowledge-bases/{kbid}/documents",
            json={
                "title": "硬拉指南",
                "filename": "deadlift.md",
                "content": "硬拉是三大力量举动作之一，锻炼后链肌群。",
            },
        )
    )
    results = unwrap(
        await user_client.get(
            f"/api/knowledge-bases/{kbid}/search", params={"query": "硬拉"}
        )
    )
    assert isinstance(results, list)


async def test_kb_tokens(user_client, admin_client):
    kb = await _create_kb(admin_client)
    kbid = kb["id"]

    created = unwrap(
        await admin_client.post(f"/api/knowledge-bases/{kbid}/tokens", json={"name": "ci"})
    )
    assert created["token"]
    token_id = created["token_out"]["id"]

    # 普通用户不可管理令牌
    assert biz_code(await user_client.get(f"/api/knowledge-bases/{kbid}/tokens")) == 40300

    tokens = unwrap(await admin_client.get(f"/api/knowledge-bases/{kbid}/tokens"))
    assert any(t["id"] == token_id for t in tokens)

    unwrap(await admin_client.delete(f"/api/knowledge-bases/{kbid}/tokens/{token_id}"))


async def test_admin_maintenance_endpoints(admin_client):
    kb = await _create_kb(admin_client)
    kbid = kb["id"]
    unwrap(await admin_client.post(f"/api/knowledge-bases/{kbid}/reindex"))
    unwrap(await admin_client.post(f"/api/knowledge-bases/{kbid}/rebuild-graph"))
    unwrap(await admin_client.get(f"/api/knowledge-bases/{kbid}/lint"))
    unwrap(await admin_client.get(f"/api/knowledge-bases/{kbid}/graph"))


async def test_delete_kb(admin_client, user_client):
    kb = await _create_kb(admin_client)
    kbid = kb["id"]
    assert biz_code(await user_client.delete(f"/api/knowledge-bases/{kbid}")) == 40300
    unwrap(await admin_client.delete(f"/api/knowledge-bases/{kbid}"))
    assert biz_code(await admin_client.get(f"/api/knowledge-bases/{kbid}")) != 0
