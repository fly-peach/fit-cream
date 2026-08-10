"""
管理端 Service

提供管理员后台所需的用户管理、全局统计聚合与知识库统计列表查询。
所有方法均假定调用方已通过 get_admin_user 权限校验。
"""
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.models.conversation import Conversation
from src.fitme.models.checkin import Checkin
from src.fitme.models.diet_plan import DietPlan
from src.fitme.models.health_metric import HealthMetric
from src.fitme.models.plan import Plan
from src.fitme.models.user import User
from src.fitme.schemas.admin import (
    AdminCheckinOut,
    AdminConversationStats,
    AdminKbListItem,
    AdminKbStats,
    AdminOverviewStats,
    AdminTrainingStats,
    AdminTrends,
    AdminUserDetail,
    AdminUserHealthMetric,
    AdminUserListItem,
    AdminUsersStats,
    AdminUserSettings,
)
from src.knowledge_base.models.chunk import KBChunk
from src.knowledge_base.models.document import KBDocument
from src.knowledge_base.models.knowledge_base import KnowledgeBase
from utils.exceptions import ForbiddenException, NotFoundException


class AdminService:
    # ============================================================
    # 用户管理
    # ============================================================

    @staticmethod
    async def _batch_counts(
        db: AsyncSession, user_ids: list[UUID]
    ) -> dict[UUID, dict[str, int]]:
        """批量统计用户维度的计划数/打卡数，避免逐用户 N+1 查询。"""
        counts: dict[UUID, dict[str, int]] = {
            uid: {"plans": 0, "checkins": 0} for uid in user_ids
        }
        if not user_ids:
            return counts

        plan_result = await db.execute(
            select(Plan.user_id, func.count(Plan.id))
            .where(Plan.user_id.in_(user_ids))
            .group_by(Plan.user_id)
        )
        for uid, n in plan_result.all():
            counts[uid]["plans"] = n

        checkin_result = await db.execute(
            select(Checkin.user_id, func.count(Checkin.id))
            .where(Checkin.user_id.in_(user_ids))
            .group_by(Checkin.user_id)
        )
        for uid, n in checkin_result.all():
            counts[uid]["checkins"] = n

        return counts

    @staticmethod
    async def _to_list_item(db: AsyncSession, user: User) -> AdminUserListItem:
        counts = await AdminService._batch_counts(db, [user.id])
        c = counts.get(user.id, {"plans": 0, "checkins": 0})
        item = AdminUserListItem.model_validate(user)
        item.plan_count = c["plans"]
        item.checkin_count = c["checkins"]
        return item

    @staticmethod
    async def list_users(
        db: AsyncSession,
        page: int = 1,
        size: int = 20,
        keyword: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> tuple[list[AdminUserListItem], int]:
        filters = [User.deleted_at.is_(None)]
        if keyword:
            kw = f"%{keyword.strip()}%"
            filters.append(
                or_(User.phone.ilike(kw), User.name.ilike(kw), User.email.ilike(kw))
            )
        if role:
            filters.append(User.role == role)
        if is_active is not None:
            filters.append(User.is_active == is_active)

        total = (
            await db.execute(select(func.count(User.id)).where(*filters))
        ).scalar_one()

        result = await db.execute(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        users = list(result.scalars().all())
        items = [await AdminService._to_list_item(db, u) for u in users]
        return items, total

    @staticmethod
    async def get_user_detail(db: AsyncSession, user_id: UUID) -> AdminUserDetail:
        result = await db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException("用户不存在")

        counts = await AdminService._batch_counts(db, [user.id])
        c = counts.get(user.id, {"plans": 0, "checkins": 0})

        diet_plan_count = (
            await db.execute(
                select(func.count(DietPlan.id)).where(DietPlan.user_id == user.id)
            )
        ).scalar_one()

        settings: Optional[AdminUserSettings] = None
        if user.settings is not None:
            settings = AdminUserSettings(
                goal=user.settings.goal,
                weekly_training_goal=user.settings.weekly_training_goal,
                calorie_goal=user.settings.calorie_goal,
                target_weight_kg=(
                    float(user.settings.target_weight_kg)
                    if user.settings.target_weight_kg is not None
                    else None
                ),
            )

        latest_metric: Optional[AdminUserHealthMetric] = None
        metric_result = await db.execute(
            select(HealthMetric)
            .where(HealthMetric.user_id == user.id)
            .order_by(HealthMetric.measure_date.desc())
            .limit(1)
        )
        metric = metric_result.scalar_one_or_none()
        if metric is not None:
            latest_metric = AdminUserHealthMetric(
                measure_date=metric.measure_date,
                weight_kg=metric.weight_kg,
                body_fat_pct=metric.body_fat_pct,
                bmi=metric.bmi,
            )

        item = AdminUserDetail.model_validate(user)
        item.plan_count = c["plans"]
        item.checkin_count = c["checkins"]
        item.diet_plan_count = diet_plan_count
        item.settings = settings
        item.latest_health_metric = latest_metric
        return item

    @staticmethod
    async def update_user(
        db: AsyncSession,
        user_id: UUID,
        admin_user: User,
        is_active: Optional[bool] = None,
        role: Optional[str] = None,
    ) -> AdminUserListItem:
        result = await db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException("用户不存在")

        if is_active is not None:
            if user.id == admin_user.id and not is_active:
                raise ForbiddenException("不能禁用自己")
            user.is_active = is_active
        if role is not None:
            if user.id == admin_user.id and role != "admin":
                raise ForbiddenException("不能取消自己的管理员权限")
            user.role = role

        await db.flush()
        return await AdminService._to_list_item(db, user)

    @staticmethod
    async def list_user_checkins(
        db: AsyncSession, user_id: UUID, limit: int = 20
    ) -> list[AdminCheckinOut]:
        result = await db.execute(
            select(Checkin)
            .where(Checkin.user_id == user_id)
            .order_by(Checkin.date.desc(), Checkin.created_at.desc())
            .limit(limit)
        )
        return [AdminCheckinOut.model_validate(c) for c in result.scalars().all()]

    # ============================================================
    # 全局统计
    # ============================================================

    @staticmethod
    async def get_overview_stats(db: AsyncSession) -> AdminOverviewStats:
        now = datetime.now(timezone.utc)
        since_7d = now - timedelta(days=7)
        today = date.today()
        since_7d_date = today - timedelta(days=7)
        since_30d_date = today - timedelta(days=30)

        # ---- 用户维度 ----
        total_users = (
            await db.execute(
                select(func.count(User.id)).where(User.deleted_at.is_(None))
            )
        ).scalar_one()
        new_7d = (
            await db.execute(
                select(func.count(User.id)).where(
                    User.deleted_at.is_(None), User.created_at >= since_7d
                )
            )
        ).scalar_one()
        # 活跃口径：近 N 天有打卡记录的去重用户（与趋势图一致）
        active_7d = (
            await db.execute(
                select(func.count(func.distinct(Checkin.user_id))).where(
                    Checkin.date >= since_7d_date
                )
            )
        ).scalar_one()

        # ---- 训练维度 ----
        total_checkins = (
            (await db.execute(select(func.count(Checkin.id)))).scalar_one()
        )
        checkins_30d = (
            await db.execute(
                select(func.count(Checkin.id)).where(Checkin.date >= since_30d_date)
            )
        ).scalar_one()
        total_plans = (
            (await db.execute(select(func.count(Plan.id)))).scalar_one()
        )
        active_plans = (
            await db.execute(
                select(func.count(Plan.id)).where(Plan.status == "active")
            )
        ).scalar_one()

        # ---- 知识库维度 ----
        total_kbs = (
            (await db.execute(select(func.count(KnowledgeBase.id)))).scalar_one()
        )
        total_documents = (
            (await db.execute(select(func.count(KBDocument.id)))).scalar_one()
        )
        pending_documents = (
            await db.execute(
                select(func.count(KBDocument.id)).where(
                    (KBDocument.last_indexed_at.is_(None))
                    | (KBDocument.status == "failed")
                )
            )
        ).scalar_one()
        total_chunks = (
            (await db.execute(select(func.count(KBChunk.id)))).scalar_one()
        )

        # ---- 对话维度 ----
        total_threads = (
            await db.execute(
                select(func.count(func.distinct(Conversation.thread_id)))
            )
        ).scalar_one()
        total_messages = (
            (await db.execute(select(func.count(Conversation.id)))).scalar_one()
        )
        threads_7d = (
            await db.execute(
                select(func.count(func.distinct(Conversation.thread_id))).where(
                    Conversation.created_at >= since_7d
                )
            )
        ).scalar_one()

        return AdminOverviewStats(
            users=AdminUsersStats(
                total=total_users, new_7d=new_7d, active_7d=active_7d
            ),
            training=AdminTrainingStats(
                total_checkins=total_checkins,
                checkins_30d=checkins_30d,
                total_plans=total_plans,
                active_plans=active_plans,
            ),
            kb=AdminKbStats(
                total_kbs=total_kbs,
                total_documents=total_documents,
                pending_documents=pending_documents,
                total_chunks=total_chunks,
            ),
            conversation=AdminConversationStats(
                total_threads=total_threads,
                total_messages=total_messages,
                threads_7d=threads_7d,
            ),
        )

    @staticmethod
    async def get_trends(db: AsyncSession, days: int = 30) -> AdminTrends:
        today = date.today()
        start_date = today - timedelta(days=days - 1)
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        series = [start_date + timedelta(days=i) for i in range(days)]
        date_map = {d.isoformat(): 0 for d in series}

        def merge(counter: dict[date, int]) -> list[int]:
            merged = dict(date_map)
            for d, n in counter.items():
                merged[d.isoformat()] = n
            return [merged[k] for k in merged]

        reg_rows = (
            await db.execute(
                select(func.date(User.created_at).label("d"), func.count(User.id))
                .where(User.created_at >= start_dt)
                .group_by(func.date(User.created_at))
            )
        ).all()
        registrations = merge({d: n for d, n in reg_rows})

        checkin_rows = (
            await db.execute(
                select(Checkin.date, func.count(Checkin.id))
                .where(Checkin.date >= start_date)
                .group_by(Checkin.date)
            )
        ).all()
        checkins = merge({d: n for d, n in checkin_rows})

        active_rows = (
            await db.execute(
                select(
                    Checkin.date, func.count(func.distinct(Checkin.user_id))
                )
                .where(Checkin.date >= start_date)
                .group_by(Checkin.date)
            )
        ).all()
        active_users = merge({d: n for d, n in active_rows})

        conv_rows = (
            await db.execute(
                select(
                    func.date(Conversation.created_at).label("d"),
                    func.count(Conversation.id),
                )
                .where(Conversation.created_at >= start_dt)
                .group_by(func.date(Conversation.created_at))
            )
        ).all()
        conversations = merge({d: n for d, n in conv_rows})

        return AdminTrends(
            days=[d.isoformat() for d in series],
            registrations=registrations,
            checkins=checkins,
            conversations=conversations,
            active_users=active_users,
        )

    # ============================================================
    # 知识库管理列表（统计列 + 搜索 + 分页）
    # ============================================================

    @staticmethod
    async def list_kbs_admin(
        db: AsyncSession,
        page: int = 1,
        size: int = 20,
        keyword: Optional[str] = None,
    ) -> tuple[list[AdminKbListItem], int]:
        filters = []
        if keyword:
            kw = f"%{keyword.strip()}%"
            filters.append(or_(KnowledgeBase.name.ilike(kw), KnowledgeBase.slug.ilike(kw)))

        total = (
            await db.execute(select(func.count(KnowledgeBase.id)).where(*filters))
        ).scalar_one()

        stmt = (
            select(
                KnowledgeBase,
                func.count(func.distinct(KBDocument.id)).label("document_count"),
                func.count(func.distinct(KBChunk.id)).label("chunk_count"),
                func.count(func.distinct(KBDocument.id))
                .filter(
                    (KBDocument.last_indexed_at.is_(None))
                    | (KBDocument.status == "failed")
                )
                .label("pending_document_count"),
            )
            .outerjoin(KBDocument, KBDocument.kb_id == KnowledgeBase.id)
            .outerjoin(KBChunk, KBChunk.document_id == KBDocument.id)
            .where(*filters)
            .group_by(KnowledgeBase.id)
            .order_by(KnowledgeBase.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = (await db.execute(stmt)).all()
        items = [
            AdminKbListItem(
                id=kb.id,
                name=kb.name,
                slug=kb.slug,
                description=kb.description or "",
                owner_name=kb.owner.name if kb.owner else None,
                document_count=doc_count or 0,
                chunk_count=chunk_count or 0,
                pending_document_count=pending or 0,
                created_at=kb.created_at,
                updated_at=kb.updated_at,
            )
            for kb, doc_count, chunk_count, pending in rows
        ]
        return items, total
