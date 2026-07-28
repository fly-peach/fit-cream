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
from src.fitme.schemas.checkin import CheckinCreate, CheckinUpdate
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

        # 预校验 exercise_id 存在性
        if data.exercises:
            exercise_ids = [ex.exercise_id for ex in data.exercises]
            result = await db.execute(
                select(Exercise.id).where(Exercise.id.in_(exercise_ids))
            )
            found_ids = {row[0] for row in result.all()}
            missing_ids = set(exercise_ids) - found_ids
            if missing_ids:
                raise BadRequestException(
                    f"动作不存在: {', '.join(str(m) for m in missing_ids)}"
                )

        checkin = Checkin(
            user_id=user_id,
            plan_day_id=data.plan_day_id,
            date=data.date,
            duration_min=data.duration_min,
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
                sets_done=ex_data.sets_done,
                reps_done=ex_data.reps_done,
                weight_kg=ex_data.weight_kg,
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

        update_data = data.model_dump(exclude_unset=True)
        has_exercises_update = "exercises" in update_data
        exercises_data = update_data.pop("exercises", None)

        for field, value in update_data.items():
            setattr(checkin, field, value)

        # 替换打卡动作记录
        if has_exercises_update:
            await db.execute(
                delete(CheckinExercise).where(
                    CheckinExercise.checkin_id == checkin_id
                )
            )
            if exercises_data:
                for ex_data in exercises_data:
                    checkin_exercise = CheckinExercise(
                        checkin_id=checkin_id,
                        exercise_id=ex_data["exercise_id"],
                        sets_done=ex_data.get("sets_done"),
                        reps_done=ex_data.get("reps_done"),
                        weight_kg=ex_data.get("weight_kg"),
                    )
                    db.add(checkin_exercise)

        await db.flush()
        await db.refresh(checkin)
        return checkin

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
