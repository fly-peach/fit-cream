"""
对话消息服务

集中封装 conversations 表的读写逻辑：
- save_message / save_messages: 落库用户输入与 AI 回复
- aggregate_threads: 按 thread_id 聚合线程摘要
- get_last_assistant_content: 取线程最近一条 AI 回复
- get_messages: 分页获取线程消息
- count_thread_messages: 校验线程归属
- delete_by_thread / clear_by_user: 删除消息

写入方法内部 commit，保持与既有 send_message 流式落库语义一致
（需立即持久化以便独立 session 可读到刚写入的消息）。
"""
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.models.conversation import Conversation


class ConversationService:
    @staticmethod
    async def save_message(
        db: AsyncSession,
        user_id: UUID,
        thread_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Conversation:
        """保存单条对话消息并立即提交"""
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

    @staticmethod
    async def save_messages(
        db: AsyncSession,
        user_id: UUID,
        thread_id: str,
        messages: list[dict[str, Any]],
    ) -> int:
        """批量保存对话消息并提交，返回写入条数"""
        for msg in messages:
            db.add(
                Conversation(
                    id=uuid4(),
                    user_id=user_id,
                    thread_id=thread_id,
                    role=msg["role"],
                    content=msg["content"],
                    metadata_json=msg.get("metadata"),
                )
            )
        await db.commit()
        return len(messages)

    @staticmethod
    async def aggregate_threads(
        db: AsyncSession, user_id: UUID, page: int, size: int
    ) -> list:
        """按 thread_id 聚合消息数与时间范围，按更新时间倒序分页"""
        subq = (
            select(
                Conversation.thread_id,
                func.count(Conversation.id).label("message_count"),
                func.max(Conversation.created_at).label("updated_at"),
                func.min(Conversation.created_at).label("created_at"),
            )
            .where(Conversation.user_id == user_id)
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
        return result.all()

    @staticmethod
    async def get_last_assistant_content(
        db: AsyncSession, user_id: UUID, thread_id: str
    ) -> Optional[str]:
        """获取线程最近一条 assistant 消息内容"""
        stmt = (
            select(Conversation.content)
            .where(Conversation.user_id == user_id)
            .where(Conversation.thread_id == thread_id)
            .where(Conversation.role == "assistant")
            .order_by(Conversation.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_messages(
        db: AsyncSession, user_id: UUID, thread_id: str, page: int, size: int
    ) -> tuple[list[Conversation], int]:
        """分页获取线程消息，返回 (messages, total)"""
        base_filter = [
            Conversation.user_id == user_id,
            Conversation.thread_id == thread_id,
        ]
        total = (
            await db.execute(select(func.count(Conversation.id)).where(*base_filter))
        ).scalar() or 0

        stmt = (
            select(Conversation)
            .where(*base_filter)
            .order_by(Conversation.created_at.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
        messages = list((await db.execute(stmt)).scalars().all())
        return messages, total

    @staticmethod
    async def count_thread_messages(
        db: AsyncSession, user_id: UUID, thread_id: str
    ) -> int:
        """统计线程消息数，用于校验线程归属"""
        return (
            await db.execute(
                select(func.count(Conversation.id)).where(
                    Conversation.user_id == user_id,
                    Conversation.thread_id == thread_id,
                )
            )
        ).scalar() or 0

    @staticmethod
    async def delete_by_thread(
        db: AsyncSession, user_id: UUID, thread_id: str
    ) -> int:
        """删除指定线程的所有消息，返回删除条数"""
        result = await db.execute(
            delete(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.thread_id == thread_id,
            )
        )
        await db.commit()
        return result.rowcount

    @staticmethod
    async def clear_by_user(db: AsyncSession, user_id: UUID) -> int:
        """清空用户所有对话消息，返回删除条数"""
        result = await db.execute(
            delete(Conversation).where(Conversation.user_id == user_id)
        )
        await db.commit()
        return result.rowcount
