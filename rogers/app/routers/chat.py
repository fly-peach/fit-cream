"""对话路由 /api/chat/* - 流式对话 + Thread CRUD + 图片上传"""
import asyncio
import base64
import json
import logging
from datetime import date
from typing import Dict, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.dependencies import get_current_user
from src.fitme.models.conversation import Conversation
from src.fitme.models.thread_meta import ThreadMeta
from src.fitme.models.thread_usage import ThreadUsage
from src.fitme.models.user import User
from src.fitme.schemas.chat import (
    ChatRequest,
    MessageOut,
    ThreadMessagesOut,
    ThreadOut,
    ThreadTitleIn,
)
from src.fitme.schemas.common import ResponseModel

logger = logging.getLogger("fitcream.chat")

router = APIRouter(prefix="/chat", tags=["chat"])

# 存储活跃的流式任务，用于停止生成
# key: thread_id, value: asyncio.Event（set() 后流式生成器检测到并终止）
_active_streams: Dict[str, asyncio.Event] = {}


def _get_agent():
    from src.agents.agent_graph import get_agent
    return get_agent()


async def _build_user_context(user: User) -> str:
    """构建用户动态上下文字符串，注入到对话输入中"""
    from app.database import async_session_factory
    from src.fitme.services.checkin_service import CheckinService
    from src.fitme.services.plan_service import PlanService
    from src.fitme.services.user_service import UserService

    parts = [f"- 当前日期：{date.today().isoformat()}"]
    parts.append(f"- 用户称呼：{user.name or '用户'}")

    try:
        async with async_session_factory() as db:
            # 获取用户设置
            settings = await UserService.get_user_settings(db, user.id)
            if settings.goal:
                goal_map = {
                    "lose_fat": "减脂", "gain_muscle": "增肌",
                    "maintain": "维持体型", "improve_health": "改善健康",
                }
                parts.append(f"- 用户目标：{goal_map.get(settings.goal, settings.goal)}")

            # 获取最新健康指标
            latest_metric = await UserService.get_latest_health_metric(db, user.id)
            if latest_metric and latest_metric.height_cm and latest_metric.weight_kg:
                bmi = latest_metric.weight_kg / ((latest_metric.height_cm / 100) ** 2)
                parts.append(f"- 身体数据：{latest_metric.height_cm}cm / {latest_metric.weight_kg}kg")
                bmi_text = "偏瘦" if bmi < 18.5 else "正常" if bmi < 24 else "偏胖" if bmi < 28 else "肥胖"
                parts.append(f"- BMI：{bmi:.1f}（{bmi_text}）")

            # 获取打卡 streak 和计划
            streak = await CheckinService.get_streak(db, user.id)
            if streak.get("current_streak"):
                parts.append(f"- 当前连续打卡：{streak['current_streak']} 天")
            plan, _ = await PlanService.list_plans(db, user.id, page=1, size=1, status="active")
            if plan:
                parts.append(f"- 当前活跃计划：{plan[0].name}（第 {plan[0].weeks} 周计划）")
    except Exception:
        pass

    return "# 当前对话上下文\n" + "\n".join(parts)


async def _save_message(
    db: AsyncSession,
    user_id: UUID,
    thread_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
) -> Conversation:
    msg = Conversation(
        id=uuid4(),
        user_id=user_id,
        thread_id=thread_id,
        role=role,
        content=content,
        metadata_json=metadata,
    )
    db.add(msg)
    await db.commit()
    return msg


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class StopRequest(BaseModel):
    """停止生成请求"""
    thread_id: str

@router.post("/message")
async def send_message(
    req: ChatRequest,
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
    - done: 对话结束
    - stopped: 用户手动停止
    - error: 错误
    """
    thread_id = req.thread_id or str(uuid4())
    user_id_str = str(user.id)

    # 保存用户消息（文本内容 + 图片数量记录到 metadata）
    user_msg_text = req.message or "[图片消息]"
    user_msg_metadata = {"images": len(req.images)} if req.images else None
    await _save_message(db, user.id, thread_id, "user", user_msg_text, metadata=user_msg_metadata)

    agent = _get_agent()
    config = {
        "configurable": {"thread_id": thread_id, "user_id": user_id_str},
        "recursion_limit": 50,
    }

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
        """SSE 流式生成器：逐 token 转发 Agent 回复"""
        yield _sse_event("start", {"thread_id": thread_id})

        full_content = ""       # 累积正式回复文本
        full_thinking = ""     # 累积思考内容（reasoning_content）
        tool_calls = []         # 完整工具调用记录 [{id, name, input, output, status}]
        _current_tool: Optional[dict] = None
        # Token 使用量追踪（部分模型仅在最终 chunk 返回 usage_metadata）
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        # 使用独立 session，避免请求级 session 在流式响应期间被关闭
        async with async_session_factory() as stream_db:
            try:
                async for event in agent.astream_events(input_msg, config=config, version="v2"):
                    # 检查是否需要停止
                    if stop_event.is_set():
                        if full_content or full_thinking:
                            await _save_message(
                                stream_db, user.id, thread_id, "assistant", full_content,
                                metadata={
                                    "thinking": full_thinking or None,
                                    "tool_calls": tool_calls or None,
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
                            full_thinking += reasoning
                            yield _sse_event("thinking", {"content": reasoning})
                        if chunk.content:
                            full_content += chunk.content
                            yield _sse_event("token", {"content": chunk.content})
                        # 累积 token 使用量（部分模型仅在最终 chunk 返回 usage_metadata）
                        chunk_usage = getattr(chunk, "usage_metadata", None) or {}
                        if chunk_usage:
                            usage["input_tokens"] = max(
                                usage["input_tokens"], chunk_usage.get("input_tokens", 0) or 0
                            )
                            usage["output_tokens"] = max(
                                usage["output_tokens"], chunk_usage.get("output_tokens", 0) or 0
                            )
                            usage["total_tokens"] = max(
                                usage["total_tokens"], chunk_usage.get("total_tokens", 0) or 0
                            )

                    elif kind == "on_chat_model_end":
                        # 部分模型仅在 end 事件的 output 中返回 usage_metadata
                        output = event.get("data", {}).get("output")
                        end_usage = getattr(output, "usage_metadata", None) if output else None
                        if end_usage:
                            usage["input_tokens"] = max(
                                usage["input_tokens"],
                                end_usage.get("input_tokens", 0) or 0,
                            )
                            usage["output_tokens"] = max(
                                usage["output_tokens"],
                                end_usage.get("output_tokens", 0) or 0,
                            )
                            usage["total_tokens"] = max(
                                usage["total_tokens"],
                                end_usage.get("total_tokens", 0) or 0,
                            )

                    elif kind == "on_tool_start":
                        tool_name = event["name"]
                        run_id = event.get("run_id", str(len(tool_calls)))
                        # 透传工具入参，便于前端展示真实参数
                        raw_input = event.get("data", {}).get("input")
                        try:
                            json.dumps(raw_input, ensure_ascii=False)
                            tool_input = raw_input
                        except (TypeError, ValueError):
                            tool_input = {"raw": str(raw_input)} if raw_input else {}
                        _current_tool = {
                            "id": run_id,
                            "name": tool_name,
                            "input": tool_input or {},
                            "output": None,
                            "status": "running",
                            "thinking_offset": len(full_thinking),
                        }
                        tool_calls.append(_current_tool)
                        yield _sse_event("tool_start", {
                            "id": run_id,
                            "tool": tool_name,
                            "input": tool_input or {},
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
                        # 更新当前工具调用状态，并记录其 id 以便前端精确匹配
                        tool_id = None
                        if _current_tool is not None:
                            tool_id = _current_tool["id"]
                            _current_tool["output"] = output_str[:2000]
                            _current_tool["status"] = "completed"
                            _current_tool = None
                        yield _sse_event("tool_result", {
                            "id": tool_id,
                            "tool": event["name"],
                            "data": output_str[:2000],
                        })

                if full_content or full_thinking:
                    await _save_message(
                        stream_db, user.id, thread_id, "assistant", full_content,
                        metadata={
                            "thinking": full_thinking or None,
                            "tool_calls": tool_calls or None,
                        },
                    )

                # 若 total 缺失则用 input+output 兜底
                if not usage["total_tokens"]:
                    usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]

                # Upsert thread_usage 到数据库（累加模式，记录对话总 token 消耗）
                if usage["total_tokens"] > 0:
                    try:
                        from sqlalchemy import select as sa_select
                        existing = (await stream_db.execute(
                            sa_select(ThreadUsage).where(ThreadUsage.thread_id == thread_id)
                        )).scalar_one_or_none()
                        if existing:
                            existing.total_tokens += usage["total_tokens"]
                            existing.input_tokens += usage["input_tokens"]
                            existing.output_tokens += usage["output_tokens"]
                        else:
                            stream_db.add(ThreadUsage(
                                user_id=user.id,
                                thread_id=thread_id,
                                total_tokens=usage["total_tokens"],
                                input_tokens=usage["input_tokens"],
                                output_tokens=usage["output_tokens"],
                            ))
                        await stream_db.commit()
                    except Exception as e:
                        logger.warning(f"[Chat] Failed to upsert thread_usage: {e}")

                yield _sse_event("usage", usage)
                yield _sse_event("done", {"thread_id": thread_id, "tool_calls": tool_calls})

            except Exception as e:
                logger.error(f"[Chat] SSE error: {e}", exc_info=True)
                yield _sse_event("error", {"message": str(e)})
            finally:
                _active_streams.pop(thread_id, None)

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
):
    """
    停止指定线程的 AI 生成。

    前端在用户点击"停止生成"按钮时调用此接口。
    """
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


@router.post("/upload-image", response_model=ResponseModel[dict])
async def upload_image(
    file: UploadFile = File(..., description="图片文件（jpg/png/webp/gif，最大 10MB）"),
    user: User = Depends(get_current_user),
):
    """
    上传图片，返回 base64 data URL 供 ChatRequest.images 使用。

    前端上传图片后，将返回的 url 放入 ChatRequest.images 数组即可发送多模态消息。
    """
    # 校验文件类型
    ext = ("." + file.filename.rsplit(".", 1)[-1].lower()) if file.filename and "." in file.filename else ""
    if file.content_type not in ALLOWED_IMAGE_TYPES and ext not in ALLOWED_IMAGE_EXTS:
        return ResponseModel(code=400, message=f"不支持的图片格式：{file.content_type or ext}，仅支持 jpg/png/webp/gif")

    # 读取文件内容并校验大小
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        return ResponseModel(code=400, message=f"图片大小超过限制（最大 {MAX_IMAGE_SIZE // 1024 // 1024}MB）")

    # 转换为 base64 data URL
    mime = file.content_type or "image/jpeg"
    b64 = base64.b64encode(content).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    return ResponseModel(
        message="上传成功",
        data={
            "url": data_url,
            "filename": file.filename or "upload.jpg",
            "size": len(content),
            "mime_type": mime,
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
    # 子查询：按 thread_id 聚合消息数和最新时间
    subq = (
        select(
            Conversation.thread_id,
            func.count(Conversation.id).label("message_count"),
            func.max(Conversation.created_at).label("updated_at"),
            func.min(Conversation.created_at).label("created_at"),
        )
        .where(Conversation.user_id == user.id)
        .where(Conversation.thread_id.isnot(None))
        .group_by(Conversation.thread_id)
        .subquery()
    )

    stmt = (
        select(subq)
        .order_by(subq.c.updated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # 批量查询 thread_usage
    thread_ids = [row.thread_id for row in rows]
    usage_map: dict[str, int] = {}
    title_map: dict[str, str] = {}
    if thread_ids:
        usage_stmt = select(ThreadUsage.thread_id, ThreadUsage.total_tokens).where(
            ThreadUsage.thread_id.in_(thread_ids)
        )
        usage_rows = (await db.execute(usage_stmt)).all()
        usage_map = {r.thread_id: r.total_tokens for r in usage_rows}

        title_stmt = select(ThreadMeta.thread_id, ThreadMeta.title).where(
            ThreadMeta.thread_id.in_(thread_ids)
        )
        title_rows = (await db.execute(title_stmt)).all()
        title_map = {
            r.thread_id: r.title for r in title_rows if r.title
        }

    threads = []
    for row in rows:
        last_msg_stmt = (
            select(Conversation.content)
            .where(Conversation.user_id == user.id)
            .where(Conversation.thread_id == row.thread_id)
            .where(Conversation.role == "assistant")
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        last_result = await db.execute(last_msg_stmt)
        last_content = last_result.scalar_one_or_none()

        threads.append(ThreadOut(
            thread_id=row.thread_id,
            title=title_map.get(row.thread_id),
            last_message=(last_content[:100] if last_content else None),
            message_count=row.message_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
            total_tokens=usage_map.get(row.thread_id, 0),
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
    base_filter = [
        Conversation.user_id == user.id,
        Conversation.thread_id == thread_id,
    ]

    count_stmt = select(func.count(Conversation.id)).where(*base_filter)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Conversation)
        .where(*base_filter)
        .order_by(Conversation.created_at.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

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
    owns = (
        await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.user_id == user.id,
                Conversation.thread_id == thread_id,
            )
        )
    ).scalar() or 0
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
    stmt = delete(Conversation).where(
        Conversation.user_id == user.id,
        Conversation.thread_id == thread_id,
    )
    result = await db.execute(stmt)
    # 同步清理线程元信息（标题），避免残留孤立记录
    await db.execute(
        delete(ThreadMeta).where(ThreadMeta.thread_id == thread_id)
    )
    await db.commit()

    if result.rowcount == 0:
        return ResponseModel(code=404, message="线程不存在")

    return ResponseModel(message=f"已删除 {result.rowcount} 条消息")

@router.delete("/history", response_model=ResponseModel[None])
async def clear_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清空当前用户的所有对话历史"""
    stmt = delete(Conversation).where(Conversation.user_id == user.id)
    result = await db.execute(stmt)
    # 同步清理该用户所有线程元信息
    await db.execute(
        delete(ThreadMeta).where(ThreadMeta.user_id == user.id)
    )
    await db.commit()

    return ResponseModel(message=f"已清空 {result.rowcount} 条消息")
