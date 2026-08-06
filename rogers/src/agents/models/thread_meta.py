"""
Thread 元信息模型

存储对话线程的自定义标题等元信息，与 Conversation / ThreadUsage 配合使用。
按 user_id + thread_id 组织，thread_id 全局唯一（与 ThreadUsage 一致）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from src.agents.models.thread_base import ThreadBase


class ThreadMeta(ThreadBase, Base):
    __tablename__ = "thread_metas"

    title: Mapped[Optional[str]] = mapped_column(String(200))
    # 线程绑定的 Agent 模式（如 "plan_design"），决定后续 message/resume 路由到哪个 graph。
    # 缺失（None）时走默认 graph。生产需手动 ALTER TABLE 补列（init_db 不会自动加列）。
    agent_mode: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
