"""
工具层公共基础

消除三类重复/不一致：
- 身份提取写法不一（config.get("configurable", {}) 与 config["configurable"].get 两种）
- 错误被裸 str(e) 吞掉（丢失 BusinessException 的 code + 业务消息）
- 会话样板重复（每个 tool 手写 async_session_factory + commit/rollback）

所有 fitme / knowledge 工具统一复用此处助手。
memory 工具属独立 MemoryStore 子系统，不适用本模式（见方案 D2）。
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from app.database import async_session_factory
from utils.exceptions import BusinessException


def extract_user_id(config: Optional[RunnableConfig]) -> Optional[UUID]:
    """从 RunnableConfig 统一提取用户身份。

    兼容两种历史写法（config.get("configurable", {}) 与 config["configurable"].get），
    并处理 config=None。user_id 可能为 str 或 UUID，统一归一为 UUID；无法解析返回 None。
    """
    if not config:
        return None

    configurable = config.get("configurable") if hasattr(config, "get") else None
    if not configurable:
        return None

    raw = configurable.get("user_id")
    if not raw:
        return None

    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return None


def error_response(e: Exception) -> dict:
    """统一错误返回，保留 BusinessException 的 code + 业务消息。"""
    if isinstance(e, BusinessException):
        return {"success": False, "error": e.message, "error_code": e.code}
    return {"success": False, "error": str(e)}


@asynccontextmanager
async def session_scope() -> AsyncIterator:
    """数据库会话上下文：正常退出 commit，异常 rollback 后重新抛出。

    用法（try/except 置于 session_scope 之外，使异常可触发 rollback）：
        try:
            async with session_scope() as db:
                ... 业务调用 ...
                return result
        except Exception as e:
            return error_response(e)
    """
    async with async_session_factory() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise
