"""
打卡服务

提供训练打卡的 CRUD 和连续打卡天数计算：
- 创建打卡（含动作记录，同日不可重复）
- 查询打卡列表（支持日期范围筛选）
- 计算当前/最长连续打卡天数
"""

from datetime import date as date_type
from datetime import timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import Integer, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.checkin import Checkin, CheckinExercise
from src.fitme.models.exercise import Exercise
from src.fitme.models.plan import PlanDayExercise
from src.fitme.schemas.checkin import CheckinCreate, CheckinExerciseCreate, CheckinUpdate
from utils.exceptions import (
    BadRequestException,
    BusinessException,
    ErrorCode,
    ForbiddenException,
    NotFoundException,
)


class CheckinService:
    @staticmethod
    async def create_checkin(
        db: AsyncSession,
        user_id: UUID,
        data: CheckinCreate,
    ) -> Checkin:
        """创建打卡记录"""
        # 检查是否已打卡
        existing = await CheckinService.get_by_date(db, user_id, data.date)
        if existing:
            raise BusinessException(
                ErrorCode.CHECKIN_ALREADY_EXISTS, "该日期已打卡，不能重复打卡"
            )

        # 检查日期不能是未来
        if data.date > date_type.today():
            raise BusinessException(
                ErrorCode.INVALID_DATE, "打卡日期不能是未来日期"
            )

        # 预校验 exercise_id 存在性（自定义动作无 exercise_id，跳过）
        if data.exercises:
            exercise_ids = [ex.exercise_id for ex in data.exercises if ex.exercise_id]
            if exercise_ids:
                result = await db.execute(
                    select(Exercise.id).where(Exercise.id.in_(exercise_ids))
                )
                found_ids = {row[0] for row in result.all()}
                missing_ids = set(exercise_ids) - found_ids
                if missing_ids:
                    raise BadRequestException(
                        f"动作不存在: {', '.join(str(m) for m in missing_ids)}"
                    )

        calorie_rates = await CheckinService._load_calorie_rates(db, data.exercises)
        checkin = Checkin(
            user_id=user_id,
            plan_day_id=data.plan_day_id,
            date=data.date,
            duration_min=data.duration_min,
            actual_intensity=data.actual_intensity,
            calories_burned=data.calories_burned or CheckinService._estimate_calories(
                data.duration_min, data.exercises, calorie_rates
            ),
            mood=data.mood,
            note=data.note,
        )
        db.add(checkin)
        await db.flush()

        # 创建打卡动作记录
        for ex_data in data.exercises:
            checkin_exercise = CheckinExercise(
                checkin_id=checkin.id,
                exercise_id=ex_data.exercise_id,
                custom_name=ex_data.custom_name,
                plan_day_exercise_id=ex_data.plan_day_exercise_id,
                sets_done=ex_data.sets_done,
                reps_done=ex_data.reps_done,
                weight_kg=ex_data.weight_kg,
                duration_min=ex_data.duration_min,
                distance_km=ex_data.distance_km,
                rpe=ex_data.rpe,
                notes=ex_data.notes,
            )
            db.add(checkin_exercise)

        await db.flush()
        await db.refresh(checkin)
        return checkin

    @staticmethod
    async def get_by_date(
        db: AsyncSession,
        user_id: UUID,
        checkin_date: date_type,
    ) -> Optional[Checkin]:
        """获取指定日期的打卡记录"""
        result = await db.execute(
            select(Checkin).where(
                Checkin.user_id == user_id,
                Checkin.date == checkin_date,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        checkin_id: UUID,
        user_id: UUID,
    ) -> Checkin:
        """获取打卡详情"""
        result = await db.execute(
            select(Checkin).where(Checkin.id == checkin_id)
        )
        checkin = result.scalar_one_or_none()

        if not checkin:
            raise NotFoundException("打卡记录不存在")
        if checkin.user_id != user_id:
            raise ForbiddenException("无权访问此打卡记录")

        return checkin

    @staticmethod
    async def list_checkins(
        db: AsyncSession,
        user_id: UUID,
        start: Optional[date_type] = None,
        end: Optional[date_type] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Checkin], int]:
        """获取打卡列表"""
        query = select(Checkin).where(Checkin.user_id == user_id)
        count_query = select(func.count()).select_from(Checkin).where(
            Checkin.user_id == user_id
        )

        if start:
            query = query.where(Checkin.date >= start)
            count_query = count_query.where(Checkin.date >= start)
        if end:
            query = query.where(Checkin.date <= end)
            count_query = count_query.where(Checkin.date <= end)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = (
            query.order_by(Checkin.date.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await db.execute(query)
        checkins = list(result.scalars().all())

        return checkins, total

    @staticmethod
    async def update_checkin(
        db: AsyncSession,
        checkin_id: UUID,
        user_id: UUID,
        data: CheckinUpdate,
    ) -> Checkin:
        """更新打卡记录"""
        checkin = await CheckinService.get_by_id(db, checkin_id, user_id)

        has_exercises_update = "exercises" in data.model_fields_set
        update_data = data.model_dump(exclude_unset=True, exclude={"exercises"})

        for field, value in update_data.items():
            setattr(checkin, field, value)

        # 替换打卡动作记录
        if has_exercises_update:
            await db.execute(
                delete(CheckinExercise).where(
                    CheckinExercise.checkin_id == checkin_id
                )
            )
            exercises_data = data.exercises or []
            for ex_data in exercises_data:
                checkin_exercise = CheckinExercise(
                    checkin_id=checkin_id,
                    exercise_id=ex_data.exercise_id,
                    custom_name=ex_data.custom_name,
                    plan_day_exercise_id=ex_data.plan_day_exercise_id,
                    sets_done=ex_data.sets_done,
                    reps_done=ex_data.reps_done,
                    weight_kg=ex_data.weight_kg,
                    duration_min=ex_data.duration_min,
                    distance_km=ex_data.distance_km,
                    rpe=ex_data.rpe,
                    notes=ex_data.notes,
                )
                db.add(checkin_exercise)
            # 动作列表变化且未显式提供热量时，按新动作行重算估算热量
            if "calories_burned" not in data.model_fields_set:
                rates = await CheckinService._load_calorie_rates(db, exercises_data)
                checkin.calories_burned = CheckinService._estimate_calories(
                    checkin.duration_min, exercises_data, rates
                )

        await db.flush()
        await db.refresh(checkin)
        return checkin

    @staticmethod
    async def _load_calorie_rates(
        db: AsyncSession,
        exercises: List[CheckinExerciseCreate],
    ) -> dict:
        """批量加载动作行可用的 calories_per_min（计划动作 -> 动作库），供热量估算。

        返回 {("pde", plan_day_exercise_id): rate, ("ex", exercise_id): rate}；
        无数据的键缺失，估算时回退默认值。
        """
        rates: dict = {}
        pde_ids = [ex.plan_day_exercise_id for ex in exercises if ex.plan_day_exercise_id]
        if pde_ids:
            result = await db.execute(
                select(PlanDayExercise.id, PlanDayExercise.calories_per_min).where(
                    PlanDayExercise.id.in_(pde_ids)
                )
            )
            for pde_id, rate in result.all():
                if rate is not None:
                    rates[("pde", pde_id)] = float(rate)
        ex_ids = [ex.exercise_id for ex in exercises if ex.exercise_id]
        if ex_ids:
            result = await db.execute(
                select(Exercise.id, Exercise.calories_per_min).where(
                    Exercise.id.in_(ex_ids)
                )
            )
            for ex_id, rate in result.all():
                if rate is not None:
                    rates[("ex", ex_id)] = float(rate)
        return rates

    @staticmethod
    def _estimate_calories(
        duration_min: Optional[int],
        exercises: List[CheckinExerciseCreate],
        calorie_rates: Optional[dict] = None,
    ) -> int:
        """按动作行估算消耗热量。

        - 有氧行（duration_min 非空）：(calories_per_min 或 8.0) × duration_min，
          calories_per_min 解析顺序：计划动作 -> 动作库 -> 默认 8.0（中等强度有氧）
        - 力量行：sets_done × reps_done × 0.15（粗略常量：每次做功约 0.15 kcal）
        - 无可利用的动作数据：回退 duration × 7 kcal/min
        """
        if not exercises:
            return int((duration_min or 0) * 7)
        rates = calorie_rates or {}
        total = 0.0
        has_data = False
        for ex in exercises:
            if ex.duration_min:
                has_data = True
                rate = None
                if ex.plan_day_exercise_id:
                    rate = rates.get(("pde", ex.plan_day_exercise_id))
                if rate is None and ex.exercise_id:
                    rate = rates.get(("ex", ex.exercise_id))
                total += (rate or 8.0) * ex.duration_min
            elif ex.sets_done and ex.reps_done:
                has_data = True
                total += ex.sets_done * ex.reps_done * 0.15
        if not has_data:
            return int((duration_min or 0) * 7)
        return int(total)

    @staticmethod
    async def get_streak(
        db: AsyncSession,
        user_id: UUID,
    ) -> dict:
        """计算连续打卡天数"""
        # 获取最近打卡日期
        last_result = await db.execute(
            select(func.max(Checkin.date)).where(Checkin.user_id == user_id)
        )
        last_date = last_result.scalar()

        if not last_date:
            return {
                "current_streak": 0,
                "longest_streak": 0,
                "last_checkin_date": None,
            }

        # 查询最近 100 天的打卡日期用于计算当前连续天数（有界查询）
        today = date_type.today()
        lookback = today - timedelta(days=100)
        recent_result = await db.execute(
            select(Checkin.date)
            .where(Checkin.user_id == user_id, Checkin.date >= lookback)
            .order_by(Checkin.date.desc())
        )
        recent_dates = [row[0] for row in recent_result.all()]

        # 计算当前连续天数
        current_streak = 0
        check_date = today

        if recent_dates and recent_dates[0] != today:
            check_date = today - timedelta(days=1)

        for d in recent_dates:
            if d == check_date:
                current_streak += 1
                check_date -= timedelta(days=1)
            elif d < check_date:
                break

        # SQL 窗口函数计算最长连续天数（gaps-and-islands）
        rn = func.row_number().over(order_by=Checkin.date)
        consecutive_cte = (
            select(
                Checkin.date,
                (Checkin.date - cast(rn, Integer)).label("grp"),
            )
            .where(Checkin.user_id == user_id)
            .cte("consecutive")
        )
        group_subq = (
            select(func.count().label("cnt"))
            .select_from(consecutive_cte)
            .group_by(consecutive_cte.c.grp)
            .subquery()
        )
        longest_result = await db.execute(select(func.max(group_subq.c.cnt)))
        longest_streak = longest_result.scalar() or 0

        return {
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "last_checkin_date": last_date,
        }
