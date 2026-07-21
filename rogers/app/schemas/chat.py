"""对话相关 Schema"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """发送消息请求"""
    message: str = Field(..., min_length=1, max_length=4000)
    thread_id: Optional[str] = Field(None, max_length=100)


class ThreadOut(BaseModel):
    """对话线程"""
    thread_id: str
    last_message: Optional[str] = None
    message_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    """单条消息"""
    id: UUID
    role: str
    content: Optional[str] = None
    metadata_json: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ThreadMessagesOut(BaseModel):
    """线程消息列表"""
    thread_id: str
    messages: list[MessageOut]
    total: int
