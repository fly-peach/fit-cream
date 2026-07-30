"""动作库服务"""
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.checkin import CheckinExercise
from src.fitme.models.exercise import Exercise
from src.fitme.models.plan import PlanDayExercise
from utils.exceptions import BusinessException, ErrorCode, NotFoundException


class ExerciseService:
    @staticmethod
    async def get_all(db: AsyncSession) -> List[Exercise]:
        result = await db.execute(select(Exercise).order_by(Exercise.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, exercise_id: UUID) -> Optional[Exercise]:
        result = await db.execute(
            select(Exercise).where(Exercise.id == exercise_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_muscle_group(
        db: AsyncSession, muscle_group: str
    ) -> List[Exercise]:
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
        result = await db.execute(
            select(Exercise)
            .where(Exercise.equipment == equipment)
            .order_by(Exercise.name)
        )
        return list(result.scalars().all())

    @staticmethod
    def _apply_exercise_filters(
        query,
        muscle_group: Optional[str] = None,
        equipment: Optional[str] = None,
        difficulty: Optional[str] = None,
        category: Optional[str] = None,
        body_part: Optional[str] = None,
        target: Optional[str] = None,
        keyword: Optional[str] = None,
    ):
        """统一构建动作筛选 WHERE 子句（search 与 count 共享，避免逻辑重复）。"""
        if muscle_group:
            query = query.where(Exercise.muscle_group == muscle_group)
        if equipment:
            query = query.where(Exercise.equipment == equipment)
        if difficulty:
            query = query.where(Exercise.difficulty == difficulty)
        if category:
            query = query.where(Exercise.category == category)
        if body_part:
            query = query.where(Exercise.body_part == body_part)
        if target:
            query = query.where(Exercise.target == target)
        if keyword:
            # 关键词 OR 匹配 name/name_en/description/instructions：
            # 中文查询（如「深蹲」）与英文查询（如 Barbell）均可命中
            query = query.where(
                or_(
                    Exercise.name.ilike(f"%{keyword}%"),
                    Exercise.name_en.ilike(f"%{keyword}%"),
                    Exercise.description.ilike(f"%{keyword}%"),
                    Exercise.instructions.ilike(f"%{keyword}%"),
                )
            )
        return query

    @staticmethod
    async def search(
        db: AsyncSession,
        muscle_group: Optional[str] = None,
        equipment: Optional[str] = None,
        keyword: Optional[str] = None,
        difficulty: Optional[str] = None,
        category: Optional[str] = None,
        body_part: Optional[str] = None,
        target: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Exercise]:
        query = ExerciseService._apply_exercise_filters(
            select(Exercise),
            muscle_group=muscle_group,
            equipment=equipment,
            difficulty=difficulty,
            category=category,
            body_part=body_part,
            target=target,
            keyword=keyword,
        ).order_by(Exercise.name).offset(offset).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def search_with_count(
        db: AsyncSession,
        muscle_group: Optional[str] = None,
        equipment: Optional[str] = None,
        keyword: Optional[str] = None,
        difficulty: Optional[str] = None,
        category: Optional[str] = None,
        body_part: Optional[str] = None,
        target: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Exercise], int]:
        """单次筛选构建、两条 SQL：返回 (items, total)，filter 逻辑只写一处。"""
        items_query = ExerciseService._apply_exercise_filters(
            select(Exercise),
            muscle_group=muscle_group,
            equipment=equipment,
            difficulty=difficulty,
            category=category,
            body_part=body_part,
            target=target,
            keyword=keyword,
        ).order_by(Exercise.name).offset(offset).limit(limit)
        count_query = ExerciseService._apply_exercise_filters(
            select(func.count()).select_from(Exercise),
            muscle_group=muscle_group,
            equipment=equipment,
            difficulty=difficulty,
            category=category,
            body_part=body_part,
            target=target,
            keyword=keyword,
        )
        items_result = await db.execute(items_query)
        count_result = await db.execute(count_query)
        return list(items_result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def search_by_name(
        db: AsyncSession, name: str
    ) -> Optional[Exercise]:
        result = await db.execute(
            select(Exercise).where(Exercise.name.ilike(f"%{name}%")).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_exercise(db: AsyncSession, data: dict) -> Exercise:
        exercise = Exercise(**data)
        db.add(exercise)
        await db.flush()
        await db.refresh(exercise)
        return exercise

    @staticmethod
    async def update_exercise(
        db: AsyncSession, exercise_id: UUID, data: dict
    ) -> Exercise:
        exercise = await ExerciseService.get_by_id(db, exercise_id)
        if not exercise:
            raise NotFoundException("动作不存在")
        for field, value in data.items():
            setattr(exercise, field, value)
        await db.flush()
        await db.refresh(exercise)
        return exercise

    @staticmethod
    async def delete_exercise(db: AsyncSession, exercise_id: UUID) -> None:
        exercise = await ExerciseService.get_by_id(db, exercise_id)
        if not exercise:
            raise NotFoundException("动作不存在")

        plan_ref = await db.execute(
            select(func.count()).select_from(PlanDayExercise).where(
                PlanDayExercise.exercise_id == exercise_id
            )
        )
        checkin_ref = await db.execute(
            select(func.count()).select_from(CheckinExercise).where(
                CheckinExercise.exercise_id == exercise_id
            )
        )
        if plan_ref.scalar() > 0 or checkin_ref.scalar() > 0:
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                "该动作已被训练计划或打卡记录引用，无法删除",
            )

        await db.delete(exercise)
        await db.flush()

    @staticmethod
    async def count(
        db: AsyncSession,
        muscle_group: Optional[str] = None,
        equipment: Optional[str] = None,
        difficulty: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        body_part: Optional[str] = None,
        target: Optional[str] = None,
    ) -> int:
        query = ExerciseService._apply_exercise_filters(
            select(func.count()).select_from(Exercise),
            muscle_group=muscle_group,
            equipment=equipment,
            difficulty=difficulty,
            category=category,
            body_part=body_part,
            target=target,
            keyword=keyword,
        )
        result = await db.execute(query)
        return result.scalar() or 0

    @staticmethod
    async def list_categories(db: AsyncSession) -> List[Dict[str, object]]:
        result = await db.execute(
            select(Exercise.category, func.count(Exercise.id))
            .where(Exercise.category.isnot(None))
            .group_by(Exercise.category)
            .order_by(Exercise.category)
        )
        return [{"name": row[0], "count": row[1]} for row in result.all()]

    @staticmethod
    async def list_muscle_groups(db: AsyncSession) -> List[Dict[str, object]]:
        result = await db.execute(
            select(Exercise.muscle_group, func.count(Exercise.id))
            .where(Exercise.muscle_group.isnot(None))
            .group_by(Exercise.muscle_group)
            .order_by(Exercise.muscle_group)
        )
        return [{"name": row[0], "count": row[1]} for row in result.all()]

    @staticmethod
    async def list_equipments(db: AsyncSession) -> List[Dict[str, object]]:
        """按器械分组统计（dataset 含 28 种器械值，前端筛选取动态值）。"""
        result = await db.execute(
            select(Exercise.equipment, func.count(Exercise.id))
            .where(Exercise.equipment.isnot(None))
            .group_by(Exercise.equipment)
            .order_by(Exercise.equipment)
        )
        return [{"name": row[0], "count": row[1]} for row in result.all()]
