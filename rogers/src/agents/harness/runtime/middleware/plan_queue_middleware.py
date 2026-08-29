"""
计划设计队列上下文注入中间件（无状态）

配合 plan_queue_tools 的队列流程（见 skills/plan-creation/SKILL.md）：
队列状态不进 agent state_schema，而是由消息历史中的工具调用承载--
每个 present_plan_queue_tool / update_plan_queue_item_tool 调用都会留下
AIMessage.tool_calls（含完整 queue 入参）。

wrap_model_call 在用户新消息（HumanMessage）时，扫描消息历史重建当前队列快照，
临时合并进 request.system_message（F1：不落 checkpoint），让 agent 始终知道：
哪些日已完成、当前在推进哪一日、下一步该做什么，避免多轮对话后失忆或重复设计
已完成日。

架构与 RequestGateMiddleware 一致：
- 仅在最新消息为 HumanMessage 时注入（跳过 ToolMessage/AIMessage，避免 tool 循环重复注入）
- 无实例级可变状态，编译进共享 graph，并发运行互不影响
- F3：队列快照经 get_queue_snapshot 单次计算并在同一 model 调用内被
  ContentValidationMiddleware 复用（进程级消息对象 id 键请求级缓存，每轮由本中间件清空）
"""

import logging
from typing import Any, Optional

from langchain.messages import HumanMessage

from src.agents.harness.tools.plan.plan_queue_tools import QUEUE_TOOLS
from src.agents.harness.runtime.middleware.robust import msg_tool_calls
from src.agents.harness.runtime.middleware.transient_prompt import (
    TransientPromptMiddleware,
)

logger = logging.getLogger("fitcream.agent")

# 未命中缓存的哨兵（区分「未缓存」与「缓存了 None」）
_MISSING = object()

# F3：队列快照在单个 model 调用内被 PlanQueue / ContentValidation 共享。
# 键为消息对象 id 元组——同一 wrap 链内 PlanQueue 与 ContentValidation 拿到的是
# 同一个 messages 列表（消息对象完全一致，id 元组相同即命中）。不同内容的列表
# 必然含不同消息对象，id 元组不同则重算；生产运行时消息对象在 checkpoint 存活
# 期间 id 不会被复用，无跨轮脏数据。容量超限整体清空（条目极小，丢失只触发一次
# 重扫）。无实例级可变状态，并发 run 互不影响。
_queue_snapshot_cache: dict[tuple, Any] = {}
_QUEUE_SNAPSHOT_CACHE_MAX = 1024


def _extract_queue_from_tool_call(name: str, args: dict) -> dict | None:
    """从工具调用入参提取完整队列快照。

    - present_plan_queue_tool：入参 {title, todos}
    - update_plan_queue_item_tool：入参含 queue 字段（{title, todos}）

    防御：todos 必须是 list 才视为有效快照（模型可能把裁剪占位符「…(省略…)」
    或字符串数组原文回传，todos_kind=str——见 context_message_gate 备注），
    否则返回 None，让 _reconstruct_queue 继续找更早的有效快照而非崩溃。
    """
    if not isinstance(args, dict):
        return None
    if name == "present_plan_queue_tool":
        todos = args.get("todos")
        return args if isinstance(todos, list) else None
    if name == "update_plan_queue_item_tool":
        q = args.get("queue")
        if isinstance(q, dict) and isinstance(q.get("todos"), list):
            return q
        return None
    return None


def _reconstruct_queue(messages: list) -> dict | None:
    """从后向前扫到第一个队列工具调用即停，返回最新队列快照。

    只找「最新一份」快照：update 携带全量更新后快照，故从后向前遇到的第一个
    队列工具调用即当前真实状态，无需全量遍历（旧实现 O(N) 深拷贝优化）。

    经 msg_tool_calls 统一安全提取：非 dict tc / 缺 name / args 非 dict 的畸形
    条目被跳过，_extract_queue_from_tool_call 对畸形快照（todos 非 list）返回
    None，继续找更早的有效快照（保持今日修复的畸形跳过语义不变）。
    """
    for msg in reversed(messages):
        for name, args, _ in reversed(msg_tool_calls(msg)):
            if name not in QUEUE_TOOLS:
                continue
            q = _extract_queue_from_tool_call(name, args)
            if q:
                return q
    return None


def get_queue_snapshot(messages: list) -> dict | None:
    """返回消息历史中的最新队列快照（同一 messages 对象复用首次扫描结果）。

    供 PlanQueueMiddleware / ContentValidationMiddleware 共享，避免同一 model
    调用内对完整消息历史重复后向扫描（F3 单次计算）。
    """
    key = tuple(id(m) for m in messages)
    cached = _queue_snapshot_cache.get(key, _MISSING)
    if cached is not _MISSING:
        return cached
    snapshot = _reconstruct_queue(messages)
    if len(_queue_snapshot_cache) >= _QUEUE_SNAPSHOT_CACHE_MAX:
        _queue_snapshot_cache.clear()
    _queue_snapshot_cache[key] = snapshot
    return snapshot


def _render_snapshot(queue: dict) -> str:
    """把队列快照渲染成注入给模型的简明文本。"""
    title = queue.get("title", "计划设计")
    raw_todos = queue.get("todos") or []
    # 防御：模型回传的 todos 可能是字符串（占位符原文）/ dict / 含非 dict 元素，
    # 只保留 dict 项，防 sum/循环里 str.get 抛 AttributeError 阻断整条消息。
    if isinstance(raw_todos, list):
        todos = [t for t in raw_todos if isinstance(t, dict)]
    elif isinstance(raw_todos, dict):
        todos = [raw_todos]
    else:
        todos = []
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


class PlanQueueMiddleware(TransientPromptMiddleware):
    """计划设计队列上下文注入（无状态，编译进共享 graph）。

    wrap_model_call（基类 TransientPromptMiddleware 统一实现）：仅当最新消息为
    HumanMessage 时，从消息历史重建队列快照并临时合并进 request.system_message
    （F1 不落 checkpoint）。队列工具调用本身是 AIMessage（非 HumanMessage），故
    tool 循环中不会重复注入，只在用户每轮新消息时刷新一次快照，token 开销可控。
    """

    def _prompt(self, messages: list) -> Optional[str]:
        if not messages:
            return None
        if not isinstance(messages[-1], HumanMessage):
            return None
        # 每轮用户新消息首次读取前清空缓存：PlanQueue 是本轮 wrap 链第一个
        # 消费者（先于 ContentValidation），清空后本调用只计算一次；跨轮/跨线程
        # 即使消息对象 id 复用也不会命中上一轮的陈旧快照。
        _queue_snapshot_cache.clear()
        snapshot = get_queue_snapshot(messages)
        if not snapshot:
            return None
        logger.info("[PlanQueue] Injected queue snapshot into context")
        return _render_snapshot(snapshot)
