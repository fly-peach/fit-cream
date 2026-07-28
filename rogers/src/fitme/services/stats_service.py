"""
统计服务

提供多维度训练数据统计：
- 周统计：本周训练次数、时长、每日明细
- 月统计：月度趋势、按周分组、平均心情
- 体重趋势：当前身体数据 + BMI
- 全部统计：累计训练量 + 连续打卡天数
"""

from datetime import date, timedelta
from typing import List, Optional, TypedDict
from uuid import UUID

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.checkin import Checkin, CheckinExercise
from src.fitme.models.user import User
from src.fitme.services.checkin_service import CheckinService
from utils.exceptions import NotFoundException


class WeeklyStats(TypedDict):
    week_start: str
    week_end: str
    total_workouts: int
    total_duration_min: int
    total_sets: int
    daily_breakdown: list


class MonthlyStats(TypedDict):
    year: int
    month: int
    total_workouts: int
    total_duration_min: int
    average_mood: Optional[float]
    weekly_trend: list


class BodyTrend(TypedDict):
    current_weight_kg: Optional[float]
    height_cm: Optional[float]
    goal: Optional[str]


class AllStats(TypedDict):
    total_workouts: int
    total_duration_min: int
    current_streak: int
    longest_streak: int


class StatsService:
    @staticmethod
    async def get_weekly_stats(
        db: AsyncSession,
        user_id: UUID,
        week_start: Optional[date] = None,
    ) -> WeeklyStats:
        """获取周统计"""
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())

        week_end = week_start + timedelta(days=6)

        result = await db.execute(
            select(Checkin).where(
                Checkin.user_id == user_id,
                Checkin.date >= week_start,
                Checkin.date <= week_end,
            )
        )
        checkins = list(result.scalars().all())

        total_workouts = len(checkins)
        total_duration = sum(c.duration_min for c in checkins)

        total_sets = 0
        if checkins:
            checkin_ids = [c.id for c in checkins]
            ex_result = await db.execute(
                select(CheckinExercise).where(
                    CheckinExercise.checkin_id.in_(checkin_ids)
                )
            )
            all_exercises = list(ex_result.scalars().all())
            total_sets = sum(e.sets_done or 0 for e in all_exercises)

        daily_breakdown = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            day_checkin = next((c for c in checkins if c.date == d), None)
            daily_breakdown.append(
                {
                    "date": str(d),
                    "completed": day_checkin is not None,
                    "duration_min": day_checkin.duration_min if day_checkin else 0,
                }
            )

        return {
            "week_start": str(week_start),
            "week_end": str(week_end),
            "total_workouts": total_workouts,
            "total_duration_min": total_duration,
            "total_sets": total_sets,
            "daily_breakdown": daily_breakdown,
        }

    @staticmethod
    async def get_monthly_trend(
        db: AsyncSession,
        user_id: UUID,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> MonthlyStats:
        """获取月统计"""
        today = date.today()
        if year is None:
            year = today.year
        if month is None:
            month = today.month

        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        agg_result = await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Checkin.duration_min), 0),
                func.avg(Checkin.mood),
            ).where(
                Checkin.user_id == user_id,
                Checkin.date >= month_start,
                Checkin.date <= month_end,
            )
        )
        total_workouts, total_duration, avg_mood = agg_result.one()
        total_workouts = int(total_workouts or 0)
        total_duration = int(total_duration or 0)
        avg_mood = round(float(avg_mood), 1) if avg_mood else None

        week_expr = (func.floor((extract("day", Checkin.date) - 1) / 7) + 1).label(
            "week"
        )
        week_result = await db.execute(
            select(
                week_expr,
                func.count().label("workouts"),
                func.coalesce(func.sum(Checkin.duration_min), 0).label("duration_min"),
            )
            .where(
                Checkin.user_id == user_id,
                Checkin.date >= month_start,
                Checkin.date <= month_end,
            )
            .group_by(week_expr)
            .order_by(week_expr)
        )
        weekly_trend = [
            {
                "week": int(row.week),
                "workouts": int(row.workouts),
                "duration_min": int(row.duration_min),
            }
            for row in week_result.all()
        ]

        return {
            "year": year,
            "month": month,
            "total_workouts": total_workouts,
            "total_duration_min": total_duration,
            "average_mood": avg_mood,
            "weekly_trend": weekly_trend,
        }

    @staticmethod
    async def get_body_trend(
        db: AsyncSession,
        user_id: UUID,
        days: int = 30,
    ) -> BodyTrend:
        """获取体重趋势（从用户资料获取当前体重）"""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundException("用户不存在")

        current_weight = float(user.weight_kg) if user.weight_kg else None

        return {
            "current_weight_kg": current_weight,
            "height_cm": float(user.height_cm) if user.height_cm else None,
            "goal": user.goal,
        }

    @staticmethod
    async def get_all_stats(
        db: AsyncSession,
        user_id: UUID,
    ) -> AllStats:
        """获取全部统计"""
        agg_result = await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Checkin.duration_min), 0),
            ).where(Checkin.user_id == user_id)
        )
        total_workouts, total_duration = agg_result.one()
        total_workouts = int(total_workouts or 0)
        total_duration = int(total_duration or 0)

        streak = await CheckinService.get_streak(db, user_id)

        return {
            "total_workouts": total_workouts,
            "total_duration_min": total_duration,
            "current_streak": streak["current_streak"],
            "longest_streak": streak["longest_streak"],
        }
