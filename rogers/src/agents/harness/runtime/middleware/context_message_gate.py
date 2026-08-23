"""
模型视图级上下文裁剪中间件（token 精简 + 结构收敛）

背景：计划设计（plan-creation）长流程中，每个 present_plan_queue_tool /
update_plan_queue_item_tool 调用都会在消息历史里留下**完整队列快照**入参
（AIMessage.tool_calls），多轮后这些冗余快照占用大量 token。

机制（纯模型视图级裁剪，不落 checkpoint、不改前端契约）：
- wrap_model_call / awrap_model_call 在模型请求前对 request.messages 做视图级
  裁剪：把历史中队列工具的完整 queue/todos 入参替换为轻量占位
  （{"title": ..., "todos": "…(省略，见 SystemMessage)"}），
  用 request.override(messages=...) 返回裁剪后的消息。
- 只影响本次模型请求：checkpoint 里的 tool_calls 原样保留，前端待办面板渲染不受影响；
  SSE tool_start/step 事件不经过此处（仍走 on_tool_start），无前端协议变更。
- 队列完整快照仍由 PlanQueueMiddleware 每轮注入 SystemMessage，模型不丢状态。

实现要求（阶段四风险表）：
- 裁剪为纯函数（_redact_messages），配单测；
- 裁剪抛任何异常都 fallback 原消息（返回 handler(request)），不阻断生产。
"""

import logging

from langchain.agents.middleware import AgentMiddleware

from src.agents.harness.tools.plan.plan_queue_tools import QUEUE_TOOLS

logger = logging.getLogger("fitcream.agent")

# todos 占位文案：完整快照由 PlanQueueMiddleware 每轮注入 SystemMessage
_QUEUE_REDACTED_TODOS = "…(省略，完整队列见注入的 SystemMessage 快照)"


def _redact_queue_args(args: dict, name: str) -> dict:
    """把队列工具入参中的完整队列快照替换为轻量占位（保留 title/item_id/status）。"""
    if name == "present_plan_queue_tool":
        return {"title": args.get("title", ""), "todos": _QUEUE_REDACTED_TODOS}
    if name == "update_plan_queue_item_tool":
        queue = args.get("queue") or {}
        return {
            "item_id": args.get("item_id", ""),
            "status": args.get("status", ""),
            "queue": {"title": queue.get("title", ""), "todos": _QUEUE_REDACTED_TODOS},
        }
    return args


def _redact_messages(messages: list) -> list:
    """返回裁剪后的消息列表（仅替换含队列工具调用的 AIMessage）。

    纯函数：不改动入参消息；无队列工具调用时原样返回同一列表对象。
    """
    out: list = []
    changed_any = False
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            out.append(msg)
            continue

        new_calls: list = []
        changed = False
        for tc in tool_calls:
            name = tc.get("name") if isinstance(tc, dict) else None
            if name not in QUEUE_TOOLS:
                new_calls.append(tc)
                continue
            args = tc.get("args")
            if not isinstance(args, dict):
                new_calls.append(tc)
                continue
            new_calls.append({**tc, "args": _redact_queue_args(args, name)})
            changed = True

        if changed:
            out.append(msg.model_copy(update={"tool_calls": new_calls}))
            changed_any = True
        else:
            out.append(msg)

    return out if changed_any else messages


class ContextMessageGateMiddleware(AgentMiddleware):
    """
    模型视图级上下文裁剪中间件：把历史中冗余的完整队列快照入参替换为轻量占位。

    仅作用于模型请求视图（request.override(messages=...)），不改 checkpoint、
    不改 SSE 工具事件，前端待办面板与历史消息渲染不受影响。

    无实例级可变状态，编译进共享 graph，并发 run 互不影响。
    """

    def wrap_model_call(self, request, handler):
        """同步路径：裁剪队列入参后调用模型。"""
        if not request.messages:
            return handler(request)
        try:
            trimmed = _redact_messages(request.messages)
            if trimmed is request.messages:
                return handler(request)
            return handler(request.override(messages=trimmed))
        except Exception as e:
            # 裁剪失败 fallback 原消息，绝不阻断生产
            logger.warning("[ContextGate] 队列入参裁剪失败，回退原消息: %s", e)
            return handler(request)

    async def awrap_model_call(self, request, handler):
        """异步路径（生产 SSE 走这里）：同 wrap_model_call。"""
        if not request.messages:
            return await handler(request)
        try:
            trimmed = _redact_messages(request.messages)
            if trimmed is request.messages:
                return await handler(request)
            return await handler(request.override(messages=trimmed))
        except Exception as e:
            logger.warning("[ContextGate] 队列入参裁剪失败，回退原消息: %s", e)
            return await handler(request)
