"""
统计服务

提供多维度训练数据统计：
- 周统计：本周训练次数、时长、每日明细
- 月统计：月度趋势、按周分组、平均心情
- 体重趋势：当前身体数据 + BMI
- 全部统计：累计训练量 + 连续打卡天数
"""

from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkin import Checkin, CheckinExercise
from app.models.user import User


class StatsService:
    @staticmethod
    async def get_weekly_stats(
        db: AsyncSession,
        user_id: UUID,
        week_start: Optional[date] = None,
    ) -> dict:
        """获取周统计"""
        if week_start is None:
            today = date.today()
            # 本周一
            week_start = today - timedelta(days=today.weekday())

        week_end = week_start + timedelta(days=6)

        # 查询本周打卡记录
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

        # 计算总组数
        total_sets = 0
        for checkin in checkins:
            ex_result = await db.execute(
                select(CheckinExercise).where(
                    CheckinExercise.checkin_id == checkin.id
                )
            )
            exercises = list(ex_result.scalars().all())
            total_sets += sum(e.sets_done or 0 for e in exercises)

        # 每日明细
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
    ) -> dict:
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

        result = await db.execute(
            select(Checkin).where(
                Checkin.user_id == user_id,
                Checkin.date >= month_start,
                Checkin.date <= month_end,
            )
        )
        checkins = list(result.scalars().all())

        total_workouts = len(checkins)
        total_duration = sum(c.duration_min for c in checkins)

        # 平均心情
        moods = [c.mood for c in checkins if c.mood is not None]
        avg_mood = sum(moods) / len(moods) if moods else None

        # 按周分组
        weekly_trend = []
        current_week = 1
        week_workouts = 0
        week_duration = 0

        for i, checkin in enumerate(
            sorted(checkins, key=lambda c: c.date)
        ):
            day_of_month = checkin.date.day
            week_num = (day_of_month - 1) // 7 + 1

            if week_num != current_week and i > 0:
                weekly_trend.append(
                    {
                        "week": current_week,
                        "workouts": week_workouts,
                        "duration_min": week_duration,
                    }
                )
                current_week = week_num
                week_workouts = 0
                week_duration = 0

            week_workouts += 1
            week_duration += checkin.duration_min

        # 最后一周
        if week_workouts > 0:
            weekly_trend.append(
                {
                    "week": current_week,
                    "workouts": week_workouts,
                    "duration_min": week_duration,
                }
            )

        return {
            "year": year,
            "month": month,
            "total_workouts": total_workouts,
            "total_duration_min": total_duration,
            "average_mood": round(avg_mood, 1) if avg_mood else None,
            "weekly_trend": weekly_trend,
        }

    @staticmethod
    async def get_body_trend(
        db: AsyncSession,
        user_id: UUID,
        days: int = 30,
    ) -> dict:
        """获取体重趋势（从用户资料获取当前体重）"""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return {"success": False, "error": "用户不存在"}

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
    ) -> dict:
        """获取全部统计"""
        result = await db.execute(
            select(Checkin).where(Checkin.user_id == user_id)
        )
        checkins = list(result.scalars().all())

        total_workouts = len(checkins)
        total_duration = sum(c.duration_min for c in checkins)

        # 计算连续天数
        from app.services.checkin_service import CheckinService

        streak = await CheckinService.get_streak(db, user_id)

        return {
            "total_workouts": total_workouts,
            "total_duration_min": total_duration,
            "current_streak": streak["current_streak"],
            "longest_streak": streak["longest_streak"],
        }