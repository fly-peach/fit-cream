"""对话路由 /api/chat/* - 流式对话 + Thread CRUD"""
import asyncio
import json
import logging
from typing import Dict, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.dependencies import get_current_user
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.chat import ChatRequest, MessageOut, ThreadMessagesOut, ThreadOut
from app.schemas.common import ResponseModel

logger = logging.getLogger("fitcream.chat")

router = APIRouter(prefix="/chat", tags=["chat"])

# 存储活跃的流式任务，用于停止生成
# key: thread_id, value: asyncio.Event
_active_streams: Dict[str, asyncio.Event] = {}


def _get_agent():
    from agents.agent_graph import get_agent
    return get_agent()


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
    发送消息并以 SSE 流式返回 Agent 回复。

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

    await _save_message(db, user.id, thread_id, "user", req.message)

    agent = _get_agent()
    config = {"configurable": {"thread_id": thread_id, "user_id": user_id_str}}
    input_msg = {"messages": [{"role": "user", "content": req.message}]}

    # 创建停止事件
    stop_event = asyncio.Event()
    _active_streams[thread_id] = stop_event

    async def event_stream():
        yield _sse_event("start", {"thread_id": thread_id})

        full_content = ""
        tool_calls = []

        # 使用独立 session，避免请求级 session 在流式响应期间被关闭
        async with async_session_factory() as stream_db:
            try:
                async for event in agent.astream_events(input_msg, config=config, version="v2"):
                    # 检查是否需要停止
                    if stop_event.is_set():
                        if full_content:
                            await _save_message(
                                stream_db, user.id, thread_id, "assistant", full_content,
                                metadata={"tool_calls": tool_calls, "stopped": True},
                            )
                        yield _sse_event("stopped", {"thread_id": thread_id, "partial_content": full_content})
                        return

                    kind = event["event"]

                    if kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        reasoning = chunk.additional_kwargs.get("reasoning_content", "")
                        if reasoning:
                            yield _sse_event("thinking", {"content": reasoning})
                        if chunk.content:
                            full_content += chunk.content
                            yield _sse_event("token", {"content": chunk.content})

                    elif kind == "on_tool_start":
                        tool_name = event["name"]
                        tool_calls.append(tool_name)
                        # 透传工具入参，便于前端展示真实参数
                        raw_input = event.get("data", {}).get("input")
                        try:
                            # 确保可 JSON 序列化
                            json.dumps(raw_input, ensure_ascii=False)
                            tool_input = raw_input
                        except (TypeError, ValueError):
                            tool_input = {"raw": str(raw_input)} if raw_input else {}
                        yield _sse_event("tool_start", {
                            "tool": tool_name,
                            "input": tool_input or {},
                        })

                    elif kind == "on_tool_end":
                        raw_output = event["data"].get("output", "")
                        # 优先尝试结构化输出（ToolMessage.content 可能是 str 或 list）
                        if isinstance(raw_output, str):
                            output_str = raw_output
                        else:
                            try:
                                output_str = json.dumps(raw_output, ensure_ascii=False)
                            except (TypeError, ValueError):
                                output_str = str(raw_output)
                        yield _sse_event("tool_result", {
                            "tool": event["name"],
                            "data": output_str[:2000],
                        })

                if full_content:
                    await _save_message(
                        stream_db, user.id, thread_id, "assistant", full_content,
                        metadata={"tool_calls": tool_calls},
                    )

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


@router.get("/threads", response_model=ResponseModel[list[ThreadOut]])
async def list_threads(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的对话线程列表"""
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
            last_message=(last_content[:100] if last_content else None),
            message_count=row.message_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
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
    await db.commit()

    return ResponseModel(message=f"已清空 {result.rowcount} 条消息")
