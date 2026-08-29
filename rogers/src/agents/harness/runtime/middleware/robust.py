"""
中间件健壮性加固：异常围栏（fail-open）+ 历史工具调用安全提取。

背景（2026-08-28 生产事故）：PlanQueueMiddleware._render_snapshot 对模型回传的
畸形 queue.todos（裁剪占位符字符串被原文回传）逐字符迭代，AttributeError 沿
wrap_model_call 链上抛 -> 整条 SSE 请求挂掉，该线程所有消息全灭。已热修
（commit 7b8af59），但暴露的是系统性缺口：中间件消费两类本质上不可信的数据——

1. checkpoint 历史中模型生成的 tool_calls args（LLM 输出落库再读回，形状不受控制）
2. 运行时附带数据（usage_metadata / configurable / 消息 content 多模态块）

除 context_message_gate（有 try/except fallback）外，所有自研中间件的钩子异常
都会沿框架链上抛杀死整个请求。增强型中间件（只加提示词/计数/日志）本应 fail-open。

本模块提供三道防线：
- model_hook_fail_open：装饰 wrap_model_call / awrap_model_call / wrap_tool_call /
  awrap_tool_call。钩子自身逻辑异常 -> ERROR 日志（带中间件类名 + hook 名，事故
  定位不再靠读源码猜帧）-> 放行 handler(request)（模型调用/工具照常执行）。
- state_hook_fail_open：装饰 before_agent / before_model / after_model / after_agent
  等 state hook。异常 -> ERROR 日志 -> 返回 None（跳过本次注入/计数/压缩/记忆提取）。
- msg_tool_calls(msg)：历史 tool_calls 统一安全提取，畸形条目跳过，语义中性，
  供重建类中间件复用（消灭重复手写防御，防将来新增中间件漏防）。

fail-open 语义 = 功能降级而非请求挂掉：少注入一段提示词 / 少一次计数 / 跳过一次
压缩，模型仍能对话。围栏吞异常以 ERROR 级日志 + exc_info 全栈暴露，不静默，
告警可依赖日志平台。
"""

import functools
import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger("fitcream.agent")


def _log_fail_open(instance: Any, hook_name: str, exc: BaseException) -> None:
    """记录围栏捕获：带中间件类名 + hook 名 + 全栈（供日志平台定位）。"""
    cls_name = type(instance).__name__ if instance is not None else "?"
    logger.error(
        "[%s.%s] 中间件钩子异常已被围栏捕获，fail-open 跳过本次增强逻辑: %s: %s",
        cls_name,
        hook_name,
        type(exc).__name__,
        exc,
        exc_info=True,
    )


def model_hook_fail_open(hook: Callable) -> Callable:
    """装饰 model/tool wrap 类钩子（sync/async 自适应，iscoroutinefunction 判断）。

    钩子自身逻辑异常 -> ERROR 日志 -> 放行 handler(request)（/ await），让模型
    调用/工具照常执行。已调用过 handler（delegated=True）后抛出的异常原样上抛：
    此刻再 fail-open 会二次执行模型/工具（更危险），且 handler 自身抛出的模型/
    工具错误本就该交给外层错误处理链（ModelRetry / ToolError / chat.py）。
    """
    if inspect.iscoroutinefunction(hook):

        @functools.wraps(hook)
        async def awrapper(self, request, handler):
            delegated = False

            async def _handler(req):
                nonlocal delegated
                delegated = True
                return await handler(req)

            try:
                return await hook(self, request, _handler)
            except Exception as e:
                if delegated:
                    raise
                _log_fail_open(self, hook.__name__, e)
                return await handler(request)

        return awrapper

    @functools.wraps(hook)
    def wrapper(self, request, handler):
        delegated = False

        def _handler(req):
            nonlocal delegated
            delegated = True
            return handler(req)

        try:
            return hook(self, request, _handler)
        except Exception as e:
            if delegated:
                raise
            _log_fail_open(self, hook.__name__, e)
            return handler(request)

    return wrapper


def state_hook_fail_open(hook: Callable) -> Callable:
    """装饰 before/after 类 state hook（sync/async 自适应）。

    钩子异常 -> ERROR 日志 -> 返回 None（跳过本次注入/计数/压缩/跳转/记忆提取）。
    """
    if inspect.iscoroutinefunction(hook):

        @functools.wraps(hook)
        async def awrapper(self, state, runtime):
            try:
                return await hook(self, state, runtime)
            except Exception as e:
                _log_fail_open(self, hook.__name__, e)
                return None

        return awrapper

    @functools.wraps(hook)
    def wrapper(self, state, runtime):
        try:
            return hook(self, state, runtime)
        except Exception as e:
            _log_fail_open(self, hook.__name__, e)
            return None

    return wrapper


def msg_tool_calls(msg: Any) -> list[tuple[str, dict, str | None]]:
    """安全提取消息中的 tool_calls：返回 [(name, args, id), ...]。

    不可信数据防御（checkpoint 历史中模型生成的 tool_calls args 形状不受控制）：
    - 非 dict 的 tc 条目跳过；
    - 缺 name（或 name 非 str）的条目跳过；
    - args 非 dict 视为 {}（语义中性：只做提取不做校验）。

    只做提取不做校验，供重建类中间件（PlanQueue / ContentValidation / SameToolLimit）
    复用；需要原样保留畸形条目语义的裁剪场景（context_message_gate）不适用本函数。
    """
    out: list[tuple[str, dict, str | None]] = []
    for tc in getattr(msg, "tool_calls", None) or []:
        if not isinstance(tc, dict):
            continue
        name = tc.get("name")
        if not isinstance(name, str):
            continue
        args = tc.get("args")
        if not isinstance(args, dict):
            args = {}
        call_id = tc.get("id")
        out.append((name, args, call_id if isinstance(call_id, str) else None))
    return out
