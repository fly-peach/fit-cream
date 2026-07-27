"""
训练计划服务

提供训练计划的完整 CRUD 和智能生成逻辑：
- 手动创建/更新/删除计划
- 根据用户目标自动生成计划（Agent create_plan_tool 调用）
- 计划调整（Agent adjust_plan_tool 调用）
"""
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.plan import Plan, PlanDay, PlanDayExercise
from src.fitme.schemas.plan import (
    PlanCreate,
    PlanDayCreate,
    PlanExerciseCreate,
    PlanExerciseUpdate,
    PlanUpdate,
)
from utils.exceptions import ForbiddenException, NotFoundException


class PlanService:
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

        # 如果包含训练日，一并创建
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
        plan_day = PlanDay(
            plan_id=plan_id,
            day_of_week=data.day_of_week,
            focus=data.focus,
            rest_seconds=data.rest_seconds,
        )
        db.add(plan_day)
        await db.flush()

        # 创建训练日动作
        for i, ex_data in enumerate(data.exercises):
            plan_exercise = PlanDayExercise(
                plan_day_id=plan_day.id,
                exercise_id=ex_data.exercise_id,
                sets=ex_data.sets,
                reps=ex_data.reps,
                weight_kg=ex_data.weight_kg,
                sort_order=ex_data.sort_order or i,
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

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
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
            select(Plan).where(Plan.id == plan_id)
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
        """软删除计划（设为 archived）"""
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
        # 验证计划归属
        await PlanService.get_plan_detail(db, plan_id, user_id)
        plan_day = await PlanService._create_plan_day(db, plan_id, data)
        await db.flush()
        return plan_day

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
        # 目标名称映射
        goal_names = {
            "lose_fat": "减脂塑形",
            "gain_muscle": "增肌力量",
            "maintain": "保持健康",
            "improve_health": "体能提升",
        }
        goal_name = goal_names.get(goal, "综合训练")

        # 根据难度设置训练参数
        difficulty_config = {
            "beginner": {"sets": 3, "reps": 12, "rest": 60},
            "intermediate": {"sets": 4, "reps": 10, "rest": 90},
            "advanced": {"sets": 5, "reps": 8, "rest": 120},
        }
        config = difficulty_config.get(difficulty, difficulty_config["beginner"])

        # 创建计划
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

        # 根据每周天数分配训练日
        # 默认分配：1=周一, 2=周二, 3=周三, 4=周四, 5=周五, 6=周六, 7=周日
        day_focuses = {
            1: "胸部 + 三头",
            2: "背部 + 二头",
            3: "腿部",
            4: "肩部 + 核心",
            5: "全身有氧",
            6: "上肢综合",
            7: "休息 / 拉伸",
        }

        # 均匀分配训练日
        if days_per_week <= 5:
            training_days = list(range(1, days_per_week + 1))
        else:
            training_days = list(range(1, 6)) + [6][: days_per_week - 5]

        for day_num in training_days:
            plan_day = PlanDay(
                plan_id=plan.id,
                day_of_week=day_num,
                focus=day_focuses.get(day_num, "综合训练"),
                rest_seconds=config["rest"],
            )
            db.add(plan_day)

        await db.flush()
        await db.refresh(plan)
        return plan

    @staticmethod
    async def update_exercise(
        db: AsyncSession,
        exercise_id: UUID,
        user_id: UUID,
        data: PlanExerciseUpdate,
    ) -> PlanDayExercise:
        """更新训练日中的单个动作"""
        result = await db.execute(
            select(PlanDayExercise).where(PlanDayExercise.id == exercise_id)
        )
        plan_exercise = result.scalar_one_or_none()
        if not plan_exercise:
            raise NotFoundException("动作不存在")

        # 验证归属：通过 plan_day -> plan -> user_id
        day_result = await db.execute(
            select(PlanDay).where(PlanDay.id == plan_exercise.plan_day_id)
        )
        plan_day = day_result.scalar_one()
        plan_result = await db.execute(
            select(Plan).where(Plan.id == plan_day.plan_id)
        )
        plan = plan_result.scalar_one()
        if plan.user_id != user_id:
            raise ForbiddenException("无权修改此动作")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(plan_exercise, field, value)

        await db.flush()
        await db.refresh(plan_exercise)
        return plan_exercise

    @staticmethod
    async def delete_exercise(
        db: AsyncSession,
        exercise_id: UUID,
        user_id: UUID,
    ) -> None:
        """删除训练日中的单个动作"""
        result = await db.execute(
            select(PlanDayExercise).where(PlanDayExercise.id == exercise_id)
        )
        plan_exercise = result.scalar_one_or_none()
        if not plan_exercise:
            raise NotFoundException("动作不存在")

        # 验证归属
        day_result = await db.execute(
            select(PlanDay).where(PlanDay.id == plan_exercise.plan_day_id)
        )
        plan_day = day_result.scalar_one()
        plan_result = await db.execute(
            select(Plan).where(Plan.id == plan_day.plan_id)
        )
        plan = plan_result.scalar_one()
        if plan.user_id != user_id:
            raise ForbiddenException("无权删除此动作")

        await db.delete(plan_exercise)
        await db.flush()

    @staticmethod
    async def add_exercise_to_day(
        db: AsyncSession,
        plan_day_id: UUID,
        user_id: UUID,
        data: PlanExerciseCreate,
    ) -> PlanDayExercise:
        """为训练日添加动作"""

        # 验证归属
        day_result = await db.execute(
            select(PlanDay).where(PlanDay.id == plan_day_id)
        )
        plan_day = day_result.scalar_one_or_none()
        if not plan_day:
            raise NotFoundException("训练日不存在")
        plan_result = await db.execute(
            select(Plan).where(Plan.id == plan_day.plan_id)
        )
        plan = plan_result.scalar_one()
        if plan.user_id != user_id:
            raise ForbiddenException("无权操作此训练日")

        plan_exercise = PlanDayExercise(
            plan_day_id=plan_day_id,
            exercise_id=data.exercise_id,
            sets=data.sets,
            reps=data.reps,
            weight_kg=data.weight_kg,
            sort_order=data.sort_order,
        )
        db.add(plan_exercise)
        await db.flush()
        await db.refresh(plan_exercise)
        return plan_exercise

    @staticmethod
    async def delete_plan_day(
        db: AsyncSession,
        plan_day_id: UUID,
        user_id: UUID,
    ) -> None:
        """删除训练日"""
        day_result = await db.execute(
            select(PlanDay).where(PlanDay.id == plan_day_id)
        )
        plan_day = day_result.scalar_one_or_none()
        if not plan_day:
            raise NotFoundException("训练日不存在")
        plan_result = await db.execute(
            select(Plan).where(Plan.id == plan_day.plan_id)
        )
        plan = plan_result.scalar_one()
        if plan.user_id != user_id:
            raise ForbiddenException("无权删除此训练日")

        await db.delete(plan_day)
        await db.flush()

    @staticmethod
    async def adjust_plan(
        db: AsyncSession,
        plan: Plan,
        action: str,
        details: str,
    ) -> dict:
        """调整计划"""
        changes = {"action": action, "details": details, "summary": ""}

        if action == "change_difficulty":
            old_difficulty = plan.difficulty
            if "初级" in details or "beginner" in details.lower():
                plan.difficulty = "beginner"
            elif "中级" in details or "intermediate" in details.lower():
                plan.difficulty = "intermediate"
            elif "高级" in details or "advanced" in details.lower():
                plan.difficulty = "advanced"
            changes["summary"] = f"难度从 {old_difficulty} 调整为 {plan.difficulty}"

        elif action == "remove_day":
            # 移除最后一个训练日
            if plan.days:
                last_day = plan.days[-1]
                await db.delete(last_day)
                changes["summary"] = f"移除了 {last_day.focus or '训练日'}"
            else:
                changes["summary"] = "没有可移除的训练日"

        else:
            changes["summary"] = f"执行了调整：{details}"

        await db.flush()
        return changes