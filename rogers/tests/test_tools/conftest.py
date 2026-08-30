"""
工具层集成测试基础设施（tests/test_tools/conftest.py）

复用 tests/conftest.py 的 fitcream_test schema 与 admin 夹具，把 Agent 工具的
数据库会话重定向到测试 schema：

- 工具统一走 _common.session_scope() -> _common.async_session_factory
  （`from app.database import async_session_factory` 的模块级绑定），
  故须 monkeypatch _common.async_session_factory，而不是 app.database 的同名对象。
- KB 搜索/部分服务会自行 `app.database.async_session_factory()` 开新会话，
  一并 patch 到测试会话工厂，保证整条链路都落在测试 schema。

agent_config：构造携带管理员 user_id 的 RunnableConfig，供工具直接 ainvoke。
"""
import pytest
from langchain_core.runnables import RunnableConfig

import app.database as app_db
import src.agents.harness.tools._common as tools_common
from tests.conftest import test_session_factory


@pytest.fixture(autouse=True)
def _tools_use_test_schema(monkeypatch):
    """工具链路的所有会话工厂指向测试 schema（autouse，作用于本目录全部测试）。"""
    monkeypatch.setattr(tools_common, "async_session_factory", test_session_factory)
    monkeypatch.setattr(app_db, "async_session_factory", test_session_factory)
    yield


@pytest.fixture
def agent_config(admin) -> RunnableConfig:
    """管理员身份的工具调用配置（configurable.user_id 即工具的身份来源）。"""
    return RunnableConfig(configurable={"user_id": str(admin.id)})


@pytest.fixture
def kb_enabled_config(admin) -> RunnableConfig:
    """开启「知识库回答」开关的管理员配置（search_knowledge_base 等工具的前置）。"""
    return RunnableConfig(configurable={"user_id": str(admin.id), "kb_enabled": True})
