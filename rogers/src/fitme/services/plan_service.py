"""
训练计划服务

提供训练计划的完整 CRUD 和智能生成逻辑：
- 手动创建/更新/删除计划
- 根据用户目标自动生成计划（Agent create_plan_tool 调用）
- 训练日/动作的增删改（Agent add/remove/update 系列工具调用）
"""
from datetime import date as date_type
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.fitme.models.exercise import Exercise
from src.fitme.models.plan import Plan, PlanDay, PlanDayExercise
from src.fitme.schemas.plan import (
    PlanCreate,
    PlanDayCreate,
    PlanDayUpdate,
    PlanExerciseCreate,
    PlanExerciseUpdate,
    PlanUpdate,
)
from utils.exceptions import ForbiddenException, NotFoundException


class PlanService:
    @staticmethod
    async def _verify_plan_day_ownership(
        db: AsyncSession,
        plan_day_id: UUID,
        user_id: UUID,
    ) -> Tuple[PlanDay, Plan]:
        """验证训练日归属，返回 (plan_day, plan)"""
        result = await db.execute(
            select(PlanDay, Plan)
            .join(Plan, PlanDay.plan_id == Plan.id)
            .where(PlanDay.id == plan_day_id)
        )
        row = result.one_or_none()
        if not row:
            raise NotFoundException("训练日不存在")
        plan_day, plan = row
        if plan.user_id != user_id:
            raise ForbiddenException("无权操作此训练日")
        return plan_day, plan

    @staticmethod
    async def _verify_exercise_ownership(
        db: AsyncSession,
        exercise_id: UUID,
        user_id: UUID,
    ) -> Tuple[PlanDayExercise, PlanDay, Plan]:
        """验证训练日动作归属，返回 (exercise, plan_day, plan)"""
        result = await db.execute(
            select(PlanDayExercise, PlanDay, Plan)
            .join(PlanDay, PlanDayExercise.plan_day_id == PlanDay.id)
            .join(Plan, PlanDay.plan_id == Plan.id)
            .where(PlanDayExercise.id == exercise_id)
        )
        row = result.one_or_none()
        if not row:
            raise NotFoundException("动作不存在")
        plan_exercise, plan_day, plan = row
        if plan.user_id != user_id:
            raise ForbiddenException("无权操作此动作")
        return plan_exercise, plan_day, plan

    @staticmethod
    async def create_plan(
        db: AsyncSession,
        user_id: UUID,
        data: PlanCreate,
    ) -> Plan:
        """创建训练计划"""
        plan = Plan(
            user_id=user_id,
            name=data.name,
            goal=data.goal,
            difficulty=data.difficulty or "beginner",
            weeks=data.weeks,
            status="active",
        )
        db.add(plan)
        await db.flush()

        if data.days:
            for day_data in data.days:
                await PlanService._create_plan_day(db, plan.id, day_data)

        await db.refresh(plan)
        return plan

    @staticmethod
    async def _create_plan_day(
        db: AsyncSession,
        plan_id: UUID,
        data: PlanDayCreate,
    ) -> PlanDay:
        """创建训练日"""
        day_id = uuid4()
        plan_day = PlanDay(
            id=day_id,
            plan_id=plan_id,
            day_of_week=data.day_of_week,
            focus=data.focus,
            rest_seconds=data.rest_seconds,
            metadata_=data.metadata_ or {},
        )
        db.add(plan_day)

        for i, ex_data in enumerate(data.exercises):
            plan_exercise = PlanDayExercise(
                id=uuid4(),
                plan_day_id=day_id,
                exercise_id=ex_data.exercise_id,
                custom_name=ex_data.custom_name,
                exercise_type=ex_data.exercise_type,
                sets=ex_data.sets,
                reps=ex_data.reps,
                weight_kg=ex_data.weight_kg,
                duration_min=ex_data.duration_min,
                distance_km=ex_data.distance_km,
                calories_per_min=ex_data.calories_per_min,
                sort_order=ex_data.sort_order or i,
                notes=ex_data.notes,
                metadata_=ex_data.metadata_ or {},
            )
            db.add(plan_exercise)

        await db.flush()
        return plan_day

    @staticmethod
    async def list_plans(
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        size: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[Plan], int]:
        """获取计划列表"""
        query = select(Plan).where(Plan.user_id == user_id)
        count_query = select(func.count()).select_from(Plan).where(Plan.user_id == user_id)

        if status:
            query = query.where(Plan.status == status)
            count_query = count_query.where(Plan.status == status)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = (
            query.order_by(Plan.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await db.execute(query)
        plans = list(result.scalars().all())

        return plans, total

    @staticmethod
    async def get_plan_detail(
        db: AsyncSession,
        plan_id: UUID,
        user_id: UUID,
    ) -> Plan:
        """获取计划详情（含训练日和动作）"""
        result = await db.execute(
            select(Plan)
            .options(
                selectinload(Plan.days).selectinload(PlanDay.exercises)
            )
            .where(Plan.id == plan_id)
            # 会话 expire_on_commit=False：增删训练日/动作后，identity map 中的 Plan
            # 仍持有旧的 days 集合；populate_existing 强制用本次查询结果覆盖，保证返回最新
            .execution_options(populate_existing=True)
        )
        plan = result.scalar_one_or_none()

        if not plan:
            raise NotFoundException("计划不存在")
        if plan.user_id != user_id:
            raise ForbiddenException("无权访问此计划")

        return plan

    @staticmethod
    async def get_active_plan(
        db: AsyncSession,
        user_id: UUID,
    ) -> Optional[Plan]:
        """获取用户当前活跃计划"""
        result = await db.execute(
            select(Plan)
            .where(Plan.user_id == user_id, Plan.status == "active")
            .order_by(Plan.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_plan_day_for_date(
        db: AsyncSession,
        user_id: UUID,
        target_date: date_type,
    ) -> Optional[Tuple[Plan, PlanDay]]:
        """获取活跃计划中与指定日期星期几匹配的训练日（供打卡关联计划）。

        显式 selectinload 预加载 exercises -> exercise，避免异步懒加载报错
        （同 generate_plan_from_goal 的处理）。无活跃计划或该星期几无训练日时返回 None。
        """
        plan = await PlanService.get_active_plan(db, user_id)
        if not plan:
            return None

        result = await db.execute(
            select(PlanDay)
            .options(
                selectinload(PlanDay.exercises).selectinload(PlanDayExercise.exercise)
            )
            .where(
                PlanDay.plan_id == plan.id,
                PlanDay.day_of_week == target_date.isoweekday(),
            )
            .order_by(PlanDay.id)
            .limit(1)
        )
        plan_day = result.scalars().first()
        if not plan_day:
            return None
        return plan, plan_day

    @staticmethod
    async def update_plan(
        db: AsyncSession,
        plan_id: UUID,
        user_id: UUID,
        data: PlanUpdate,
    ) -> Plan:
        """更新训练计划"""
        plan = await PlanService.get_plan_detail(db, plan_id, user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(plan, field, value)

        await db.flush()
        await db.refresh(plan)
        return plan

    @staticmethod
    async def delete_plan(
        db: AsyncSession,
        plan_id: UUID,
        user_id: UUID,
    ) -> None:
        """软删除计划（设为 archived，训练日与动作保留）"""
        plan = await PlanService.get_plan_detail(db, plan_id, user_id)
        plan.status = "archived"
        await db.flush()

    @staticmethod
    async def add_plan_day(
        db: AsyncSession,
        plan_id: UUID,
        user_id: UUID,
        data: PlanDayCreate,
    ) -> PlanDay:
        """为计划添加训练日"""
        await PlanService.get_plan_detail(db, plan_id, user_id)
        plan_day = await PlanService._create_plan_day(db, plan_id, data)
        await db.flush()
        return plan_day

    @staticmethod
    async def update_plan_day(
        db: AsyncSession,
        plan_day_id: UUID,
        user_id: UUID,
        data: PlanDayUpdate,
    ) -> PlanDay:
        """更新训练日"""
        plan_day, _ = await PlanService._verify_plan_day_ownership(
            db, plan_day_id, user_id
        )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(plan_day, field, value)

        await db.flush()
        await db.refresh(plan_day)
        return plan_day

    @staticmethod
    def _parse_equipment_preferences(
        preferences: Optional[str],
    ) -> Optional[set]:
        """从偏好自由文本解析器械约束集合，无命中返回 None（不限）。

        多个约束可叠加（如「家里有哑铃」-> {bodyweight, dumbbell}）。
        伤病类偏好（如「膝盖有伤」）仅记录，不做过滤（难度/禁忌过滤超出本次范围）。
        """
        if not preferences:
            return None
        text = preferences.lower()
        result: set = set()
        # 无器械/居家/自重 -> bodyweight；「无器械」含「器械」子串，故 machine 判断需排除该场景
        no_equipment = any(
            k in text for k in ("无器械", "没器械", "没有器械", "无设备", "没有设备")
        )
        if (
            no_equipment
            or any(k in text for k in ("家里", "居家", "在家", "home"))
            or "自重" in text
        ):
            result.add("bodyweight")
        if "哑铃" in text or "dumbbell" in text:
            result.add("dumbbell")
        if "杠铃" in text or "barbell" in text:
            result.add("barbell")
        if "壶铃" in text or "kettlebell" in text:
            result.add("kettlebell")
        if "弹力带" in text or "band" in text:
            result.add("band")
        # 「器械」单独指综合器械；无器械场景下不叠加 machine
        if not no_equipment and ("器械" in text or "machine" in text):
            result.add("machine")
        return result or None

    @staticmethod
    async def generate_plan_from_goal(
        db: AsyncSession,
        user_id: UUID,
        goal: str,
        days_per_week: int,
        difficulty: str = "beginner",
        preferences: Optional[str] = None,
        user_data: Optional[dict] = None,
    ) -> Plan:
        """根据目标智能生成计划（Agent 调用）"""
        goal_names = {
            "lose_fat": "减脂塑形",
            "gain_muscle": "增肌力量",
            "maintain": "保持健康",
            "improve_health": "体能提升",
        }
        goal_name = goal_names.get(goal, "综合训练")

        difficulty_config = {
            "beginner": {"sets": 3, "reps": 12, "rest": 60},
            "intermediate": {"sets": 4, "reps": 10, "rest": 90},
            "advanced": {"sets": 5, "reps": 8, "rest": 120},
        }
        config = difficulty_config.get(difficulty, difficulty_config["beginner"])

        plan = Plan(
            user_id=user_id,
            name=f"{goal_name}计划 - 每周{days_per_week}天",
            goal=goal,
            difficulty=difficulty,
            weeks=8,
            status="active",
        )
        db.add(plan)
        await db.flush()

        day_focuses = {
            1: "胸部 + 三头",
            2: "背部 + 二头",
            3: "腿部",
            4: "肩部 + 核心",
            5: "全身有氧",
            6: "上肢综合",
            7: "休息 / 拉伸",
        }

        focus_to_muscle = {
            "胸部 + 三头": "chest",
            "背部 + 二头": "back",
            "腿部": "legs",
            "肩部 + 核心": "shoulders",
            "全身有氧": "full_body",
            "上肢综合": "arms",
        }

        training_days = list(range(1, min(days_per_week, 7) + 1))

        # 解析器械偏好约束（如「家里没器械」-> {bodyweight}），无命中则不限
        allowed_eq = PlanService._parse_equipment_preferences(preferences)
        used_ids: set = set()

        for day_num in training_days:
            focus = day_focuses.get(day_num, "综合训练")
            muscle_group = focus_to_muscle.get(focus)

            day_id = uuid4()
            plan_day = PlanDay(
                id=day_id,
                plan_id=plan.id,
                day_of_week=day_num,
                focus=focus,
                rest_seconds=config["rest"],
            )
            db.add(plan_day)

            # 查询匹配肌群的动作填充训练日
            if muscle_group:
                # 复合动作优先 + 难度升序；叠加器械约束
                base = (
                    select(Exercise)
                    .where(Exercise.muscle_group == muscle_group)
                    .order_by(
                        Exercise.is_compound.desc(),
                        Exercise.difficulty.nulls_last(),
                    )
                )
                if allowed_eq:
                    base = base.where(Exercise.equipment.in_(allowed_eq))
                candidates = list(
                    (await db.execute(base.limit(8))).scalars().all()
                )
                fresh = [c for c in candidates if c.id not in used_ids]
                # 回退：器械约束后可用候选不足，放宽约束补足（保证训练日有动作）
                if allowed_eq and len(fresh) < 3:
                    relaxed = (
                        select(Exercise)
                        .where(Exercise.muscle_group == muscle_group)
                        .order_by(
                            Exercise.is_compound.desc(),
                            Exercise.difficulty.nulls_last(),
                        )
                        .limit(8)
                    )
                    candidates = list((await db.execute(relaxed)).scalars().all())
                    fresh = [c for c in candidates if c.id not in used_ids]
                # 难度偏好排前（不硬过滤），复合动作优先，跨天去重，取 3 个
                fresh.sort(
                    key=lambda c: (
                        not c.is_compound,
                        0 if c.difficulty == difficulty else 1,
                        c.name or "",
                    )
                )
                for i, ex in enumerate(fresh[:3]):
                    used_ids.add(ex.id)
                    db.add(
                        PlanDayExercise(
                            id=uuid4(),
                            plan_day_id=day_id,
                            exercise_id=ex.id,
                            sets=config["sets"],
                            reps=config["reps"],
                            sort_order=i,
                        )
                    )

        await db.flush()
        # 预加载 days -> exercises -> exercise，避免工具层访问关系触发异步懒加载
        # （async SQLAlchemy 下同步访问关系会抛 greenlet_spawn has not been called）
        result = await db.execute(
            select(Plan)
            .options(
                selectinload(Plan.days)
                .selectinload(PlanDay.exercises)
                .selectinload(PlanDayExercise.exercise)
            )
            .where(Plan.id == plan.id)
        )
        return result.scalar_one()

    @staticmethod
    async def update_exercise(
        db: AsyncSession,
        exercise_id: UUID,
        user_id: UUID,
        data: PlanExerciseUpdate,
    ) -> Tuple[PlanDayExercise, Plan]:
        """更新训练日中的单个动作，返回 (plan_exercise, plan)"""
        plan_exercise, _, plan = await PlanService._verify_exercise_ownership(
            db, exercise_id, user_id
        )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(plan_exercise, field, value)

        await db.flush()
        await db.refresh(plan_exercise)
        return plan_exercise, plan

    @staticmethod
    async def delete_exercise(
        db: AsyncSession,
        exercise_id: UUID,
        user_id: UUID,
    ) -> Tuple[PlanDayExercise, Plan]:
        """删除训练日中的单个动作，返回 (plan_exercise, plan)"""
        plan_exercise, _, plan = await PlanService._verify_exercise_ownership(
            db, exercise_id, user_id
        )

        await db.delete(plan_exercise)
        await db.flush()
        return plan_exercise, plan

    @staticmethod
    async def add_exercise_to_day(
        db: AsyncSession,
        plan_day_id: UUID,
        user_id: UUID,
        data: PlanExerciseCreate,
    ) -> Tuple[PlanDayExercise, Plan]:
        """为训练日添加动作，返回 (plan_exercise, plan)"""
        _, plan = await PlanService._verify_plan_day_ownership(db, plan_day_id, user_id)

        plan_exercise = PlanDayExercise(
            id=uuid4(),
            plan_day_id=plan_day_id,
            exercise_id=data.exercise_id,
            custom_name=data.custom_name if not data.exercise_id else None,
            exercise_type=data.exercise_type,
            sets=data.sets,
            reps=data.reps,
            weight_kg=data.weight_kg,
            duration_min=data.duration_min,
            distance_km=data.distance_km,
            calories_per_min=data.calories_per_min,
            sort_order=data.sort_order,
            notes=data.notes,
            metadata_=data.metadata_ or {},
        )
        db.add(plan_exercise)
        await db.flush()
        await db.refresh(plan_exercise)
        return plan_exercise, plan

    @staticmethod
    async def delete_plan_day(
        db: AsyncSession,
        plan_day_id: UUID,
        user_id: UUID,
    ) -> Tuple[PlanDay, Plan]:
        """删除训练日，返回 (plan_day, plan)"""
        plan_day, plan = await PlanService._verify_plan_day_ownership(
            db, plan_day_id, user_id
        )

        await db.delete(plan_day)
        await db.flush()
        return plan_day, plan

