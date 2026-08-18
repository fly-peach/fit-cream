"""
独立心情记录服务

提供心情记录的按日期 upsert 与日期范围查询：
- upsert：按 (user_id, date) 查，存在则更新 mood/note，否则新建（同日覆盖语义）
- list_by_range：按日期升序返回区间内记录
"""
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.mood_log import MoodLog
from src.fitme.schemas.mood import MoodUpsert


class MoodService:
    @staticmethod
    async def upsert(
        db: AsyncSession,
        user_id: UUID,
        data: MoodUpsert,
    ) -> MoodLog:
        """按 (user_id, date) 记录心情，同日覆盖"""
        result = await db.execute(
            select(MoodLog).where(
                MoodLog.user_id == user_id,
                MoodLog.date == data.date,
            )
        )
        mood = result.scalar_one_or_none()

        if not mood:
            mood = MoodLog(
                user_id=user_id,
                date=data.date,
                mood=data.mood,
                note=data.note,
            )
            db.add(mood)
        else:
            mood.mood = data.mood
            mood.note = data.note

        await db.flush()
        await db.refresh(mood)
        return mood

    @staticmethod
    async def list_by_range(
        db: AsyncSession,
        user_id: UUID,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> list[MoodLog]:
        """按日期升序返回区间内心情记录"""
        query = (
            select(MoodLog)
            .where(MoodLog.user_id == user_id)
            .order_by(MoodLog.date.asc())
        )
        if start:
            query = query.where(MoodLog.date >= start)
        if end:
            query = query.where(MoodLog.date <= end)
        result = await db.execute(query)
        return list(result.scalars().all())
