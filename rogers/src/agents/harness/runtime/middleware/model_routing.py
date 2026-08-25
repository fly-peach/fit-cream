"""
模型路由中间件（ModelRoutingMiddleware）—— 按请求切换 qwen / 用户自备 DeepSeek

背景：LangChain 1.3 的 ``create_agent`` 把 model 烘焙进 graph，但中间件
``wrap_model_call`` / ``awrap_model_call`` 的 ``request.override(model=...)`` 可
每调用替换模型。因此单一共享 graph + 本中间件即可按请求路由，无需为每个用户
编译多份 graph。

路由规则（读取 ``RunnableConfig.configurable["deepseek_api_key"]``）：
- 有用户 DeepSeek key：``resolve_chat_model(user_ds_key=key)`` → 用 deepseek
  视觉模型（官方端点）覆盖本轮 model
- 无 key：不覆盖，保持 graph 默认 qwen 模型

失效回退（BYOK key 无效 / 中途 401/403）：
- 捕获认证类异常（401/403）：``mark_ds_key_invalid(key)`` 写入负缓存（后续请求
  直接回退 qwen），置「本轮已回退」ContextVar 标志（chat.py 据此发
  ``ds_key_invalid`` SSE 事件），并用 qwen model 重试一次。
- 日志一律脱敏：不打印 key 本体。

无实例级可变状态：并发 run 互不影响（模型实例与负缓存均在 model_factory 进程级
管理，key 从 configurable 每请求解析）。
"""

import logging
from contextvars import ContextVar
from typing import Optional

from langchain.agents.middleware import AgentMiddleware

from src.agents.harness.runtime.config_flags import get_config_value
from src.agents.harness.orchestration.model_factory import (
    mark_ds_key_invalid,
    resolve_chat_model,
)

logger = logging.getLogger("fitcream.agent")

# 「本轮已回退」标志：模型路由中间件在某请求内因 DS key 无效回退 qwen 时置位，
# chat.py 在流结束后读取并发 ds_key_invalid SSE 事件。
# 注意：中间件在 langgraph 的子任务上下文执行，ContextVar 不会回传调用方，
# 故以 thread_id 为键的进程级集合为主信号（每请求开头 reset，按线程隔离并发）。
_ds_fallback_flag: ContextVar[bool] = ContextVar(
    "fitcream_ds_key_fallback", default=False
)
_ds_fallback_threads: set[str] = set()


def ds_key_fallback_active(thread_id: Optional[str] = None) -> bool:
    """当前 run 是否发生过 DS key 无效回退（按 thread_id，缺失时回退 ContextVar）。"""
    if thread_id and thread_id in _ds_fallback_threads:
        return True
    return _ds_fallback_flag.get()


def reset_ds_key_fallback(thread_id: Optional[str] = None) -> None:
    """重置回退标志（chat.py 每个请求开始时调用）。"""
    _ds_fallback_flag.set(False)
    if thread_id:
        _ds_fallback_threads.discard(thread_id)


def _mark_ds_fallback() -> None:
    _ds_fallback_flag.set(True)
    tid = get_config_value("thread_id")
    if isinstance(tid, str) and tid:
        # 上限保护：回退是低频一次性警示，超限时整体清空（丢失旧线程标志无害）
        if len(_ds_fallback_threads) >= 1024:
            _ds_fallback_threads.clear()
        _ds_fallback_threads.add(tid)


def _ds_key() -> Optional[str]:
    key = get_config_value("deepseek_api_key")
    if isinstance(key, str) and key.strip():
        return key.strip()
    return None


def _auth_status_code(exc: BaseException) -> Optional[int]:
    """从异常提取认证类状态码（401/403）；非认证类返回 None。"""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    # openai.AuthenticationError / PermissionDeniedError 等 API 错误子类
    try:
        import openai

        for exc_type in (
            openai.AuthenticationError,
            openai.PermissionDeniedError,
        ):
            if isinstance(exc, exc_type):
                return getattr(exc, "status_code", 401)
    except Exception:
        pass
    # langchain_core 可能包装原始异常
    cause = getattr(exc, "__cause__", None) or getattr(exc, "from_exception", None)
    if cause is not None and cause is not exc:
        return _auth_status_code(cause)
    return None


class ModelRoutingMiddleware(AgentMiddleware):
    """按请求路由模型（qwen 默认 / 用户自备 DeepSeek key）。"""

    def wrap_model_call(self, request, handler):
        ds_key = _ds_key()
        if not ds_key:
            return handler(request)

        try:
            model = resolve_chat_model(user_ds_key=ds_key)
            return handler(request.override(model=model))
        except Exception as e:
            # 负缓存命中时 resolve_chat_model 已回退 qwen；这里兜底 401/403 重试
            status = _auth_status_code(e)
            if status in (401, 403):
                return self._fallback(request, handler, ds_key, e)
            logger.error("[ModelRouting] DS 模型调用异常: %s", e)
            return handler(request)

    async def awrap_model_call(self, request, handler):
        ds_key = _ds_key()
        if not ds_key:
            return await handler(request)

        try:
            model = resolve_chat_model(user_ds_key=ds_key)
            return await handler(request.override(model=model))
        except Exception as e:
            status = _auth_status_code(e)
            if status in (401, 403):
                return await self._afallback(request, handler, ds_key, e)
            logger.error("[ModelRouting] DS 模型调用异常: %s", e)
            return await handler(request)

    def _fallback(self, request, handler, ds_key: str, exc: BaseException):
        """401/403：标记 key 无效 + 置回退标志 + 用 qwen 重试一次。"""
        _mark_ds_fallback()
        mark_ds_key_invalid(ds_key)
        logger.warning(
            "[ModelRouting] deepseek key 无效（%s），已标记负缓存并回退 qwen",
            exc.__class__.__name__,
        )
        qwen = resolve_chat_model(user_ds_key=None)
        return handler(request.override(model=qwen))

    async def _afallback(self, request, handler, ds_key: str, exc: BaseException):
        _mark_ds_fallback()
        mark_ds_key_invalid(ds_key)
        logger.warning(
            "[ModelRouting] deepseek key 无效（%s），已标记负缓存并回退 qwen",
            exc.__class__.__name__,
        )
        qwen = resolve_chat_model(user_ds_key=None)
        return await handler(request.override(model=qwen))
