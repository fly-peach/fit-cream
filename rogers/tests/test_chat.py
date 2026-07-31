"""对话路由 /api/chat/* 测试（线程管理 + 图片上传；SSE 对话依赖 Agent，不在此测试）"""
import base64

from src.agents.models.conversation import Conversation
from tests.util import auth_headers, biz_code, create_user, unwrap

PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
PNG_BYTES = base64.b64decode(PNG_B64)


async def _seed_thread(db_session, user, thread_id="t1"):
    db_session.add_all(
        [
            Conversation(user_id=user.id, thread_id=thread_id, role="user", content="你好"),
            Conversation(
                user_id=user.id, thread_id=thread_id, role="assistant", content="你好！有什么可以帮你？"
            ),
        ]
    )
    await db_session.commit()


async def test_list_threads(user_client, db_session, user):
    await _seed_thread(db_session, user)
    data = unwrap(await user_client.get("/api/chat/threads"))
    assert len(data) == 1
    assert data[0]["thread_id"] == "t1"
    assert data[0]["message_count"] == 2


async def test_get_thread_messages(user_client, db_session, user):
    await _seed_thread(db_session, user)
    data = unwrap(await user_client.get("/api/chat/threads/t1/messages"))
    assert data["total"] == 2
    assert len(data["messages"]) == 2


async def test_update_thread_title(user_client, db_session, user):
    await _seed_thread(db_session, user)
    updated = unwrap(
        await user_client.patch("/api/chat/threads/t1/title", json={"title": "我的对话"})
    )
    assert updated["title"] == "我的对话"
    threads = unwrap(await user_client.get("/api/chat/threads"))
    assert threads[0]["title"] == "我的对话"


async def test_update_title_unknown_thread(user_client):
    resp = await user_client.patch("/api/chat/threads/nope/title", json={"title": "x"})
    assert biz_code(resp) == 404


async def test_delete_thread(user_client, db_session, user):
    await _seed_thread(db_session, user)
    unwrap(await user_client.delete("/api/chat/threads/t1"))
    threads = unwrap(await user_client.get("/api/chat/threads"))
    assert threads == []


async def test_clear_history(user_client, db_session, user):
    await _seed_thread(db_session, user, "t1")
    await _seed_thread(db_session, user, "t2")
    unwrap(await user_client.delete("/api/chat/history"))
    threads = unwrap(await user_client.get("/api/chat/threads"))
    assert threads == []


async def test_thread_isolation_between_users(user_client, db_session, user):
    await _seed_thread(db_session, user, "t1")
    other = await create_user(db_session, phone="13700000005", name="其他用户")

    threads = unwrap(
        await user_client.get("/api/chat/threads", headers=auth_headers(other))
    )
    assert threads == []

    msgs = unwrap(
        await user_client.get("/api/chat/threads/t1/messages", headers=auth_headers(other))
    )
    assert msgs["total"] == 0


async def test_upload_image_base64_fallback(user_client):
    data = unwrap(
        await user_client.post(
            "/api/chat/upload-image", files={"file": ("test.png", PNG_BYTES, "image/png")}
        )
    )
    assert data["url"].startswith("data:image/png;base64,")
    assert data["mime_type"] == "image/png"


async def test_upload_image_invalid_type(user_client):
    resp = await user_client.post(
        "/api/chat/upload-image", files={"file": ("note.txt", b"hello", "text/plain")}
    )
    assert biz_code(resp) == 400


async def test_stop_unknown_thread(user_client):
    resp = await user_client.post("/api/chat/stop", json={"thread_id": "nope"})
    assert biz_code(resp) == 404
