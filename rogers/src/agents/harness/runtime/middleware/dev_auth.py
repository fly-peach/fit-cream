"""
Dev Auth Middleware

开发环境专用中间件：自动注入管理员身份到 tool config 中。
使 LangGraph Studio 中无需手动配置 user_id 即可测试所有工具。

原理：
- 在 awrap_tool_call 中拦截工具调用
- 通过 contextvar (var_child_runnable_config) 注入 admin user_id
- 工具函数读取 config 时自动获得管理员身份
"""

import logging
from typing import Any, Callable, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command

from utils.security import mask_phone

logger = logging.getLogger("fitcream.agent.dev_auth")

# 缓存管理员 user_id（避免每次工具调用都查 DB）
_admin_user_id: Optional[str] = None


def _is_dev_env() -> bool:
    """仅在开发环境生效：DEBUG=True 或 langgraph dev（LANGGRAPH_DEV）运行时。"""
    import os

    try:
        from app.config import settings

        if getattr(settings, "DEBUG", False):
            return True
    except Exception:
        pass
    return os.getenv("LANGGRAPH_DEV", "").lower() in ("1", "true", "yes")


async def _get_admin_user_id() -> Optional[str]:
    """
    从数据库获取管理员 user_id（懒加载 + 缓存）。
    使用 .env 中 SEED_ADMIN_PHONE 对应的用户。
    """
    global _admin_user_id
    if _admin_user_id is not None:
        return _admin_user_id

    try:
        from app.database import async_session_factory
        from src.fitme.models.user import User
        from sqlalchemy import select

        # 读取配置的管理员手机号
        import os
        admin_phone = os.getenv("SEED_ADMIN_PHONE", "")
        if not admin_phone:
            logger.warning("[DevAuth] SEED_ADMIN_PHONE 未配置，无法注入管理员身份")
            return None

        async with async_session_factory() as db:
            result = await db.execute(select(User).where(User.phone == admin_phone))
            user = result.scalar_one_or_none()
            if user:
                _admin_user_id = str(user.id)
                logger.info(f"[DevAuth] 管理员身份已加载: {mask_phone(admin_phone)} -> {_admin_user_id[:8]}...")
                return _admin_user_id
            else:
                logger.warning(f"[DevAuth] 管理员账号不存在: {mask_phone(admin_phone)}")
                return None
    except Exception as e:
        logger.error(f"[DevAuth] 获取管理员身份失败: {e}")
        return None


class DevAuthMiddleware(AgentMiddleware):
    """
    开发环境认证中间件。

    在工具调用前自动注入管理员 user_id 到 config 中，
    使所有工具无需登录即可正常工作。

    仅用于 langgraph dev / LangGraph Studio 调试。
    """

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if _is_dev_env():
            logger.info("[DevAuth] Agent started (dev mode with admin auth)")
        return None

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable,
    ) -> ToolMessage | Command:
        """
        拦截工具调用，注入管理员身份到 config contextvar。

        通过 var_child_runnable_config 注入 user_id，
        使工具函数读取 config 时自动获得管理员身份。

        仅在开发环境（DEBUG 或 LANGGRAPH_DEV）生效；生产环境直接放行。
        """
        if not _is_dev_env():
            return await handler(request)

        from langchain_core.runnables.config import var_child_runnable_config

        admin_id = await _get_admin_user_id()
        if not admin_id:
            return await handler(request)

        # 读取当前 config
        current_config = var_child_runnable_config.get(None)
        if current_config is None:
            current_config = {}

        # 检查是否已有 user_id
        configurable = current_config.get("configurable", {})
        if configurable.get("user_id"):
            # 已有 user_id，不覆盖
            return await handler(request)

        # 注入管理员身份
        patched_config = {
            **current_config,
            "configurable": {
                **configurable,
                "user_id": admin_id,
                "thread_id": configurable.get("thread_id", f"dev-{admin_id[:8]}"),
            },
        }

        # 设置 contextvar，使工具函数能读取到
        token = var_child_runnable_config.set(patched_config)
        try:
            result = await handler(request)
            return result
        finally:
            var_child_runnable_config.reset(token)

    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if _is_dev_env():
            logger.info("[DevAuth] Agent ended (dev mode)")
        return None