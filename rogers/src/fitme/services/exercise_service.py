"""
动作库服务

提供健身动作的多维度查询：
- 按肌群、器械、难度筛选
- 关键词模糊搜索
- 名称精确匹配（Agent 打卡时匹配动作）
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.exercise import Exercise


class ExerciseService:
    @staticmethod
    async def get_all(db: AsyncSession) -> List[Exercise]:
        """获取所有动作"""
        result = await db.execute(select(Exercise).order_by(Exercise.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, exercise_id: UUID) -> Optional[Exercise]:
        """根据 ID 获取动作"""
        result = await db.execute(
            select(Exercise).where(Exercise.id == exercise_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_muscle_group(
        db: AsyncSession, muscle_group: str
    ) -> List[Exercise]:
        """根据肌群获取动作"""
        result = await db.execute(
            select(Exercise)
            .where(Exercise.muscle_group == muscle_group)
            .order_by(Exercise.name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_by_equipment(
        db: AsyncSession, equipment: str
    ) -> List[Exercise]:
        """根据器械获取动作"""
        result = await db.execute(
            select(Exercise)
            .where(Exercise.equipment == equipment)
            .order_by(Exercise.name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def search(
        db: AsyncSession,
        muscle_group: Optional[str] = None,
        equipment: Optional[str] = None,
        keyword: Optional[str] = None,
        difficulty: Optional[str] = None,
        limit: int = 20,
    ) -> List[Exercise]:
        """搜索动作"""
        query = select(Exercise)

        if muscle_group:
            query = query.where(Exercise.muscle_group == muscle_group)
        if equipment:
            query = query.where(Exercise.equipment == equipment)
        if difficulty:
            query = query.where(Exercise.difficulty == difficulty)
        if keyword:
            query = query.where(
                or_(
                    Exercise.name.ilike(f"%{keyword}%"),
                    Exercise.description.ilike(f"%{keyword}%"),
                )
            )

        query = query.order_by(Exercise.name).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def search_by_name(
        db: AsyncSession, name: str
    ) -> Optional[Exercise]:
        """根据名称模糊搜索动作（返回第一个匹配）"""
        result = await db.execute(
            select(Exercise).where(Exercise.name.ilike(f"%{name}%")).limit(1)
        )
        return result.scalar_one_or_none()