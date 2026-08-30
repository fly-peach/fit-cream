"""对话路由 /api/chat/* - 流式对话 + Thread CRUD + 图片上传"""
import asyncio
import base64
import json
import logging
import time
from datetime import date, datetime
from typing import Dict, Optional
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.dependencies import get_current_user
from src.agents.harness.orchestration.model_factory import (
    create_deepseek_vision,
    estimate_tokens,
    extract_usage,
    is_ds_key_invalid,
)
from src.agents.harness.runtime.middleware.model_routing import (
    ds_key_fallback_active,
    reset_ds_key_fallback,
)
from src.agents.harness.runtime.conversation_service import ConversationService
from src.agents.models.thread_meta import ThreadMeta
from src.agents.models.thread_usage import ThreadUsage
from src.fitme.models.user import User
from src.fitme.services.usage_service import UsageService
from src.agents.schemas.chat import (
    ChatRequest,
    MessageOut,
    ThreadMessagesOut,
    ThreadOut,
    ThreadTitleIn,
)
from src.fitme.schemas.common import ResponseModel
from utils.exceptions import ForbiddenException
from utils.logger import reset_user_context, set_user_context
from utils.oss import is_oss_configured, upload_chat_image

logger = logging.getLogger("fitcream.chat")

router = APIRouter(prefix="/chat", tags=["chat"])

# 存储活跃的流式任务，用于停止生成
# key: thread_id, value: asyncio.Event（set() 后流式生成器检测到并终止）
_active_streams: Dict[str, asyncio.Event] = {}

# SSE 事件中单个字符串字段的最大长度，防止 nginx proxy_buffer_size 溢出
_MAX_SSE_FIELD_LENGTH = 5000


def _truncate_tool_input(data, max_len: int = _MAX_SSE_FIELD_LENGTH):
    """递归截断工具入参中的过长字符串字段，防止 SSE 单事件超出 nginx 缓冲区。"""
    if isinstance(data, str):
        return data[:max_len] + "…" if len(data) > max_len else data
    if isinstance(data, dict):
        return {k: _truncate_tool_input(v, max_len) for k, v in data.items()}
    if isinstance(data, list):
        return [_truncate_tool_input(v, max_len) for v in data]
    return data


def _json_default(obj):
    """json.dumps default：把 date/datetime 等非 JSON 原生值转为 ISO 字符串。"""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def _serialize_tool_output(raw_output) -> str:
    """把 on_tool_end 的工具输出规范化为 JSON 字符串。

    新版 LangGraph 的 on_tool_end 事件里 ``data.output`` 是 ``ToolMessage`` 对象
    （而非工具返回的原始 dict），直接 ``str()`` 会产生 ``content="..."`` 前缀，
    前端无法解析。这里统一做三件事：
    1. 若是消息对象，提取其 ``content``（工具真实返回值）；
    2. 用 ``_json_default`` 兜底 date/datetime 等非 JSON 原生值；
    3. 实在无法序列化时回退 ``str()``，保证 SSE 字段始终是字符串。
    """
    if not isinstance(raw_output, str) and hasattr(raw_output, "content"):
        raw_output = raw_output.content
    if isinstance(raw_output, str):
        return raw_output
    try:
        return json.dumps(raw_output, ensure_ascii=False, default=_json_default)
    except (TypeError, ValueError):
        return str(raw_output)


def _get_agent():
    from src.agents.agent_graph import get_agent
    return get_agent()


def _image_url_expired(url: str) -> bool:
    """判断 OSS 签名 URL 是否已过期（解析 Expires 查询参数）。"""
    if not url or not url.startswith("http"):
        return False
    try:
        qs = parse_qs(urlparse(url).query)
        expires = qs.get("Expires")
        if not expires:
            return False
        return float(expires[0]) < time.time()
    except Exception:
        return False


async def _clean_expired_image_urls(checkpointer, thread_id: str) -> None:
    """Agent 发送前清理 checkpoint 中的过期 OSS 签名图片 URL。

    仅替换**已过期**的 OSS 签名 URL（已无法被模型读取）为占位文本，避免每轮
    重复发送无效图片浪费 token。统一 qwen3.8-flash / deepseek 视觉模型后所有模型
    均支持多模态，不再有非视觉模型强剥图片分支。无修改则不写 checkpoint。
    """
    if checkpointer is None:
        return
    config = {"configurable": {"thread_id": thread_id}}
    try:
        tup = await checkpointer.aget_tuple(config)
    except Exception as e:
        logger.warning(f"[Chat] aget_tuple failed: {e}")
        return
    if not tup:
        return
    checkpoint = tup.checkpoint or {}
    messages = (checkpoint.get("channel_values") or {}).get("messages") or []
    modified = False
    for msg in messages:
        content = getattr(msg, "content", None)
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "image_url":
                continue
            img = block.get("image_url") or {}
            url = img.get("url", "") if isinstance(img, dict) else ""
            if url and _image_url_expired(url):
                block["type"] = "text"
                block["text"] = "[图片已分析完毕]"
                modified = True
    if modified:
        try:
            # 必须 bump messages 的 channel_versions：AsyncPostgresSaver 的 blob 存储
            # 按 channel_versions 判断是否变更，版本不变则不会持久化修改后的消息
            new_versions = dict(checkpoint.get("channel_versions") or {})
            new_versions["messages"] = (
                f"{new_versions.get('messages', '0')}.img-clean.{modified}"
            )
            checkpoint["channel_versions"] = new_versions
            await checkpointer.aput(tup.config, checkpoint, tup.metadata, new_versions)
            logger.info(f"[Chat] Cleaned expired image_urls | thread={thread_id[:8]}")
        except Exception as e:
            logger.warning(f"[Chat] aput failed: {e}")


async def _repair_dangling_tool_calls(checkpointer, thread_id: str) -> None:
    """修复 checkpoint 中悬空的 AIMessage.tool_calls（缺对应 ToolMessage 的调用）。

    异常/递归崩溃后，checkpoint 可能残留「已发出 tool_calls 但无 ToolMessage 响应」
    的 AIMessage。qwen 容忍此类坏状态，但 DeepSeek 严格要求每个 tool_call_id 都有
    响应，继续对话会触发 400（Bug B1）。这里扫描历史，为缺少响应的
    tool_call 追加合成 ToolMessage（占位说明），幂等；同时修复存量坏线程
    （9cd8bb77 / a471d3bd 等）。无修改则不写 checkpoint。

    仅限 /chat/message 路径调用；/chat/resume 绝不可调用——resume 面对的
    合法 pending 中断会被误判为悬空并被修复逻辑破坏（审批死循环事故）。
    """
    if checkpointer is None:
        return
    config = {"configurable": {"thread_id": thread_id}}
    try:
        tup = await checkpointer.aget_tuple(config)
    except Exception as e:
        logger.warning(f"[Chat] aget_tuple failed: {e}")
        return
    if not tup:
        return
    checkpoint = tup.checkpoint or {}
    messages = (checkpoint.get("channel_values") or {}).get("messages") or []
    if not messages:
        return

    replied_ids = {
        getattr(msg, "tool_call_id", None)
        for msg in messages
        if isinstance(msg, ToolMessage)
    }
    dangling = []
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        for tc in getattr(msg, "tool_calls", []) or []:
            cid = tc.get("id")
            if cid and cid not in replied_ids:
                dangling.append(tc)
    if not dangling:
        return

    for tc in dangling:
        messages.append(ToolMessage(
            content="[该工具调用未执行完成（此前的运行被中断或用户放弃了审批）；如仍需要请重新发起]",
            tool_call_id=tc["id"],
            name=tc.get("name", ""),
        ))
    try:
        # 必须 bump messages 的 channel_versions：AsyncPostgresSaver 的 blob 存储
        # 按 channel_versions 判断是否变更，版本不变则 aput 不会持久化修复结果
        # （此前实测：24 条消息 + 1 悬空，修复后仍 24 条——aput 静默未写入）。
        new_versions = dict(checkpoint.get("channel_versions") or {})
        new_versions["messages"] = (
            f"{new_versions.get('messages', '0')}.repair.{len(dangling)}"
        )
        checkpoint["channel_versions"] = new_versions
        await checkpointer.aput(tup.config, checkpoint, tup.metadata, new_versions)
        logger.info(
            f"[Chat] Repaired {len(dangling)} dangling tool_calls | thread={thread_id[:8]}"
        )
    except Exception as e:
        logger.warning(f"[Chat] aput failed: {e}")


async def _build_user_context(user: User) -> str:
    """构建用户动态上下文（精简版）：注入当前日期/时间（用户时区）与用户称呼。

    此前每轮会查询 goal/BMI/streak/active plan 并作为 SystemMessage 注入，
    这些数据随 checkpointer 累积在历史中、逐轮重复消耗 token。用户目标 / 身体
    数据 / 打卡 / 计划均可通过 get_user_profile_tool / get_streak_tool /
    list_plans_tool 等按需获取，故不再每轮注入，仅在需要时由模型主动调用工具。
    日期/时间由 utils.timeutil 按 APP_TZ（默认 Asia/Shanghai）计算，
    保证打卡/补卡等按"今天/昨天"语义取到用户时区的正确日期。
    """
    from utils.timeutil import now, today

    now_local = now()
    weekday_cn = ["一", "二", "三", "四", "五", "六", "日"][now_local.weekday()]
    parts = [
        f"- 当前日期：{today().isoformat()}（周{weekday_cn}）",
        f"- 当前时间：{now_local:%H:%M}",
    ]
    parts.append(f"- 用户称呼：{user.name or '用户'}")
    return "# 当前对话上下文\n" + "\n".join(parts)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ============================================================
# HITL（Human-in-the-Loop）中断检测与审批载荷
# ============================================================

def _extract_pending_approvals(state_snapshot) -> list[dict]:
    """从 agent state snapshot 提取待审批的 HITL 中断，转为前端 approval_needed 载荷。

    遍历 ``state.tasks[*].interrupts``，每个中断的 ``value`` 是 HITLRequest：
    ``{"action_requests": [...], "review_configs": [...]}``（同序对齐）。

    Returns:
        ``[{id, tool, input, description, allowed_decisions}, ...]``
    """
    approvals: list[dict] = []
    if state_snapshot is None:
        return approvals

    tasks = getattr(state_snapshot, "tasks", ()) or ()
    for task in tasks:
        interrupts = getattr(task, "interrupts", ()) or ()
        for intr in interrupts:
            value = getattr(intr, "value", None) or {}
            if not isinstance(value, dict):
                continue
            action_requests = value.get("action_requests", []) or []
            review_configs = value.get("review_configs", []) or []
            intr_id = getattr(intr, "id", None) or getattr(task, "id", "")
            for idx, ar in enumerate(action_requests):
                rc = review_configs[idx] if idx < len(review_configs) else {}
                approvals.append({
                    "id": str(intr_id),
                    "tool": ar.get("name", ""),
                    "input": ar.get("args", {}) or {},
                    "description": ar.get("description", ""),
                    "allowed_decisions": rc.get("allowed_decisions") or ["approve", "reject"],
                })
    return approvals


async def _detect_interrupts(agent, config) -> list[dict]:
    """流结束后检查 agent state 是否有待审批中断，返回 approval 载荷（空表表示无中断）。"""
    try:
        state = await agent.aget_state(config)
    except Exception as e:
        logger.warning(f"[Chat] aget_state failed: {e}")
        return []
    return _extract_pending_approvals(state)


def _mark_stale_tools(steps: list, status: str) -> None:
    """把仍处于 running 的工具步骤就地改写为指定状态。

    中断/异常发生在 on_tool_start 之后、on_tool_end 之前时，被中断的工具
    没有 tool_result，步骤会停留在 running。这里统一改写，避免前端永久转圈。
    """
    for s in steps:
        if isinstance(s, dict) and s.get("type") == "tool" and s.get("status") == "running":
            s["status"] = status


class StopRequest(BaseModel):
    """停止生成请求"""
    thread_id: str


class ResumeDecision(BaseModel):
    """单个审批决策。

    - type=approve：批准执行
    - type=reject：拒绝；reason 为修改说明/修订稿时，后端作为 reject 消息注入，
      引导 agent 按修订稿重新提案并再次中断（edit 语义）
    """
    type: str  # "approve" | "reject"
    reason: Optional[str] = None


class ResumeRequest(BaseModel):
    """恢复被中断对话的请求"""
    thread_id: str
    decisions: list[ResumeDecision]
    # 知识库回答开关：resume 后仍有模型调用，需保持门控一致（前端随 resume 传当前开关状态）
    kb_enabled: Optional[bool] = Field(
        None, description="是否开启知识库回答（与 /chat/message 一致）"
    )
    # 用户自备 DeepSeek API Key（BYOK）：resume 后仍有模型调用，需保持一致
    deepseek_api_key: Optional[str] = Field(
        None, max_length=512, description="用户自备 DeepSeek API Key（仅前端 localStorage 持有）"
    )


def _inject_request_config(config: dict, req) -> None:
    """把 kb_enabled / deepseek_api_key 写入 RunnableConfig.configurable。

    deepseek key 命中负缓存（曾 401/403）时直接忽略并告警，避免无效重试。
    """
    conf = config["configurable"]
    conf["kb_enabled"] = bool(req.kb_enabled)
    key = (req.deepseek_api_key or "").strip() if getattr(req, "deepseek_api_key", None) else ""
    if key:
        if is_ds_key_invalid(key):
            logger.warning("[Chat] deepseek key 命中负缓存，忽略本次注入")
        else:
            conf["deepseek_api_key"] = key


class VerifyDeepSeekKeyIn(BaseModel):
    """校验用户自备 DeepSeek API Key（保存前调用，不落库）"""
    deepseek_api_key: str = Field(..., min_length=8, max_length=512)


def _build_resume_command(decisions: list[ResumeDecision]):
    """把前端 decisions 转为 LangGraph Command(resume=...)。

    reject 的 reason 映射为 RejectDecision.message（注入给模型的拒绝说明）。
    """
    from langgraph.types import Command

    lc_decisions: list[dict] = []
    for d in decisions:
        if d.type == "approve":
            lc_decisions.append({"type": "approve"})
        elif d.type == "reject":
            if d.reason:
                lc_decisions.append({
                    "type": "reject",
                    "message": f"用户修改了方案，请按以下内容重新设计并再次提交提案：\n{d.reason}",
                })
            else:
                lc_decisions.append({"type": "reject"})
        else:
            lc_decisions.append({"type": d.type})

    return Command(resume={"decisions": lc_decisions})


async def _run_agent_sse(
    agent,
    config: dict,
    input_or_command,
    *,
    thread_id: str,
    user_id,
    user,
    stop_event: "asyncio.Event",
    stream_db: AsyncSession,
    is_resume: bool = False,
):
    """共享 SSE 流式生成器：逐 token 转发 Agent 回复 + 中断检测 + 落库。

    被 /chat/message（普通消息）与 /chat/resume（恢复中断）复用。
    input_or_command 为 dict（新消息）或 Command(resume=...)（恢复）。

    yields SSE 事件字符串。
    """
    # 每请求重置「DS key 无效回退」标志（ModelRoutingMiddleware 置位，结束后发警示）
    reset_ds_key_fallback(thread_id)
    yield _sse_event("start", {"thread_id": thread_id})

    # D2：本请求的上下文上限（plan_design 200K / 默认 150K），随 usage 事件下发
    is_plan_design = bool((config.get("configurable") or {}).get("plan_design"))
    context_max_tokens = 200_000 if is_plan_design else 150_000

    full_content = ""        # 累积正式回复文本（本阶段）
    # 思考内容不再累积/落库（D5）：仅用 reasoning 分支判定思考阶段切换
    tool_calls = []          # 完整工具调用记录 [{id, name, input, output, status}]
    steps: list[dict] = []   # ReAct 步骤序列（不含 thought：思考碎片不再进入前端时间线）
    pending_reply: Optional[dict] = None
    # 当前思考阶段是否已发「思考中」状态事件（每阶段只发一次；思考内容仍不下发）
    thinking_started = False
    # 按 run_id 索引进行中的工具：并行工具调用时 on_tool_start/end 事件交错，
    # 单指针跟踪会丢失先启动的工具，导致其永远停留在 running
    _tools_by_run_id: dict[str, dict] = {}
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "max_tokens": context_max_tokens,
    }
    run_usage: dict[str, dict[str, int]] = {}
    # FR-3: 请求级累加 token（区别于非累加的 usage「最近一次上下文大小」）
    usage_total = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "llm_calls": 0,
        "estimated": False,
    }

    try:
        async for event in agent.astream_events(input_or_command, config=config, version="v2"):
            if stop_event.is_set():
                _mark_stale_tools(steps, "interrupted")
                if full_content or tool_calls:
                    await ConversationService.save_message(
                        stream_db, user.id, thread_id, "assistant", full_content,
                        metadata={
                            "tool_calls": tool_calls or None,
                            "steps": steps or None,
                            "stopped": True,
                        },
                    )
                yield _sse_event("stopped", {"thread_id": thread_id, "partial_content": full_content})
                return

            kind = event["event"]

            if kind == "on_chat_model_start":
                # 模型调用开始即发「思考中」状态事件：不依赖 reasoning_content--
                # plan_design 会话路由 enable_thinking=False 的 qwen（P1-4 省
                # reasoning tokens）时无 reasoning 产出，工具轮间隙前端会完全无
                # 反馈干等。首个 token / step / tool_start 事件到达即清除。
                if not thinking_started:
                    thinking_started = True
                    yield _sse_event("thinking", {"content": ""})

            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                reasoning = chunk.additional_kwargs.get("reasoning_content", "")
                if reasoning:
                    if not thinking_started:
                        # 思考阶段开始：发一个无内容的 thinking 状态事件，让前端显示
                        # 「思考中...」而不是干等。不带 reasoning 内容（防泄漏内部权衡）。
                        thinking_started = True
                        yield _sse_event("thinking", {"content": ""})
                    # 思考内容不下发前端、不累积落库（D5）：reasoning_content 仅用于
                    # 判定思考阶段切换，qwen enable_thinking 的冗长内容不再保存。
                if chunk.content:
                    if thinking_started:
                        thinking_started = False  # 开始出正式回复，思考阶段结束
                    if pending_reply is None:
                        pending_reply = {"type": "reply", "content": ""}
                        steps.append(pending_reply)
                    pending_reply["content"] += chunk.content
                    full_content += chunk.content
                    yield _sse_event("token", {"content": chunk.content})
                    # 回复内容也作为 step 发射，让前端按「思考→回复→工具」顺序交错渲染
                    yield _sse_event("step", {"type": "reply", "delta": chunk.content})
                chunk_usage = extract_usage(chunk)
                if chunk_usage:
                    cur = run_usage.setdefault(
                        event.get("run_id", "_"),
                        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                    )
                    cur["input_tokens"] = max(cur["input_tokens"], chunk_usage.get("input_tokens", 0) or 0)
                    cur["output_tokens"] = max(cur["output_tokens"], chunk_usage.get("output_tokens", 0) or 0)
                    cur["total_tokens"] = max(cur["total_tokens"], chunk_usage.get("total_tokens", 0) or 0)

            elif kind == "on_chat_model_end":
                run_id = event.get("run_id", "_")
                output = event.get("data", {}).get("output")
                end_usage = extract_usage(output) if output else {}
                stream_usage = run_usage.pop(run_id, None)
                final = end_usage or stream_usage or None
                if final:
                    # 覆盖为「最近一次 LLM 调用」的用量（非累加）：
                    # input_tokens = 当前上下文大小（系统提示+全部消息+工具定义），
                    # 压缩（SummarizationMiddleware）后下一次调用的 input 回落，
                    # 使前端进度条回到 100% 以内，而非累加消费越过 100% 不回。
                    usage["input_tokens"] = final.get("input_tokens", 0) or 0
                    usage["output_tokens"] = final.get("output_tokens", 0) or 0
                    usage["total_tokens"] = final.get("total_tokens", 0) or 0
                    # reasoning/cache 明细（D5：思考 token 仍计入，仅不落库思考文本）
                    usage["reasoning_tokens"] = final.get("reasoning_tokens", 0) or 0
                    usage["cache_read_tokens"] = final.get("cache_read_tokens", 0) or 0
                    usage["cache_write_tokens"] = final.get("cache_write_tokens", 0) or 0
                # FR-3: 累加本次请求所有 LLM 调用的真实 token（与上方非累加 usage 区分）
                if final:
                    usage_total["input_tokens"] += final.get("input_tokens", 0) or 0
                    usage_total["output_tokens"] += final.get("output_tokens", 0) or 0
                    usage_total["total_tokens"] += final.get("total_tokens", 0) or 0
                    usage_total["cache_read_tokens"] += final.get("cache_read_tokens", 0) or 0
                    usage_total["cache_write_tokens"] += final.get("cache_write_tokens", 0) or 0
                    usage_total["reasoning_tokens"] += final.get("reasoning_tokens", 0) or 0
                else:
                    usage_total["estimated"] = True
                usage_total["llm_calls"] += 1
                pending_reply = None
                thinking_started = False

            elif kind == "on_tool_start":
                thinking_started = False  # 进入工具调用，思考状态结束
                tool_name = event["name"]
                run_id = event.get("run_id", str(len(tool_calls)))
                raw_input = event.get("data", {}).get("input")
                try:
                    json.dumps(raw_input, ensure_ascii=False)
                    tool_input = raw_input
                except (TypeError, ValueError):
                    tool_input = {"raw": str(raw_input)} if raw_input else {}
                tool_step = {
                    "type": "tool",
                    "id": run_id,
                    "name": tool_name,
                    "tool": tool_name,
                    "input": tool_input or {},
                    "output": None,
                    "status": "running",
                }
                steps.append(tool_step)
                _tools_by_run_id[run_id] = tool_step
                tool_calls.append(tool_step)
                # SSE 事件使用截断后的入参，防止单事件超出 nginx 缓冲区
                sse_input = _truncate_tool_input(tool_input or {})
                yield _sse_event("step", {
                    "type": "tool",
                    "id": run_id,
                    "tool": tool_name,
                    "input": sse_input,
                })
                yield _sse_event("tool_start", {
                    "id": run_id,
                    "tool": tool_name,
                    "input": sse_input,
                })

            elif kind == "on_tool_end":
                raw_output = event["data"].get("output", "")
                output_str = _serialize_tool_output(raw_output)
                tool_step = _tools_by_run_id.pop(event.get("run_id"), None)
                if tool_step is not None:
                    tool_id = tool_step["id"]
                    tool_step["output"] = output_str[:2000]
                    tool_step["status"] = "completed"
                    yield _sse_event("step", {
                        "type": "tool_result",
                        "id": tool_id,
                        "tool": event["name"],
                        "data": output_str[:2000],
                    })
                    yield _sse_event("tool_result", {
                        "id": tool_id,
                        "tool": event["name"],
                        "data": output_str[:2000],
                    })
                else:
                    # run_id 匹配不上时不发 id=None 的 tool_result，
                    # 避免前端按 name 回退匹配错误改写其他同名工具的状态
                    logger.warning(
                        f"[Chat] on_tool_end with unmatched run_id: tool={event['name']}"
                    )

        # ---- 流结束：检测 HITL 中断 ----
        approvals = await _detect_interrupts(agent, config)

        if approvals:
            # 中断：保存当前阶段的 assistant 消息（含审批请求状态），等待 /chat/resume。
            # 被中断的工具（如 create_plan_tool）没有 on_tool_end，步骤停留在 running；
            # 统一标记为 interrupted，避免前端在历史里永久显示转圈。
            _mark_stale_tools(steps, "interrupted")
            if full_content or tool_calls:
                await ConversationService.save_message(
                    stream_db, user.id, thread_id, "assistant", full_content,
                    metadata={
                        "tool_calls": tool_calls or None,
                        "steps": steps or None,
                        "approvals": approvals or None,
                        "approval_state": "approval-requested",
                    },
                )
            yield _sse_event("approval_needed", {
                "thread_id": thread_id,
                "action_requests": approvals,
            })
            # DS key 无效已回退：发一次性警示（前端据此清除/标记 localStorage）
            if ds_key_fallback_active(thread_id):
                yield _sse_event("ds_key_invalid", {})
            # 中断态下不发 done（流程未结束），但发 usage 供上下文统计
            if not usage["total_tokens"]:
                usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
            if usage["total_tokens"] > 0:
                yield _sse_event("usage", usage)
                await _upsert_thread_usage(stream_db, user.id, thread_id, usage)
            return

        # ---- 无中断：正常结束，落库 assistant 消息 ----
        # 兜底：未匹配到 on_tool_end 的残留 running 工具统一收尾，防止"执行中"落库
        _mark_stale_tools(steps, "completed")
        if full_content or tool_calls:
            await ConversationService.save_message(
                stream_db, user.id, thread_id, "assistant", full_content,
                metadata={
                    "tool_calls": tool_calls or None,
                    "steps": steps or None,
                    # resume 阶段结束：记录审批已解决（前端据 decisions 已知结果）
                    "approvals": None,
                    "approval_state": "approval-responded" if is_resume else None,
                },
            )

        if not usage["total_tokens"]:
            usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
        if usage["total_tokens"] > 0:
            await _upsert_thread_usage(stream_db, user.id, thread_id, usage)

        yield _sse_event("usage", usage)
        # DS key 无效已回退：发一次性警示（前端据此清除/标记 localStorage）
        if ds_key_fallback_active(thread_id):
            yield _sse_event("ds_key_invalid", {})
        yield _sse_event("done", {"thread_id": thread_id, "tool_calls": tool_calls})
    except Exception as e:
        logger.error(f"[Chat] SSE error: {e}", exc_info=True)
        # 人性化错误文案：GraphRecursionError 单独提示（计划设计死循环 A 类根因），
        # 其余异常脱敏展示（不把原始异常串/路径/密钥泄漏给前端）
        if isinstance(e, GraphRecursionError):
            err_text = "本轮处理超出复杂度上限已终止，请换个说法重试"
        else:
            err_text = f"处理出错（{e.__class__.__name__}），请稍后重试"
        # 落库一条 assistant 兜底消息（错误说明），刷新历史仍可见，不消失
        try:
            await ConversationService.save_message(
                stream_db, user.id, thread_id, "assistant", err_text,
                metadata={
                    # 错误兜底消息**不携带**崩溃残留的 steps/tool_calls：
                    # 前端 StreamSteps 会把崩溃循环产生的多个 reply 步骤渲染成多段
                    # 碎片正文，且 hasReply 为真会抑制兜底错误文案（表现为最新消息
                    # 渲染成 6-7 段乱码正文，真正的错误提示反而不可见）。
                    "error": str(e)[:500],
                },
            )
        except Exception as save_err:
            logger.warning(f"[Chat] Failed to save fallback error message: {save_err}")
        yield _sse_event("error", {"message": err_text})
    finally:
        _log_usage_summary(usage_total, full_content, thread_id, user_id)
        await _upsert_user_token_usage(stream_db, user_id, usage_total)


async def _upsert_thread_usage(stream_db: AsyncSession, user_id, thread_id: str, usage: dict) -> None:
    """覆盖 thread_usage 为「当前上下文大小」（最近一次调用用量），非累加消费：
    压缩后值回落，使前端进度条回到 100% 以内。
    """
    try:
        existing = (await stream_db.execute(
            select(ThreadUsage).where(ThreadUsage.thread_id == thread_id)
        )).scalar_one_or_none()
        if existing:
            existing.total_tokens = usage["total_tokens"]
            existing.input_tokens = usage["input_tokens"]
            existing.output_tokens = usage["output_tokens"]
        else:
            stream_db.add(ThreadUsage(
                user_id=user_id,
                thread_id=thread_id,
                total_tokens=usage["total_tokens"],
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
            ))
        await stream_db.commit()
    except Exception as e:
        logger.warning(f"[Chat] Failed to upsert thread_usage: {e}")


async def _upsert_user_token_usage(stream_db: AsyncSession, user_id, usage_total: dict) -> None:
    """累加本请求 token 到用户级每日流水（source=chat）。

    与 thread_usages 的覆盖式「最近一次上下文大小」区分：这里记录请求内
    所有 LLM 调用真实 usage_metadata 之和（含 estimated 兜底），口径与
    _log_usage_summary 一致，用于用户整体对话的累计用量。
    """
    total = usage_total.get("total_tokens", 0) or 0
    if total <= 0:
        return
    try:
        await UsageService.record(
            stream_db,
            user_id=user_id,
            source="chat",
            input_tokens=usage_total.get("input_tokens", 0) or 0,
            output_tokens=usage_total.get("output_tokens", 0) or 0,
            total_tokens=total,
            llm_calls=usage_total.get("llm_calls", 0) or 0,
            estimated=bool(usage_total.get("estimated", False)),
        )
    except Exception as e:
        logger.warning(f"[Chat] Failed to upsert user_token_usage: {e}")


def _log_usage_summary(
    usage_total: dict, output_text: str, thread_id: str, user_id
) -> None:
    """FR-3: 请求结束时输出一条 token 汇总摘要（累加消费，区别于非累加的 usage）。

    usage_total 为本次请求内所有 LLM 调用真实 usage_metadata 之和（含 cache_read /
    reasoning 拆分）；若全程未回传 usage_metadata 但有输出，则用
    estimate_tokens（count_tokens_approximately）粗估并标记 estimated。
    """
    usage_logger = logging.getLogger("fitcream.usage")
    total = usage_total["total_tokens"]
    estimated = usage_total["estimated"]
    if total == 0 and output_text:
        est_output = estimate_tokens(output_text)
        usage_total["output_tokens"] = est_output
        usage_total["total_tokens"] = est_output
        estimated = True
    usage_logger.info(
        f"token 汇总 | thread={thread_id[:8]} | user={str(user_id)[:8]} | "
        f"input={usage_total['input_tokens']} | output={usage_total['output_tokens']} | "
        f"total={usage_total['total_tokens']} | "
        f"cache_read={usage_total.get('cache_read_tokens', 0)} | "
        f"cache_write={usage_total.get('cache_write_tokens', 0)} | "
        f"reasoning={usage_total.get('reasoning_tokens', 0)} | "
        f"llm_calls={usage_total['llm_calls']} | "
        f"estimated={'true' if estimated else 'false'}"
    )


@router.post("/message")
async def send_message(
    req: ChatRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    发送消息并以 SSE 流式返回 Agent 回复（支持多模态：文本 + 图片）。

    当 req.images 不为空时，构建 OpenAI 兼容的多模态 content blocks，
    适配 DashScope Qwen-VL 接口。图片支持 URL 和 base64 data URL 两种格式。

    SSE 事件类型：
    - start: 流式开始，返回 thread_id
    - token: 正式回复 token
    - tool_start: Tool 调用开始
    - tool_result: Tool 调用结果
    - approval_needed: HITL 中断，前端弹出审批卡片（含 action_requests）
    - done: 对话结束
    - stopped: 用户手动停止
    - error: 错误
    """
    thread_id = str(uuid4()) if req.plan_design else (req.thread_id or str(uuid4()))
    user_id_str = str(user.id)
    request.state.user_id = user_id_str

    # 线程归属校验：指定已有线程时必须是当前用户所有，防跨用户注入
    # （plan_design 为全新线程，跳过校验）
    if req.thread_id and not req.plan_design and await ConversationService.thread_is_foreign(db, user.id, thread_id):
        raise ForbiddenException("无权访问该线程")

    # plan_design：标记线程 agent_mode，后续 message/resume 按此识别计划设计会话
    if req.plan_design:
        await ConversationService.upsert_thread_agent_mode(db, user.id, thread_id, "plan_design")

    # 保存用户消息（文本内容 + 图片 URL 列表记录到 metadata，供前端历史渲染）
    user_msg_text = req.message or "[图片消息]"
    user_msg_metadata = {"images": list(req.images)} if req.images else None
    await ConversationService.save_message(db, user.id, thread_id, "user", user_msg_text, metadata=user_msg_metadata)

    # plan_design 门控：完整 plan-execute 计划设计流程只允许按钮进入的会话触发。
    # 首条消息（req.plan_design=true）或已有线程 agent_mode=plan_design 的后续消息
    # 都视为计划设计会话（写入 configurable.plan_design 供 RequestGateMiddleware 读取）。
    is_plan_design = bool(req.plan_design)
    if not is_plan_design and req.thread_id:
        mode = await ConversationService.get_thread_agent_mode(db, thread_id)
        is_plan_design = mode == "plan_design"

    # 解析 agent：统一走默认 graph（ModelRoutingMiddleware 按 deepseek_api_key 切模型）。
    # plan_design 仅作为线程标记保留（ThreadMeta.agent_mode），不再承载模型路由。
    agent = _get_agent()
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id_str,
            "plan_design": is_plan_design,
        },
        "recursion_limit": 100,
    }
    _inject_request_config(config, req)

    # 清理 checkpoint 中过期的 OSS 签名图片 URL（已无法被模型读取，避免浪费 token）；
    # 统一 qwen3.8-flash / deepseek 视觉模型均支持多模态，不再强剥图片
    await _clean_expired_image_urls(getattr(agent, "checkpointer", None), thread_id)
    # 修复 checkpoint 中悬空的 tool_calls（缺 ToolMessage 响应）：
    # 崩溃残留会导致 DeepSeek resume/续聊 400（Bug B1），先修复再进流
    await _repair_dangling_tool_calls(getattr(agent, "checkpointer", None), thread_id)

    # 构建动态上下文注入到对话首条消息之前
    context_msg = await _build_user_context(user)

    # 构建用户消息内容（支持多模态：文本 + 图片）
    # 使用 OpenAI 兼容格式，适配 DashScope Qwen-VL 接口
    if req.images:
        user_content: list[dict] = []
        if req.message:
            user_content.append({"type": "text", "text": req.message})
        else:
            user_content.append({"type": "text", "text": "请分析这张/这些图片"})
        for img_url in req.images:
            user_content.append({"type": "image_url", "image_url": {"url": img_url}})
    else:
        user_content = req.message  # type: ignore

    input_msg = {
        "messages": [
            {"role": "system", "content": context_msg},
            {"role": "user", "content": user_content},
        ]
    }

    # 创建停止事件
    stop_event = asyncio.Event()
    _active_streams[thread_id] = stop_event

    async def event_stream():
        """SSE 流式生成器：委托共享 runner（含 HITL 中断检测与落库）"""
        async with async_session_factory() as stream_db:
            ctx_tokens = set_user_context(user_id=user_id_str, thread_id=thread_id)
            try:
                async for sse in _run_agent_sse(
                    agent, config, input_msg,
                    thread_id=thread_id, user_id=user_id_str, user=user,
                    stop_event=stop_event, stream_db=stream_db, is_resume=False,
                ):
                    yield sse
            finally:
                _active_streams.pop(thread_id, None)
                reset_user_context(ctx_tokens)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/resume")
async def resume_conversation(
    req: ResumeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    恢复被 HITL 中断的对话（用户对计划操作做了审批决策）。

    入参 thread_id + decisions（approve/reject，reject 可带 reason 作为修订稿）。
    复用同一 SSE 流式逻辑转发 token/tool 事件，结束后落库 assistant 消息。
    若 reject 带修订稿，agent 会重新提案并可能再次中断（发新的 approval_needed）。

    SSE 事件类型同 /chat/message，额外：
    - approval_needed: 恢复后再次中断时（如 reject 后重新提案）
    - done: 审批流程结束（approve 落库完成 / reject 终结）
    """
    thread_id = req.thread_id
    user_id_str = str(user.id)
    request.state.user_id = user_id_str

    # 线程归属校验：必须是当前用户的线程
    if await ConversationService.thread_is_foreign(db, user.id, thread_id):
        raise ForbiddenException("无权访问该线程")

    # 按统一 graph 路由（ModelRoutingMiddleware 按 deepseek_api_key 切模型）；
    # 同一 checkpointer + 相同 graph 结构，resume 安全。
    # plan_design 门控：resume 属于计划设计审批流程，按线程 agent_mode 识别并写入 configurable。
    mode = await ConversationService.get_thread_agent_mode(db, thread_id)
    agent = _get_agent()
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id_str,
            "plan_design": mode == "plan_design",
        },
        "recursion_limit": 100,
    }
    _inject_request_config(config, req)
    await _clean_expired_image_urls(getattr(agent, "checkpointer", None), thread_id)
    # 注意：resume 前绝不可做悬空修复！待审批中断的 AIMessage.tool_calls 天然
    # 缺 ToolMessage 响应（属合法的 pending 状态），修复会给它追加「未执行」合成
    # ToolMessage + 改写 messages channel，导致被审批的工具节点被跳过、真实落库
    # 不发生（roadmap/plan 审批死循环事故）。历史真悬空由下一条 /message 修复。

    # 构建 resume 命令（decisions 顺序须与 approval_needed 的 action_requests 对齐）
    resume_command = _build_resume_command(req.decisions)

    stop_event = asyncio.Event()
    _active_streams[thread_id] = stop_event

    async def event_stream():
        """SSE 流式生成器：恢复中断并续流"""
        async with async_session_factory() as stream_db:
            ctx_tokens = set_user_context(user_id=user_id_str, thread_id=thread_id)
            try:
                async for sse in _run_agent_sse(
                    agent, config, resume_command,
                    thread_id=thread_id, user_id=user_id_str, user=user,
                    stop_event=stop_event, stream_db=stream_db, is_resume=True,
                ):
                    yield sse
            finally:
                _active_streams.pop(thread_id, None)
                reset_user_context(ctx_tokens)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/verify-deepseek-key", response_model=ResponseModel[dict])
async def verify_deepseek_key(
    req: VerifyDeepSeekKeyIn,
    user: User = Depends(get_current_user),
):
    """
    校验用户自备 DeepSeek API Key 有效性（个人中心保存前调用）。

    用该 key 对 DeepSeek 官方端点做一次最小调用（max_tokens=1 文本），
    成功返回 ``{valid: true}``，失败返回 ``{valid: false, error}``。
    不落库、不记日志明文；key 仅随请求体到达本端点，不入 checkpoint。
    """
    key = req.deepseek_api_key.strip()
    try:
        llm = create_deepseek_vision(api_key=key, max_tokens=1)
        await llm.ainvoke([("human", "hi")])
        return ResponseModel(data={"valid": True})
    except Exception as e:
        logger.info("[Chat] verify-deepseek-key 校验失败: %s", e.__class__.__name__)
        return ResponseModel(data={"valid": False, "error": str(e)[:200]})


@router.post("/stop", response_model=ResponseModel[None])
async def stop_generation(
    req: StopRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    停止指定线程的 AI 生成。

    前端在用户点击"停止生成"按钮时调用此接口。
    """
    # 线程归属校验：已存在的线程必须属于当前用户，防越权停止他人会话
    if await ConversationService.thread_is_foreign(db, user.id, req.thread_id):
        raise ForbiddenException("无权停止该线程")

    stop_event = _active_streams.get(req.thread_id)
    if stop_event:
        stop_event.set()
        return ResponseModel(message="已发送停止信号")
    return ResponseModel(code=404, message="未找到活跃的生成任务")


# ============================================================
# 图片上传
# ============================================================

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
}
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _to_data_url(content: bytes, mime: str) -> str:
    """将图片字节转为 base64 data URL（OSS 未配置时的开发模式回退）。"""
    b64 = base64.b64encode(content).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _strip_image_metadata(content: bytes, mime: str) -> bytes:
    """剥离图片 EXIF 等元数据（照片常携带 GPS 位置、设备信息等隐私），GIF 无 EXIF 直接返回。

    使用 Pillow 重新编码并丢弃全部元数据；解析失败时保留原内容。
    """
    if mime == "image/gif":
        return content
    try:
        from io import BytesIO

        from PIL import Image

        fmt = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
        }.get(mime, "JPEG")
        img = Image.open(BytesIO(content))
        img.load()
        img.info.clear()
        if fmt == "JPEG" and img.mode in ("RGBA", "LA", "P", "PA"):
            img = img.convert("RGB")
        buf = BytesIO()
        if fmt == "JPEG":
            img.save(buf, fmt, quality=90)
        else:
            img.save(buf, fmt)
        return buf.getvalue()
    except Exception:
        logger.warning("EXIF 剥离失败，保留原图: %s", mime)
        return content


@router.post("/upload-image", response_model=ResponseModel[dict])
async def upload_image(
    file: UploadFile = File(..., description="图片文件（jpg/png/webp/gif，最大 10MB）"),
    thread_id: Optional[str] = Form(None, description="所属对话线程 ID（可选）"),
    user: User = Depends(get_current_user),
):
    """
    上传图片到阿里云 OSS（私有路径），返回长期有效签名的 URL 供 ChatRequest.images 使用。

    OSS 未配置时（开发模式）回退为 base64 data URL。
    前端上传图片后，将返回的 url 放入 ChatRequest.images 数组即可发送多模态消息。
    传入 thread_id 时图片归入 chat/{user_id}/{thread_id}/ 目录，便于按会话管理。
    """
    # 校验文件类型
    ext = ("." + file.filename.rsplit(".", 1)[-1].lower()) if file.filename and "." in file.filename else ""
    if file.content_type not in ALLOWED_IMAGE_TYPES and ext not in ALLOWED_IMAGE_EXTS:
        return ResponseModel(code=400, message=f"不支持的图片格式：{file.content_type or ext}，仅支持 jpg/png/webp/gif")

    # 读取文件内容并校验大小
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        return ResponseModel(code=400, message=f"图片大小超过限制（最大 {MAX_IMAGE_SIZE // 1024 // 1024}MB）")

    mime = file.content_type or "image/jpeg"

    # 上传前剥离 EXIF 等元数据（照片常携带 GPS 位置、设备信息等隐私）
    content = _strip_image_metadata(content, mime)

    # 优先上传 OSS 返回签名 URL；未配置或上传失败时回退 base64 data URL
    if is_oss_configured():
        try:
            url = upload_chat_image(content, user.id, content_type=mime, thread_id=thread_id)
        except Exception:
            logger.exception("OSS 上传失败，回退 base64 data URL")
            url = _to_data_url(content, mime)
    else:
        url = _to_data_url(content, mime)

    return ResponseModel(
        message="上传成功",
        data={
            "url": url,
            "filename": file.filename or "upload.jpg",
            "size": len(content),
            "mime_type": mime,
            "thread_id": thread_id,
        },
    )


@router.get("/threads", response_model=ResponseModel[list[ThreadOut]])
async def list_threads(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的对话线程列表"""
    rows = await ConversationService.aggregate_threads(db, user.id, page, size)

    # 批量查询 thread_usage
    thread_ids = [row.thread_id for row in rows]
    usage_map: dict[str, int] = {}
    title_map: dict[str, str] = {}
    mode_map: dict[str, str] = {}
    if thread_ids:
        usage_stmt = select(ThreadUsage.thread_id, ThreadUsage.total_tokens).where(
            ThreadUsage.thread_id.in_(thread_ids)
        )
        usage_rows = (await db.execute(usage_stmt)).all()
        usage_map = {r.thread_id: r.total_tokens for r in usage_rows}

        meta_stmt = select(
            ThreadMeta.thread_id, ThreadMeta.title, ThreadMeta.agent_mode
        ).where(ThreadMeta.thread_id.in_(thread_ids))
        meta_rows = (await db.execute(meta_stmt)).all()
        for r in meta_rows:
            if r.title:
                title_map[r.thread_id] = r.title
            if r.agent_mode:
                mode_map[r.thread_id] = r.agent_mode

    threads = []
    for row in rows:
        last_content = await ConversationService.get_last_assistant_content(
            db, user.id, row.thread_id
        )

        threads.append(ThreadOut(
            thread_id=row.thread_id,
            title=title_map.get(row.thread_id),
            last_message=(last_content[:100] if last_content else None),
            message_count=row.message_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
            total_tokens=usage_map.get(row.thread_id, 0),
            agent_mode=mode_map.get(row.thread_id),
        ))

    return ResponseModel(data=threads)


@router.get("/threads/{thread_id}/messages", response_model=ResponseModel[ThreadMessagesOut])
async def get_thread_messages(
    thread_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定线程的消息列表"""
    messages, total = await ConversationService.get_messages(
        db, user.id, thread_id, page, size
    )

    return ResponseModel(data=ThreadMessagesOut(
        thread_id=thread_id,
        messages=[MessageOut.model_validate(m) for m in messages],
        total=total,
    ))


@router.patch("/threads/{thread_id}/title", response_model=ResponseModel[ThreadOut])
async def update_thread_title(
    thread_id: str,
    req: ThreadTitleIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新对话线程的自定义标题（用户可编辑会话记录名称）。

    采用 upsert 语义：若 ThreadMeta 不存在则创建，存在则更新标题。
    仅允许线程所有者操作；线程需归属当前用户（校验存在至少一条消息）。
    """
    # 校验线程归属当前用户
    owns = await ConversationService.count_thread_messages(db, user.id, thread_id)
    if owns == 0:
        return ResponseModel(code=404, message="线程不存在")

    meta = (
        await db.execute(
            select(ThreadMeta).where(ThreadMeta.thread_id == thread_id)
        )
    ).scalar_one_or_none()

    if meta is None:
        meta = ThreadMeta(
            user_id=user.id,
            thread_id=thread_id,
            title=req.title.strip(),
        )
        db.add(meta)
    else:
        meta.title = req.title.strip()
    await db.commit()
    await db.refresh(meta)

    return ResponseModel(
        message="标题已更新",
        data=ThreadOut(
            thread_id=thread_id,
            title=meta.title,
        ),
    )


@router.delete("/threads/{thread_id}", response_model=ResponseModel[None])
async def delete_thread(
    thread_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定线程的所有消息"""
    deleted = await ConversationService.delete_by_thread(db, user.id, thread_id)
    # 同步清理线程元信息与 token 用量，避免删除后残留孤立记录（幽灵 token）
    await db.execute(
        delete(ThreadMeta).where(ThreadMeta.thread_id == thread_id)
    )
    await db.execute(
        delete(ThreadUsage).where(ThreadUsage.thread_id == thread_id)
    )
    await db.commit()

    if deleted == 0:
        return ResponseModel(code=404, message="线程不存在")

    return ResponseModel(message=f"已删除 {deleted} 条消息")

@router.delete("/history", response_model=ResponseModel[None])
async def clear_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清空当前用户的所有对话历史"""
    deleted = await ConversationService.clear_by_user(db, user.id)
    # 同步清理该用户所有线程元信息与 token 用量，避免残留孤立记录（幽灵 token）
    await db.execute(
        delete(ThreadMeta).where(ThreadMeta.user_id == user.id)
    )
    await db.execute(
        delete(ThreadUsage).where(ThreadUsage.user_id == user.id)
    )
    await db.commit()

    return ResponseModel(message=f"已清空 {deleted} 条消息")
