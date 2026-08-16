"""
对话相关 Schemas

定义 AI 对话（SSE 流式）相关的请求/响应模型：
- ChatRequest: 发送消息请求（支持多模态：文本 + 图片）
- ThreadOut: 对话线程摘要（最后消息、消息数、token 用量）
- MessageOut: 单条消息输出（角色、内容、元数据）
- ThreadMessagesOut: 线程消息分页列表

多模态说明：
- ChatRequest.images 支持 OpenAI 兼容格式，适配 DashScope Qwen-VL 接口
- 每项可以是 HTTP/HTTPS URL 或 base64 data URL（data:image/jpeg;base64,...）
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ChatRequest(BaseModel):
    """
    发送消息请求（支持多模态：文本 + 图片）。

    至少提供 message 或 images 之一。当仅提供图片时，message 可为空。

    images 格式示例：
    - URL: ["https://example.com/photo.jpg"]
    - base64: ["data:image/jpeg;base64,/9j/4AAQ..."]
    - 混合: ["https://example.com/a.jpg", "data:image/png;base64,iVBOR..."]
    """
    message: Optional[str] = Field(None, max_length=4000, description="文本消息内容")
    images: Optional[list[str]] = Field(
        None,
        max_length=10,
        description="图片列表（URL 或 base64 data URL），最多 10 张",
    )
    thread_id: Optional[str] = Field(None, max_length=100)
    # 为 true 时：生成新 thread_id 并标记 agent_mode=plan_design，全程路由到计划设计专用模型
    plan_design: Optional[bool] = Field(None, description="是否开启计划设计会话（新线程 + 专用模型）")
    # 知识库回答开关：默认关闭（None/falsy 时模型不可见知识库工具）
    kb_enabled: Optional[bool] = Field(
        None, description="是否开启知识库回答（开启则优先检索用户订阅的知识库作答）"
    )

    @model_validator(mode="after")
    def _require_message_or_images(self):
        """确保 message 和 images 至少提供一个"""
        if not self.message and not self.images:
            raise ValueError("message 和 images 至少提供一个")
        return self


class ThreadOut(BaseModel):
    """对话线程"""
    thread_id: str
    title: Optional[str] = None
    last_message: Optional[str] = None
    message_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    total_tokens: int = 0
    # 线程绑定的 agent 模式（plan_design -> 计划设计专用模型），供前端徽标展示
    agent_mode: Optional[str] = None

    model_config = {"from_attributes": True}


class ThreadTitleIn(BaseModel):
    """更新线程标题请求"""
    title: str = Field(..., min_length=1, max_length=200, description="自定义线程标题")


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
