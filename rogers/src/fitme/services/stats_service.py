"""
统计服务

提供多维度训练数据统计：
- 周统计：训练次数、时长、消耗热量、每日明细
- 月统计：月度趋势、按周分组、平均心情、强度分布
- 体重趋势：当前身体数据 + BMI
- 全部统计：累计训练量 + 连续打卡天数 + 累计消耗热量
- 饮食统计：每日营养汇总趋势
"""

from datetime import date, timedelta
from typing import List, Optional, TypedDict
from uuid import UUID

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.checkin import Checkin, CheckinExercise
from src.fitme.models.diet_meal import DailyDietSummary
from src.fitme.models.user import User
from src.fitme.services.checkin_service import CheckinService
from utils.exceptions import NotFoundException


class WeeklyStats(TypedDict):
    week_start: str
    week_end: str
    total_workouts: int
    total_duration_min: int
    total_sets: int
    total_calories: int
    daily_breakdown: list


class MonthlyStats(TypedDict):
    year: int
    month: int
    total_workouts: int
    total_duration_min: int
    total_calories: int
    average_mood: Optional[float]
    intensity_distribution: dict
    weekly_trend: list


class BodyTrend(TypedDict):
    current_weight_kg: Optional[float]
    height_cm: Optional[float]
    goal: Optional[str]


class AllStats(TypedDict):
    total_workouts: int
    total_duration_min: int
    total_calories: int
    current_streak: int
    longest_streak: int


class DietTrendItem(TypedDict):
    summary_date: str
    total_calories: int
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    meal_count: int


class StatsService:
    @staticmethod
    async def get_weekly_stats(
        db: AsyncSession,
        user_id: UUID,
        week_start: Optional[date] = None,
    ) -> WeeklyStats:
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
        total_calories = sum(c.calories_burned or 0 for c in checkins)

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
                    "calories_burned": day_checkin.calories_burned or 0 if day_checkin else 0,
                    "intensity": day_checkin.actual_intensity if day_checkin else None,
                }
            )

        return {
            "week_start": str(week_start),
            "week_end": str(week_end),
            "total_workouts": total_workouts,
            "total_duration_min": total_duration,
            "total_sets": total_sets,
            "total_calories": total_calories,
            "daily_breakdown": daily_breakdown,
        }

    @staticmethod
    async def get_monthly_trend(
        db: AsyncSession,
        user_id: UUID,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> MonthlyStats:
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
                func.coalesce(func.sum(Checkin.calories_burned), 0),
                func.avg(Checkin.mood),
            ).where(
                Checkin.user_id == user_id,
                Checkin.date >= month_start,
                Checkin.date <= month_end,
            )
        )
        total_workouts, total_duration, total_calories, avg_mood = agg_result.one()
        total_workouts = int(total_workouts or 0)
        total_duration = int(total_duration or 0)
        total_calories = int(total_calories or 0)
        avg_mood = round(float(avg_mood), 1) if avg_mood else None

        intensity_result = await db.execute(
            select(
                Checkin.actual_intensity,
                func.count(),
            ).where(
                Checkin.user_id == user_id,
                Checkin.date >= month_start,
                Checkin.date <= month_end,
                Checkin.actual_intensity.isnot(None),
            ).group_by(Checkin.actual_intensity)
        )
        intensity_distribution = {
            row[0]: row[1] for row in intensity_result.all()
        }

        week_expr = (func.floor((extract("day", Checkin.date) - 1) / 7) + 1).label(
            "week"
        )
        week_result = await db.execute(
            select(
                week_expr,
                func.count().label("workouts"),
                func.coalesce(func.sum(Checkin.duration_min), 0).label("duration_min"),
                func.coalesce(func.sum(Checkin.calories_burned), 0).label("calories"),
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
                "calories": int(row.calories),
            }
            for row in week_result.all()
        ]

        return {
            "year": year,
            "month": month,
            "total_workouts": total_workouts,
            "total_duration_min": total_duration,
            "total_calories": total_calories,
            "average_mood": avg_mood,
            "intensity_distribution": intensity_distribution,
            "weekly_trend": weekly_trend,
        }

    @staticmethod
    async def get_body_trend(
        db: AsyncSession,
        user_id: UUID,
        days: int = 30,
    ) -> BodyTrend:
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
        agg_result = await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Checkin.duration_min), 0),
                func.coalesce(func.sum(Checkin.calories_burned), 0),
            ).where(Checkin.user_id == user_id)
        )
        total_workouts, total_duration, total_calories = agg_result.one()
        total_workouts = int(total_workouts or 0)
        total_duration = int(total_duration or 0)
        total_calories = int(total_calories or 0)

        streak = await CheckinService.get_streak(db, user_id)

        return {
            "total_workouts": total_workouts,
            "total_duration_min": total_duration,
            "total_calories": total_calories,
            "current_streak": streak["current_streak"],
            "longest_streak": streak["longest_streak"],
        }

    @staticmethod
    async def get_diet_trend(
        db: AsyncSession,
        user_id: UUID,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> List[DietTrendItem]:
        if start is None:
            start = date.today() - timedelta(days=7)
        if end is None:
            end = date.today()

        result = await db.execute(
            select(DailyDietSummary)
            .where(
                DailyDietSummary.user_id == user_id,
                DailyDietSummary.summary_date >= start,
                DailyDietSummary.summary_date <= end,
            )
            .order_by(DailyDietSummary.summary_date)
        )
        summaries = result.scalars().all()

        return [
            {
                "summary_date": str(s.summary_date),
                "total_calories": s.total_calories,
                "total_protein_g": float(s.total_protein_g),
                "total_carbs_g": float(s.total_carbs_g),
                "total_fat_g": float(s.total_fat_g),
                "meal_count": s.meal_count,
            }
            for s in summaries
        ]
