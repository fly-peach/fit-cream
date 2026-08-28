"""动作库服务"""
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import case, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.checkin import CheckinExercise
from src.fitme.models.exercise import Exercise, UserExerciseFavorite
from src.fitme.models.plan import PlanDayExercise
from utils.exceptions import BusinessException, ErrorCode, NotFoundException

_CATEGORY_LABELS = {
    "compound": "复合动作",
    "isolation": "孤立动作",
    "cardio": "有氧训练",
}
_DIFFICULTY_LABELS = {
    "beginner": "初级",
    "intermediate": "中级",
    "advanced": "高级",
}


class ExerciseService:
    @staticmethod
    async def get_all(db: AsyncSession) -> List[Exercise]:
        result = await db.execute(select(Exercise).order_by(Exercise.name))
        return list(result.scalars().all())

    @staticmethod
    async def list_name_map(db: AsyncSession) -> List[Dict[str, str]]:
        """全量动作名 -> ID 映射（id/name/name_en），供前端把计划提案中的动作名转为详情链接。"""
        result = await db.execute(
            select(Exercise.id, Exercise.name, Exercise.name_en).order_by(Exercise.name)
        )
        return [
            {"id": str(eid), "name": name, "name_en": name_en}
            for eid, name, name_en in result.all()
        ]

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
        """拼接用于向量化的动作文本（标签化自然语言句）。

        覆盖名称中英、类型（复合/孤立/有氧）、主要锻炼、协同肌群、部位、身体部位、
        器械、难度、简介、提示，避免裸值拼接导致概念被稀释。
        安全/功能类语义查询（「不伤膝盖」「核心稳定」「新手」）依赖这些字段，
        缺省会显著降低召回——改此函数后必须重跑
        scripts/backfill_exercise_embeddings.py 回填存量向量。
        """
        parts = [f"动作：{ex.name or ''}"]
        if ex.name_en:
            parts[0] += f"（{ex.name_en}）"
        if ex.category:
            label = _CATEGORY_LABELS.get(ex.category, ex.category)
            parts.append(f"类型：{label}（{ex.category}）")
        elif ex.is_compound:
            parts.append("类型：复合动作")
        else:
            parts.append("类型：孤立动作")
        target = ex.target_zh or ex.target
        if target:
            parts.append(f"主要锻炼：{target}")
        secondary = ex.secondary_muscles_zh or []
        if secondary:
            parts.append("协同肌群：" + "、".join(str(s) for s in secondary))
        if ex.muscle_subgroup_zh or ex.muscle_subgroup:
            parts.append(f"部位：{ex.muscle_subgroup_zh or ex.muscle_subgroup}")
        body = ex.body_part_zh or ex.body_part
        if body:
            parts.append(f"身体部位：{body}")
        equipment = ex.equipment_zh or ex.equipment
        if equipment:
            tail = (
                f"（{ex.equipment}）"
                if ex.equipment and equipment != ex.equipment
                else ""
            )
            parts.append(f"器械：{equipment}{tail}")
        if ex.difficulty:
            label = _DIFFICULTY_LABELS.get(ex.difficulty, ex.difficulty)
            parts.append(f"难度：{label}（{ex.difficulty}）")
        if ex.description:
            parts.append(f"简介：{ex.description}")
        if ex.tips:
            parts.append(f"提示：{ex.tips}")
        return "。".join(parts) + "。"

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
    def rrf_fuse(ranked_lists: List[List[UUID]], k: int = 60) -> List[UUID]:
        """Reciprocal Rank Fusion：合并多路 ID 排名，返回按融合分降序去重后的 ID 列表。

        RRF 分 = 求和 1/(k+rank)。纯函数（不依赖外部服务），供混合检索与离线单测复用。
        """
        scores: Dict[UUID, float] = {}
        for ranked in ranked_lists:
            for rank, uid in enumerate(ranked, start=1):
                scores[uid] = scores.get(uid, 0.0) + 1.0 / (k + rank)
        return [
            uid for uid, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ]

    @staticmethod
    async def hybrid_search(
        db: AsyncSession,
        query_text: str,
        *,
        muscle_group: Optional[str] = None,
        equipment: Optional[str] = None,
        difficulty: Optional[str] = None,
        category: Optional[str] = None,
        keyword_terms: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Tuple[Exercise, float]]:
        """混合检索（与 get_exercises_tool 同一入口）。

        管线：向量 top-``max(limit*15, 150)`` ->（提供 keyword_terms 时按名称词项检索并
        RRF 融合）-> rerank 精排取 top-``limit``。

        - **精确匹配优先**：keyword_terms 命中的动作（名称/描述词项匹配，最高置信）
          按 RRF 序置于前列；rerank 只对纯语义候选（向量命中未被词项匹配的）重排，
          避免 rerank 基于查询字面 token 把精确匹配项挤出 top-K（实测「不伤膝盖」
          的 leg press/glute bridge 曾被 rerank 压到拉伸类之后）。
        - 精排：``EXERCISE_RERANK_ENABLED`` 且 rerank 可用时按 query_text 重排；
          不可用/异常回退向量序（含 RRF 融合序）。
        - 候选池取 300（limit=20 时）：语义软查询的相关动作常排在向量 50-300 位，
          池过小会被截断、rerank 无法救回（实测「不伤膝盖」相关动作在 rank 49-294）。
        - 返回 [(Exercise, similarity)]：similarity 为向量相似度（rerank 仅重排不改分）。
        - 语义不可用 / embedding 失败：返回空（调用方回退关键词检索）。
        """
        if not query_text or not await ExerciseService.semantic_available(db):
            return []

        from src.agents.harness.runtime.memory.embeddings import (
            get_embedding_model,
            rerank_texts,
        )

        try:
            embedding = await get_embedding_model().aget_text_embedding(query_text)
        except Exception:
            return []

        candidate_n = max(limit * 15, 150)
        vector = await ExerciseService.semantic_search(
            db,
            embedding,
            muscle_group=muscle_group,
            equipment=equipment,
            difficulty=difficulty,
            category=category,
            limit=candidate_n,
        )
        if not vector:
            return []

        scored = {ex.id: sim for ex, sim in vector}
        order: List[UUID] = [ex.id for ex, _ in vector]
        all_ex = {ex.id: ex for ex, _ in vector}
        keyword_lists: List[List[UUID]] = []

        if keyword_terms:
            for term in keyword_terms:
                items = await ExerciseService.search(
                    db,
                    muscle_group=muscle_group,
                    equipment=equipment,
                    difficulty=difficulty,
                    category=category,
                    keyword=term,
                    limit=candidate_n,
                )
                if items:
                    keyword_lists.append([ex.id for ex in items])
                    all_ex.update({ex.id: ex for ex in items})

        keyword_exact: List[UUID] = []
        if keyword_lists:
            fused = ExerciseService.rrf_fuse([order, *keyword_lists])[:candidate_n]
            keyword_id_set = {uid for lst in keyword_lists for uid in lst}
            # 名称词项精确匹配是最高置信信号（如「卧推」「leg press」），置于前列；
            keyword_exact = [uid for uid in fused if uid in keyword_id_set]
            # 纯语义候选（向量命中且未被词项匹配）交给 rerank 精排
            order = [uid for uid in fused if uid not in keyword_id_set]

        rerank_enabled = True
        try:
            from app.config import get_settings

            rerank_enabled = bool(
                getattr(get_settings(), "EXERCISE_RERANK_ENABLED", True)
            )
        except Exception:
            pass

        if rerank_enabled and order:
            texts = [
                ExerciseService.build_embedding_text(all_ex[uid]) for uid in order
            ]
            indices = await rerank_texts(query_text, texts, top_n=limit)
            order = [order[i] for i in indices]

        # 精确匹配在前（按 RRF 序），rerank 后的语义候选补足到 limit
        order = (keyword_exact + order)[:limit]

        return [
            (all_ex[uid], scored.get(uid, 0.0)) for uid in order if uid in all_ex
        ]

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
