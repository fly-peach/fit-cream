"""
记忆工具测试（管理员账户）

记忆子系统使用独立 MemoryBase（不走 app Base），测试时把全局 MemoryStore 单例
替换为绑定 fitcream_test schema 的实例，并用离线假 embedding 替换 DashScope，
保证不触发任何网络调用即可完成读写检索。
"""
import hashlib
import re

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from tests.conftest import TEST_SEARCH_PATH


class _FakeEmbed:
    """离线确定性 embedding：按文本哈希生成 1024 维向量，避免真实 API 调用。"""

    def __init__(self, dim: int):
        self.dim = dim

    async def aget_text_embedding(self, text: str):
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [((h[i % 32] * 31 + i) % 255) / 255.0 for i in range(self.dim)]


@pytest.fixture
async def memory_store(monkeypatch):
    from tests.conftest import test_session_factory

    from src.agents.harness.runtime.memory.embeddings import get_embedding_dimension
    from src.agents.harness.runtime.memory import store as store_mod
    from src.agents.harness.runtime.memory.store import MemoryStore
    from src.agents.harness.tools.memory import memory_tools as mem_tools
    from src.agents.models.memory import MemoryBase

    store = MemoryStore(
        database_url=settings.DATABASE_URL,
        embed_model=_FakeEmbed(get_embedding_dimension()),
    )
    # 重定向到测试 schema：MemoryStore 构造不接收 connect_args，这里整体替换引擎
    store.engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args={"server_settings": {"search_path": TEST_SEARCH_PATH}},
    )
    store.async_session = async_sessionmaker(
        store.engine, class_=AsyncSession, expire_on_commit=False
    )
    store._vector_store = None

    async def _setup():
        async with store.engine.begin() as conn:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception:
                pass
            await conn.run_sync(MemoryBase.metadata.create_all)

    await _setup()

    monkeypatch.setattr(store_mod, "_memory_store", store)
    monkeypatch.setattr(store_mod, "get_memory_store", lambda: store)
    # _db_profile_facts 直连 app.database.async_session_factory（模块级绑定），同步重定向
    monkeypatch.setattr(mem_tools, "async_session_factory", test_session_factory)
    yield store

    async def _cleanup():
        async with store.engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE TABLE episodic_memories, semantic_memories,"
                    " procedural_memories, memory_consolidation_logs"
                    " RESTART IDENTITY CASCADE"
                )
            )

    await _cleanup()
    await store.close()


async def test_save_preference_and_list(memory_store, agent_config):
    from src.agents.harness.tools.memory.memory_tools import list_user_profile, save_preference

    res = await save_preference.ainvoke({"preference": "运动时间", "value": "晨跑"}, config=agent_config)
    assert "已保存" in res

    dup = await save_preference.ainvoke({"preference": "运动时间", "value": "晨跑"}, config=agent_config)
    assert "已记录" in dup

    profile = await list_user_profile.ainvoke({}, config=agent_config)
    assert "运动时间" in profile and "晨跑" in profile


async def test_save_user_fact_and_recall(memory_store, agent_config):
    from src.agents.harness.tools.memory.memory_tools import recall_memory, save_user_fact

    res = await save_user_fact.ainvoke(
        {"subject": "用户", "fact": "膝盖有旧伤", "category": "fact", "predicate": "状况"},
        config=agent_config,
    )
    assert "已保存" in res

    recalled = await recall_memory.ainvoke({"query": "膝盖", "memory_type": "semantic"}, config=agent_config)
    assert "膝盖有旧伤" in recalled


async def test_save_event_episodic(memory_store, agent_config):
    from src.agents.harness.tools.memory.memory_tools import recall_memory, save_event

    res = await save_event.ainvoke({"event": "今天完成第一次 5 公里跑步", "importance": 0.8}, config=agent_config)
    assert "已记录事件" in res

    recalled = await recall_memory.ainvoke({"query": "跑步", "memory_type": "episodic"}, config=agent_config)
    assert "5 公里跑步" in recalled


async def test_update_and_delete_memory(memory_store, agent_config):
    from src.agents.harness.tools.memory.memory_tools import (
        delete_memory,
        list_user_profile,
        recall_memory,
        save_preference,
        update_memory,
    )

    await save_preference.ainvoke({"preference": "饮食偏好", "value": "不吃辣"}, config=agent_config)
    recalled = await recall_memory.ainvoke({"query": "饮食", "memory_type": "semantic"}, config=agent_config)
    m = re.search(r"id:([0-9a-fA-F-]+)", recalled)
    assert m, recalled
    memory_id = m.group(1)

    updated = await update_memory.ainvoke({"memory_id": memory_id, "new_value": "少油清淡"}, config=agent_config)
    assert "已更新" in updated

    profile = await list_user_profile.ainvoke({}, config=agent_config)
    assert "少油清淡" in profile
    assert "不吃辣" not in profile

    deleted = await delete_memory.ainvoke({"memory_id": memory_id}, config=agent_config)
    assert "已删除" in deleted

    profile = await list_user_profile.ainvoke({}, config=agent_config)
    assert "暂无存储的用户信息" in profile


async def test_memory_cross_user_isolation(memory_store, db_session, agent_config, admin):
    """A 用户保存的记忆，B 用户不得检索到（身份来自 config，杜绝跨用户读写）。"""
    from src.agents.harness.tools.memory.memory_tools import (
        list_user_profile,
        save_preference,
    )
    from tests.util import create_user

    await save_preference.ainvoke({"preference": "训练时间", "value": "晚上"}, config=agent_config)

    other = await create_user(db_session, phone="13900000099", name="其他管理员", role="admin")
    from langchain_core.runnables import RunnableConfig

    other_config = RunnableConfig(configurable={"user_id": str(other.id)})
    other_profile = await list_user_profile.ainvoke({}, config=other_config)
    assert "暂无存储的用户信息" in other_profile
