"""动作库服务"""
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import case, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.checkin import CheckinExercise
from src.fitme.models.exercise import Exercise, UserExerciseFavorite
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
        """按名称匹配单个动作（中文名或英文名均命中）。

        排序策略保证结果稳定且更贴合用户输入：
        1. 精确匹配（中文名或英文名全等）优先于子串匹配；
        2. 同级内名称更短者优先（"深蹲" 命中 "深蹲" 而非 "杠铃深蹲"）。
        """
        name_match = or_(
            Exercise.name.ilike(f"%{name}%"),
            Exercise.name_en.ilike(f"%{name}%"),
        )
        exact_rank = case(
            # ilike 不带通配符 = 大小写不敏感全等
            (or_(Exercise.name.ilike(name), Exercise.name_en.ilike(name)), 0),
            else_=1,
        )
        # 取中/英文名中较短者作为"更接近用户输入"的度量（name_en 可能为 NULL）
        matched_len = func.least(
            func.char_length(Exercise.name),
            func.char_length(func.coalesce(Exercise.name_en, Exercise.name)),
        )
        result = await db.execute(
            select(Exercise)
            .where(name_match)
            .order_by(exact_rank, matched_len)
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def match_names(
        db: AsyncSession, names: List[str]
    ) -> Dict[str, Optional[Exercise]]:
        """将动作名称列表批量匹配到动作库，返回 {name: Exercise|None}。

        供 Agent 打卡按名称输入时使用（名称→ID 的模糊匹配属 agent 输入便利，
        见方案 D6；公共 CRUD schema 保持 id-only）。内部复用 search_by_name。
        """
        matched: Dict[str, Optional[Exercise]] = {}
        for name in names:
            matched[name] = await ExerciseService.search_by_name(db, name)
        return matched

    # exercises.embedding 向量列是否可用（进程级缓存）
    _embedding_col_available: Optional[bool] = None

    @staticmethod
    async def semantic_available(db: AsyncSession) -> bool:
        """语义检索是否可用（embedding 向量列存在）。

        pgvector 扩展不可用时 init_db 不会创建该列，语义检索整体关闭（不做降级）：
        本方法返回 False，调用方自行回退关键词检索。结果进程级缓存，只探测一次。
        """
        if ExerciseService._embedding_col_available is None:
            result = await db.execute(
                text(
                    "SELECT 1 FROM information_schema.columns"
                    " WHERE table_name = 'exercises' AND column_name = 'embedding'"
                    " AND udt_name = 'vector'"
                )
            )
            ExerciseService._embedding_col_available = result.scalar() is not None
        return ExerciseService._embedding_col_available

    @staticmethod
    def build_embedding_text(ex: Exercise) -> str:
        """拼接用于向量化的动作文本（名称中英 + 肌群 + 器械 + 描述）。

        供回填脚本与新增动作时生成 embedding 输入，保证检索与入库同口径。
        """
        parts = [
            ex.name or "",
            ex.name_en or "",
            ex.muscle_subgroup_zh or ex.muscle_subgroup or "",
            ex.target_zh or ex.target or "",
            ex.equipment_zh or ex.equipment or "",
            ex.description or "",
        ]
        return " | ".join(p for p in parts if p)

    @staticmethod
    async def semantic_search(
        db: AsyncSession,
        query_embedding: List[float],
        muscle_group: Optional[str] = None,
        equipment: Optional[str] = None,
        difficulty: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Tuple[Exercise, float]]:
        """按语义向量检索动作，返回 [(Exercise, similarity)] 按相似度降序。

        服务层保持纯净：query_embedding 由调用方（tool 层）用 embedding 模型算好传入，
        本方法只做向量相似度排序，不依赖 agents.harness。

        仅支持 pgvector 原生余弦距离排序；embedding 向量列不存在（扩展缺失）时
        直接返回空，调用方回退关键词检索（不做降级）。
        仅检索已回填 embedding 的动作（embedding 非空）。
        """
        if not await ExerciseService.semantic_available(db):
            return []

        filters = []
        if muscle_group:
            filters.append(Exercise.muscle_group == muscle_group)
        if equipment:
            filters.append(Exercise.equipment == equipment)
        if difficulty:
            filters.append(Exercise.difficulty == difficulty)
        if category:
            filters.append(Exercise.category == category)

        distance = Exercise.embedding.cosine_distance(query_embedding)
        stmt = (
            select(Exercise, distance.label("distance"))
            .where(Exercise.embedding.isnot(None), *filters)
            .order_by(distance)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [(ex, 1.0 - float(dist)) for ex, dist in result.all()]

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

    @staticmethod
    async def toggle_favorite(db: AsyncSession, user_id: UUID, exercise_id: UUID) -> bool:
        existing = await db.execute(
            select(UserExerciseFavorite).where(
                UserExerciseFavorite.user_id == user_id,
                UserExerciseFavorite.exercise_id == exercise_id,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            await db.execute(
                delete(UserExerciseFavorite).where(UserExerciseFavorite.id == row.id)
            )
            await db.commit()
            return False
        fav = UserExerciseFavorite(user_id=user_id, exercise_id=exercise_id)
        db.add(fav)
        await db.commit()
        return True

    @staticmethod
    async def get_favorite_ids(db: AsyncSession, user_id: UUID) -> Set[UUID]:
        result = await db.execute(
            select(UserExerciseFavorite.exercise_id).where(
                UserExerciseFavorite.user_id == user_id
            )
        )
        return set(result.scalars().all())

    @staticmethod
    async def list_favorites(
        db: AsyncSession, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Exercise], int]:
        count_q = select(func.count()).select_from(UserExerciseFavorite).where(
            UserExerciseFavorite.user_id == user_id
        )
        total = (await db.execute(count_q)).scalar() or 0

        q = (
            select(Exercise)
            .join(UserExerciseFavorite, UserExerciseFavorite.exercise_id == Exercise.id)
            .where(UserExerciseFavorite.user_id == user_id)
            .order_by(UserExerciseFavorite.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(q)
        return list(result.scalars().all()), total
