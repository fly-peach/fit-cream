"""
运行时配置开关读取（共享图架构下的统一入口）

中间件/工具需要读取 RunnableConfig.configurable 中的布尔开关时，
统一走 ``get_config_flag``，避免各中间件重复手写 get_config() 解析、
也避免中间件之间互相 import（如 intent_middleware 曾 import
kb_gate_middleware 的 kb_enabled_from_config 造成耦合）。

缺失 / falsy / 解析异常（如 LangGraph Studio 无 configurable）一律返回 default，
保证旧客户端与开发环境行为不变。
"""

from typing import Any


def get_config_flag(name: str, default: bool = False) -> bool:
    """从当前 run 的 RunnableConfig.configurable 解析布尔开关。"""
    try:
        from langgraph.config import get_config

        cfg = get_config() or {}
        conf = cfg.get("configurable") or {}
        return bool(conf.get(name, default))
    except Exception:
        return default


def get_config_value(name: str, default: Any = None) -> Any:
    """从当前 run 的 RunnableConfig.configurable 解析任意值。"""
    try:
        from langgraph.config import get_config

        cfg = get_config() or {}
        conf = cfg.get("configurable") or {}
        return conf.get(name, default)
    except Exception:
        return default
