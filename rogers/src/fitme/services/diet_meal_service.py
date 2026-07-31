"""
饮食记录服务

DietMeal: 实际每餐记录的 CRUD
DailyDietSummary: 每日营养汇总
CustomFoodItem: 用户自定义食物管理
"""
from datetime import date as date_type
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.diet_meal import CustomFoodItem, DailyDietSummary, DietMeal
from src.fitme.models.user_settings import UserSettings
from utils.exceptions import ForbiddenException, NotFoundException


class DietMealService:
    @staticmethod
    async def create_meal(db: AsyncSession, user_id: UUID, data: dict) -> DietMeal:
        meal = DietMeal(user_id=user_id, **data)
        db.add(meal)
        await db.flush()
        await db.refresh(meal)
        await DietMealService._recalc_summary(db, user_id, meal.meal_date)
        return meal

    @staticmethod
    async def batch_create_meals(
        db: AsyncSession, user_id: UUID, meals_data: List[dict]
    ) -> List[DietMeal]:
        created = []
        dates_to_recalc = set()
        for data in meals_data:
            meal = DietMeal(user_id=user_id, **data)
            db.add(meal)
            await db.flush()
            await db.refresh(meal)
            created.append(meal)
            dates_to_recalc.add(meal.meal_date)
        for d in dates_to_recalc:
            await DietMealService._recalc_summary(db, user_id, d)
        return created

    @staticmethod
    async def get_by_id(db: AsyncSession, meal_id: UUID, user_id: UUID) -> DietMeal:
        result = await db.execute(select(DietMeal).where(DietMeal.id == meal_id))
        meal = result.scalar_one_or_none()
        if not meal:
            raise NotFoundException("饮食记录不存在")
        if meal.user_id != user_id:
            raise ForbiddenException("无权访问此饮食记录")
        return meal

    @staticmethod
    async def list_meals(
        db: AsyncSession,
        user_id: UUID,
        start: Optional[date_type] = None,
        end: Optional[date_type] = None,
        meal_type: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[DietMeal], int]:
        query = select(DietMeal).where(DietMeal.user_id == user_id)
        count_query = select(func.count()).select_from(DietMeal).where(
            DietMeal.user_id == user_id
        )

        if start:
            query = query.where(DietMeal.meal_date >= start)
            count_query = count_query.where(DietMeal.meal_date >= start)
        if end:
            query = query.where(DietMeal.meal_date <= end)
            count_query = count_query.where(DietMeal.meal_date <= end)
        if meal_type:
            query = query.where(DietMeal.meal_type == meal_type)
            count_query = count_query.where(DietMeal.meal_type == meal_type)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = (
            query.order_by(DietMeal.meal_date.desc(), DietMeal.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await db.execute(query)
        return list(result.scalars().all()), total

    @staticmethod
    async def update_meal(
        db: AsyncSession, meal_id: UUID, user_id: UUID, data: dict
    ) -> DietMeal:
        meal = await DietMealService.get_by_id(db, meal_id, user_id)
        for field, value in data.items():
            setattr(meal, field, value)
        await db.flush()
        await db.refresh(meal)
        await DietMealService._recalc_summary(db, user_id, meal.meal_date)
        return meal

    @staticmethod
    async def delete_meal(db: AsyncSession, meal_id: UUID, user_id: UUID) -> None:
        meal = await DietMealService.get_by_id(db, meal_id, user_id)
        meal_date = meal.meal_date
        await db.delete(meal)
        await db.flush()
        await DietMealService._recalc_summary(db, user_id, meal_date)

    @staticmethod
    async def get_summary(
        db: AsyncSession, user_id: UUID, summary_date: date_type
    ) -> DailyDietSummary:
        result = await db.execute(
            select(DailyDietSummary).where(
                DailyDietSummary.user_id == user_id,
                DailyDietSummary.summary_date == summary_date,
            )
        )
        summary = result.scalar_one_or_none()
        if not summary:
            return await DietMealService._recalc_summary(db, user_id, summary_date)
        return summary

    @staticmethod
    async def get_summary_with_goals(
        db: AsyncSession, user_id: UUID, summary_date: date_type
    ) -> dict:
        """合并当日营养汇总 + 用户营养目标 + 达标状态（供 Agent query_diet_summary 使用）。"""
        summary = await DietMealService.get_summary(db, user_id, summary_date)

        settings_result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = settings_result.scalar_one_or_none()

        return {
            "intake": {
                "total_calories": summary.total_calories,
                "total_protein_g": float(summary.total_protein_g),
                "total_carbs_g": float(summary.total_carbs_g),
                "total_fat_g": float(summary.total_fat_g),
                "meal_count": summary.meal_count,
            },
            "goals": {
                "calorie_goal": settings.calorie_goal if settings else None,
                "protein_goal_g": settings.protein_goal_g if settings else None,
                "carbs_goal_g": settings.carbs_goal_g if settings else None,
                "fat_goal_g": settings.fat_goal_g if settings else None,
            },
            "goal_met": {
                "protein": summary.protein_goal_met,
                "carbs": summary.carbs_goal_met,
                "fat": summary.fat_goal_met,
            },
        }

    @staticmethod
    async def list_summaries(
        db: AsyncSession,
        user_id: UUID,
        start: Optional[date_type] = None,
        end: Optional[date_type] = None,
    ) -> List[DailyDietSummary]:
        query = select(DailyDietSummary).where(
            DailyDietSummary.user_id == user_id
        ).order_by(DailyDietSummary.summary_date.desc())
        if start:
            query = query.where(DailyDietSummary.summary_date >= start)
        if end:
            query = query.where(DailyDietSummary.summary_date <= end)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def _recalc_summary(
        db: AsyncSession, user_id: UUID, summary_date: date_type
    ) -> DailyDietSummary:
        meals_result = await db.execute(
            select(DietMeal).where(
                DietMeal.user_id == user_id,
                DietMeal.meal_date == summary_date,
            )
        )
        meals = meals_result.scalars().all()

        total_calories = sum(m.calories or 0 for m in meals)
        total_protein = sum(m.protein_g or 0 for m in meals)
        total_carbs = sum(m.carbs_g or 0 for m in meals)
        total_fat = sum(m.fat_g or 0 for m in meals)

        settings_result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = settings_result.scalar_one_or_none()

        protein_met = total_protein >= settings.protein_goal_g if settings else False
        carbs_met = total_carbs >= settings.carbs_goal_g if settings else False
        fat_met = total_fat >= settings.fat_goal_g if settings else False

        result = await db.execute(
            select(DailyDietSummary).where(
                DailyDietSummary.user_id == user_id,
                DailyDietSummary.summary_date == summary_date,
            )
        )
        summary = result.scalar_one_or_none()

        if summary:
            summary.total_calories = total_calories
            summary.total_protein_g = total_protein
            summary.total_carbs_g = total_carbs
            summary.total_fat_g = total_fat
            summary.protein_goal_met = protein_met
            summary.carbs_goal_met = carbs_met
            summary.fat_goal_met = fat_met
            summary.meal_count = len(meals)
        else:
            summary = DailyDietSummary(
                user_id=user_id,
                summary_date=summary_date,
                total_calories=total_calories,
                total_protein_g=total_protein,
                total_carbs_g=total_carbs,
                total_fat_g=total_fat,
                protein_goal_met=protein_met,
                carbs_goal_met=carbs_met,
                fat_goal_met=fat_met,
                meal_count=len(meals),
            )
            db.add(summary)

        await db.flush()
        await db.refresh(summary)
        return summary


class CustomFoodItemService:
    @staticmethod
    async def create(db: AsyncSession, user_id: UUID, data: dict) -> CustomFoodItem:
        item = CustomFoodItem(user_id=user_id, **data)
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item

    @staticmethod
    async def get_by_id(db: AsyncSession, food_id: UUID, user_id: UUID) -> CustomFoodItem:
        result = await db.execute(select(CustomFoodItem).where(CustomFoodItem.id == food_id))
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundException("食物不存在")
        if item.user_id != user_id:
            raise ForbiddenException("无权访问此食物")
        return item

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: UUID,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> List[CustomFoodItem]:
        query = select(CustomFoodItem).where(CustomFoodItem.user_id == user_id)
        if category:
            query = query.where(CustomFoodItem.category == category)
        if keyword:
            query = query.where(CustomFoodItem.name.ilike(f"%{keyword}%"))
        query = query.order_by(CustomFoodItem.name)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession, food_id: UUID, user_id: UUID, data: dict
    ) -> CustomFoodItem:
        item = await CustomFoodItemService.get_by_id(db, food_id, user_id)
        for field, value in data.items():
            setattr(item, field, value)
        await db.flush()
        await db.refresh(item)
        return item

    @staticmethod
    async def delete(db: AsyncSession, food_id: UUID, user_id: UUID) -> None:
        item = await CustomFoodItemService.get_by_id(db, food_id, user_id)
        await db.delete(item)
        await db.flush()
