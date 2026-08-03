"""
工具层公共基础

消除三类重复/不一致：
- 身份提取写法不一（config.get("configurable", {}) 与 config["configurable"].get 两种）
- 错误被裸 str(e) 吞掉（丢失 BusinessException 的 code + 业务消息）
- 会话样板重复（每个 tool 手写 async_session_factory + commit/rollback）

所有 fitme / knowledge 工具统一复用此处助手。
memory 工具属独立 MemoryStore 子系统，不适用本模式（见方案 D2）。
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from app.database import async_session_factory
from utils.exceptions import BusinessException

logger = logging.getLogger("fitcream.tools")


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


# 工具失败时回传给 LLM 的统一指引：禁止用大模型编造结果，必须如实告知用户并引导重试
_FAIL_GUIDE = "请如实告知用户该操作未成功并建议重试，不要编造结果或假装已完成。"


def error_response(e: Exception) -> dict:
    """统一错误返回，保留 BusinessException 的 code + 业务消息。

    - 记录日志：业务异常（BusinessException）记 WARNING，未预期异常记 ERROR + 堆栈，
      避免工具失败被静默吞掉、Agent 日志误报成功。
    - 在返回中附带 message 指引 LLM：失败时不得编造结果，应告知用户并引导重试。
    """
    if isinstance(e, BusinessException):
        logger.warning("工具业务异常: %s (code=%s)", e.message, e.code)
        return {
            "success": False,
            "error": e.message,
            "error_code": e.code,
            "message": f"操作失败：{e.message}。{_FAIL_GUIDE}",
        }
    logger.error("工具执行失败: %s", e, exc_info=True)
    return {
        "success": False,
        "error": str(e),
        "message": f"工具调用失败：{e}。{_FAIL_GUIDE}",
    }


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
