"""
计划设计队列上下文注入中间件（无状态）

配合 plan_queue_tools 的队列流程（见 skills/plan-creation/SKILL.md）：
队列状态不进 agent state_schema，而是由消息历史中的工具调用承载--
每个 present_plan_queue_tool / update_plan_queue_item_tool 调用都会留下
AIMessage.tool_calls（含完整 queue 入参）。

before_model 在用户新消息（HumanMessage）时，扫描消息历史重建当前队列快照，
注入 SystemMessage，让 agent 始终知道：哪些日已完成、当前在推进哪一日、
下一步该做什么，避免多轮对话后失忆或重复设计已完成日。

架构与 IntentMiddleware 一致：
- 仅在最新消息为 HumanMessage 时注入（跳过 ToolMessage/AIMessage，避免 tool 循环重复注入）
- 无实例级可变状态，编译进共享 graph，并发运行互不影响
"""

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from src.agents.harness.tools.plan.plan_queue_tools import QUEUE_TOOLS

logger = logging.getLogger("fitcream.agent")


def _extract_queue_from_tool_call(name: str, args: dict) -> dict | None:
    """从工具调用入参提取完整队列快照。

    - present_plan_queue_tool：入参 {title, todos}
    - update_plan_queue_item_tool：入参含 queue 字段（{title, todos}）
    """
    if not isinstance(args, dict):
        return None
    if name == "present_plan_queue_tool":
        return args if args.get("todos") is not None else None
    if name == "update_plan_queue_item_tool":
        q = args.get("queue")
        return q if isinstance(q, dict) else None
    return None


def _reconstruct_queue(messages: list) -> dict | None:
    """从后向前扫到第一个队列工具调用即停，返回最新队列快照。

    只找「最新一份」快照：update 携带全量更新后快照，故从后向前遇到的第一个
    队列工具调用即当前真实状态，无需全量遍历（旧实现 O(N) 深拷贝优化）。
    """
    for msg in reversed(messages):
        tool_calls = getattr(msg, "tool_calls", None) or []
        if not tool_calls:
            continue
        for tc in reversed(tool_calls):
            name = tc.get("name") if isinstance(tc, dict) else None
            if name not in QUEUE_TOOLS:
                continue
            args = tc.get("args") if isinstance(tc, dict) else None
            q = _extract_queue_from_tool_call(name, args or {})
            if q:
                return q
    return None


def _render_snapshot(queue: dict) -> str:
    """把队列快照渲染成注入给模型的简明文本。"""
    title = queue.get("title", "计划设计")
    todos = queue.get("todos") or []
    done = sum(1 for t in todos if t.get("status") == "completed")
    lines = [
        "# 计划设计待办进度（务必据此推进，做了就打勾，勿重复已完成项）",
        f"队列：{title}（{done}/{len(todos)} 完成）",
    ]
    next_todo = None
    for t in todos:
        status = t.get("status", "pending")
        mark = {
            "completed": "✓",
            "in_progress": "▸",
            "skipped": "·",
            "pending": "○",
        }.get(status, "○")
        lines.append(f"  {mark} [{t.get('id', '?')}] {t.get('title', '?')}")
        if status == "in_progress":
            next_todo = t.get("title", t.get("id", "当前项"))
        elif status == "pending" and next_todo is None:
            next_todo = t.get("title", t.get("id", "下一个待办"))
    if next_todo:
        lines.append(f"当前应推进：{next_todo}")
    else:
        lines.append("所有待办已完成：流程结束，总结即可")
    return "\n".join(lines)


class PlanQueueMiddleware(AgentMiddleware):
    """计划设计队列上下文注入（无状态，编译进共享 graph）。

    before_model：仅当最新消息为 HumanMessage 时，从消息历史重建队列快照并注入
    SystemMessage。队列工具调用本身是 AIMessage（非 HumanMessage），故 tool 循环
    中不会重复注入，只在用户每轮新消息时刷新一次快照，token 开销可控。
    """

    def before_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, HumanMessage):
            return None

        snapshot = _reconstruct_queue(messages)
        if not snapshot:
            return None

        logger.info("[PlanQueue] Injected queue snapshot into context")
        return {"messages": [SystemMessage(content=_render_snapshot(snapshot))]}
