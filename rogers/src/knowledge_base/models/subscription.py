"""
订阅 ORM 模型（kb_subscriptions 表）

用户与知识库多对多订阅关联。完整权限门槛型：订阅某 KB 后才能读其文档 / 搜索，
Agent 也只搜索已订阅的 KB。
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KBSubscription(Base):
    __tablename__ = "kb_subscriptions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    kb_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 关系
    kb: Mapped["KnowledgeBase"] = relationship(back_populates="subscriptions")  # noqa: F821
    user: Mapped["User"] = relationship()  # noqa: F821

    __table_args__ = (UniqueConstraint("kb_id", "user_id"),)