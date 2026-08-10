"""对话路由 /api/chat/* - 流式对话 + Thread CRUD + 图片上传"""
import asyncio
import base64
import json
import logging
import time
from datetime import date
from typing import Dict, Optional
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.dependencies import get_current_user
from src.agents.harness.runtime.conversation_service import ConversationService
from src.agents.models.thread_meta import ThreadMeta
from src.agents.models.thread_usage import ThreadUsage
from src.fitme.models.user import User
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


def _get_agent():
    from src.agents.agent_graph import get_agent
    return get_agent()


async def _resolve_agent(
    db: AsyncSession, thread_id: str, plan_design: bool, has_images: bool = False
) -> tuple:
    """按线程 agent_mode 解析 Agent 实例（路由 chokepoint）。

    返回 ``(agent, is_non_vision)``：
    - plan_design 请求直接路由到计划设计 graph；否则按 ThreadMeta.agent_mode 路由
      （缺失 -> 默认 graph）。
    - 图片例外：deepseek（计划设计模型）不支持视觉，plan_design 线程收到图片时
      改走默认 qwen 图（qwen3.7-flash，已验证可处理多模态）。
    - ``is_non_vision=True`` 表示本轮路由到 deepseek（不支持视觉），调用方应把历史中的
      image_url 替换为占位文本，避免非视觉模型收到无法处理的图片块。
    """
    from src.agents.agent_graph import get_agent_by_mode

    if plan_design:
        if has_images:
            logger.info(f"[Chat] plan_design 线程收到图片，改用默认 qwen 图 | thread={thread_id[:8]}")
            return get_agent_by_mode(None), False
        return get_agent_by_mode("plan_design"), True
    mode = await ConversationService.get_thread_agent_mode(db, thread_id)
    if mode == "plan_design" and has_images:
        logger.info(f"[Chat] plan_design 线程收到图片，改用默认 qwen 图 | thread={thread_id[:8]}")
        return get_agent_by_mode(None), False
    if mode == "plan_design":
        return get_agent_by_mode("plan_design"), True
    return get_agent_by_mode(mode), False


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


async def _clean_expired_image_urls(checkpointer, thread_id: str, force_strip: bool = False) -> None:
    """Agent 发送前清理 checkpoint 中的多模态 image_url。

    - 默认：仅替换已过期的 OSS 签名 URL（已无法被模型读取）为占位文本，
      避免每轮重复发送无效图片浪费 token。
    - ``force_strip=True``：替换**所有** image_url（不论是否过期）为占位文本，
      供非视觉模型（如 deepseek 计划设计模型）使用--图片已由 qwen 在上一轮分析完毕，
      非视觉模型用不上且无法处理图片块。无修改则不写 checkpoint。
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
            if force_strip or (url and _image_url_expired(url)):
                block["type"] = "text"
                block["text"] = "[图片已分析完毕]"
                modified = True
    if modified:
        try:
            new_versions = checkpoint.get("channel_versions") or {}
            await checkpointer.aput(tup.config, checkpoint, tup.metadata, new_versions)
            logger.info(f"[Chat] Cleaned expired image_urls | thread={thread_id[:8]}")
        except Exception as e:
            logger.warning(f"[Chat] aput failed: {e}")


async def _build_user_context(user: User) -> str:
    """构建用户动态上下文（精简版）：仅注入当前日期与用户称呼。

    此前每轮会查询 goal/BMI/streak/active plan 并作为 SystemMessage 注入，
    这些数据随 checkpointer 累积在历史中、逐轮重复消耗 token。用户目标 / 身体
    数据 / 打卡 / 计划均可通过 get_user_profile_tool / get_streak_tool /
    list_plans_tool 等按需获取，故不再每轮注入，仅在需要时由模型主动调用工具。
    """
    parts = [f"- 当前日期：{date.today().isoformat()}"]
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
    yield _sse_event("start", {"thread_id": thread_id})

    full_content = ""        # 累积正式回复文本（本阶段）
    full_thinking = ""       # 累积思考内容
    tool_calls = []          # 完整工具调用记录 [{id, name, input, output, status}]
    steps: list[dict] = []   # ReAct 步骤序列
    pending_thought: Optional[dict] = None
    pending_reply: Optional[dict] = None
    _current_tool: Optional[dict] = None
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    run_usage: dict[str, dict[str, int]] = {}
    # FR-3: 请求级累加 token（区别于非累加的 usage「最近一次上下文大小」）
    usage_total = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "llm_calls": 0,
        "estimated": False,
    }
    output_chars = 0

    try:
        async for event in agent.astream_events(input_or_command, config=config, version="v2"):
            if stop_event.is_set():
                if full_content or full_thinking:
                    await ConversationService.save_message(
                        stream_db, user.id, thread_id, "assistant", full_content,
                        metadata={
                            "thinking": full_thinking or None,
                            "tool_calls": tool_calls or None,
                            "steps": steps or None,
                            "stopped": True,
                        },
                    )
                yield _sse_event("stopped", {"thread_id": thread_id, "partial_content": full_content})
                return

            kind = event["event"]

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                reasoning = chunk.additional_kwargs.get("reasoning_content", "")
                if reasoning:
                    if pending_thought is None:
                        pending_thought = {"type": "thought", "content": ""}
                        steps.append(pending_thought)
                    pending_thought["content"] += reasoning
                    full_thinking += reasoning
                    yield _sse_event("thinking", {"content": reasoning})
                    yield _sse_event("step", {"type": "thought", "delta": reasoning})
                if chunk.content:
                    if pending_reply is None:
                        pending_reply = {"type": "reply", "content": ""}
                        steps.append(pending_reply)
                    pending_reply["content"] += chunk.content
                    full_content += chunk.content
                    output_chars += len(chunk.content)
                    yield _sse_event("token", {"content": chunk.content})
                    # 回复内容也作为 step 发射，让前端按「思考→回复→工具」顺序交错渲染
                    yield _sse_event("step", {"type": "reply", "delta": chunk.content})
                chunk_usage = getattr(chunk, "usage_metadata", None) or {}
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
                end_usage = getattr(output, "usage_metadata", None) if output else None
                stream_usage = run_usage.pop(run_id, None)
                final = end_usage or stream_usage
                if final:
                    # 覆盖为「最近一次 LLM 调用」的用量（非累加）：
                    # input_tokens = 当前上下文大小（系统提示+全部消息+工具定义），
                    # 压缩（SummarizationMiddleware）后下一次调用的 input 回落，
                    # 使前端进度条回到 100% 以内，而非累加消费越过 100% 不回。
                    usage["input_tokens"] = final.get("input_tokens", 0) or 0
                    usage["output_tokens"] = final.get("output_tokens", 0) or 0
                    usage["total_tokens"] = final.get("total_tokens", 0) or 0
                # FR-3: 累加本次请求所有 LLM 调用的真实 token（与上方非累加 usage 区分）
                if final:
                    usage_total["input_tokens"] += final.get("input_tokens", 0) or 0
                    usage_total["output_tokens"] += final.get("output_tokens", 0) or 0
                    usage_total["total_tokens"] += final.get("total_tokens", 0) or 0
                else:
                    usage_total["estimated"] = True
                usage_total["llm_calls"] += 1
                pending_thought = None
                pending_reply = None

            elif kind == "on_tool_start":
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
                _current_tool = tool_step
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
                if isinstance(raw_output, str):
                    output_str = raw_output
                else:
                    try:
                        output_str = json.dumps(raw_output, ensure_ascii=False)
                    except (TypeError, ValueError):
                        output_str = str(raw_output)
                tool_id = None
                if _current_tool is not None:
                    tool_id = _current_tool["id"]
                    _current_tool["output"] = output_str[:2000]
                    _current_tool["status"] = "completed"
                    yield _sse_event("step", {
                        "type": "tool_result",
                        "id": tool_id,
                        "tool": event["name"],
                        "data": output_str[:2000],
                    })
                    _current_tool = None
                yield _sse_event("tool_result", {
                    "id": tool_id,
                    "tool": event["name"],
                    "data": output_str[:2000],
                })

        # ---- 流结束：检测 HITL 中断 ----
        approvals = await _detect_interrupts(agent, config)

        if approvals:
            # 中断：保存当前阶段的 assistant 消息（含审批请求状态），等待 /chat/resume
            if full_content or full_thinking or tool_calls:
                await ConversationService.save_message(
                    stream_db, user.id, thread_id, "assistant", full_content,
                    metadata={
                        "thinking": full_thinking or None,
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
            # 中断态下不发 done（流程未结束），但发 usage 供上下文统计
            if not usage["total_tokens"]:
                usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
            if usage["total_tokens"] > 0:
                yield _sse_event("usage", usage)
                await _upsert_thread_usage(stream_db, user.id, thread_id, usage)
            return

        # ---- 无中断：正常结束，落库 assistant 消息 ----
        if full_content or full_thinking:
            await ConversationService.save_message(
                stream_db, user.id, thread_id, "assistant", full_content,
                metadata={
                    "thinking": full_thinking or None,
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
        yield _sse_event("done", {"thread_id": thread_id, "tool_calls": tool_calls})
    except Exception as e:
        logger.error(f"[Chat] SSE error: {e}", exc_info=True)
        yield _sse_event("error", {"message": str(e)})
    finally:
        _log_usage_summary(usage_total, output_chars, thread_id, user_id)


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


def _log_usage_summary(
    usage_total: dict, output_chars: int, thread_id: str, user_id
) -> None:
    """FR-3: 请求结束时输出一条 token 汇总摘要（累加消费，区别于非累加的 usage）。

    usage_total 为本次请求内所有 LLM 调用真实 usage_metadata 之和；若全程未
    回传 usage_metadata 但有输出，则按输出字符粗估并标记 estimated。
    """
    usage_logger = logging.getLogger("fitcream.usage")
    total = usage_total["total_tokens"]
    estimated = usage_total["estimated"]
    if total == 0 and output_chars > 0:
        est_output = max(1, output_chars // 2)
        usage_total["output_tokens"] = est_output
        usage_total["total_tokens"] = est_output
        estimated = True
    usage_logger.info(
        f"token 汇总 | thread={thread_id[:8]} | user={str(user_id)[:8]} | "
        f"input={usage_total['input_tokens']} | output={usage_total['output_tokens']} | "
        f"total={usage_total['total_tokens']} | llm_calls={usage_total['llm_calls']} | "
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
    - thinking: 模型思考内容（reasoning_content）
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

    # plan_design：标记线程 agent_mode，后续 message/resume 按此路由到计划设计模型
    if req.plan_design:
        await ConversationService.upsert_thread_agent_mode(db, user.id, thread_id, "plan_design")

    # 保存用户消息（文本内容 + 图片 URL 列表记录到 metadata，供前端历史渲染）
    user_msg_text = req.message or "[图片消息]"
    user_msg_metadata = {"images": list(req.images)} if req.images else None
    await ConversationService.save_message(db, user.id, thread_id, "user", user_msg_text, metadata=user_msg_metadata)

    # 解析 agent：plan_design 请求或按线程已记录的 agent_mode 路由；
    # plan_design 线程的图片消息改走默认 qwen 图（deepseek 不支持视觉）。
    # is_non_vision=True 表示本轮路由到 deepseek，需强制剥离历史图片为占位文本。
    agent, is_non_vision = await _resolve_agent(db, thread_id, req.plan_design, has_images=bool(req.images))
    config = {
        "configurable": {"thread_id": thread_id, "user_id": user_id_str},
        "recursion_limit": 100,
    }

    # 清理 checkpoint 中的图片：过期的 OSS 签名 URL 一律替换为占位文本；
    # 路由到 deepseek（非视觉）时强制剥离所有 image_url（已由 qwen 分析完毕，deepseek 用不上）
    await _clean_expired_image_urls(getattr(agent, "checkpointer", None), thread_id, force_strip=is_non_vision)

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

    # 按线程 agent_mode 路由（plan_design 线程续流仍走计划设计模型；
    # 同一 checkpointer + 相同 graph 结构，resume 安全）。
    # is_non_vision=True 时（路由到 deepseek）强制剥离历史图片，避免非视觉模型收到图片块
    agent, is_non_vision = await _resolve_agent(db, thread_id, False)
    config = {
        "configurable": {"thread_id": thread_id, "user_id": user_id_str},
        "recursion_limit": 100,
    }
    await _clean_expired_image_urls(getattr(agent, "checkpointer", None), thread_id, force_strip=is_non_vision)

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
