"""
饮食计划服务

提供饮食计划的完整 CRUD 和智能生成逻辑：
- 手动创建/更新/删除饮食计划
- 根据用户目标自动生成饮食计划（Agent create_diet_plan_tool 调用）
"""
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.fitme.models.diet_plan import DietPlan, DietPlanDay, DietPlanMeal
from src.fitme.schemas.diet_plan import (
    DietDayCreate,
    DietDayUpdate,
    DietMealCreate,
    DietMealUpdate,
    DietPlanCreate,
    DietPlanUpdate,
)
from src.fitme.services import activity_level_service
from utils.exceptions import ForbiddenException, NotFoundException


class DietPlanService:
    @staticmethod
    async def _verify_diet_day_ownership(
        db: AsyncSession,
        diet_day_id: UUID,
        user_id: UUID,
    ) -> Tuple[DietPlanDay, DietPlan]:
        """验证饮食日归属，返回 (diet_day, diet_plan)"""
        result = await db.execute(
            select(DietPlanDay, DietPlan)
            .join(DietPlan, DietPlanDay.diet_plan_id == DietPlan.id)
            .where(DietPlanDay.id == diet_day_id)
        )
        row = result.one_or_none()
        if not row:
            raise NotFoundException("饮食日不存在")
        diet_day, diet_plan = row
        if diet_plan.user_id != user_id:
            raise ForbiddenException("无权操作此饮食日")
        return diet_day, diet_plan

    @staticmethod
    async def _verify_meal_ownership(
        db: AsyncSession,
        meal_id: UUID,
        user_id: UUID,
    ) -> Tuple[DietPlanMeal, DietPlanDay, DietPlan]:
        """验证餐食归属，返回 (meal, diet_day, diet_plan)"""
        result = await db.execute(
            select(DietPlanMeal, DietPlanDay, DietPlan)
            .join(DietPlanDay, DietPlanMeal.diet_plan_day_id == DietPlanDay.id)
            .join(DietPlan, DietPlanDay.diet_plan_id == DietPlan.id)
            .where(DietPlanMeal.id == meal_id)
        )
        row = result.one_or_none()
        if not row:
            raise NotFoundException("餐食不存在")
        meal, diet_day, diet_plan = row
        if diet_plan.user_id != user_id:
            raise ForbiddenException("无权操作此餐食")
        return meal, diet_day, diet_plan

    @staticmethod
    async def create_diet_plan(
        db: AsyncSession,
        user_id: UUID,
        data: DietPlanCreate,
    ) -> DietPlan:
        """创建饮食计划"""
        diet_plan = DietPlan(
            user_id=user_id,
            name=data.name,
            target_calories=data.target_calories,
            goal=data.goal,
            status="active",
        )
        db.add(diet_plan)
        await db.flush()

        if data.days:
            for day_data in data.days:
                await DietPlanService._create_diet_day(db, diet_plan.id, day_data)

        await db.refresh(diet_plan)
        return diet_plan

    @staticmethod
    async def _create_diet_day(
        db: AsyncSession,
        diet_plan_id: UUID,
        data: DietDayCreate,
    ) -> DietPlanDay:
        """创建饮食日"""
        day_id = uuid4()
        diet_day = DietPlanDay(
            id=day_id,
            diet_plan_id=diet_plan_id,
            day_of_week=data.day_of_week,
            focus=data.focus,
            metadata_=data.metadata_ or {},
        )
        db.add(diet_day)

        for i, meal_data in enumerate(data.meals):
            meal = DietPlanMeal(
                id=uuid4(),
                diet_plan_day_id=day_id,
                meal_type=meal_data.meal_type,
                food_name=meal_data.food_name,
                calories=meal_data.calories,
                protein_g=meal_data.protein_g,
                carbs_g=meal_data.carbs_g,
                fat_g=meal_data.fat_g,
                portion=meal_data.portion,
                sort_order=meal_data.sort_order or i,
                metadata_=meal_data.metadata_ or {},
            )
            db.add(meal)

        await db.flush()
        return diet_day

    @staticmethod
    async def list_diet_plans(
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        size: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[DietPlan], int]:
        """获取饮食计划列表"""
        query = select(DietPlan).where(DietPlan.user_id == user_id)
        count_query = select(func.count()).select_from(DietPlan).where(DietPlan.user_id == user_id)

        if status:
            query = query.where(DietPlan.status == status)
            count_query = count_query.where(DietPlan.status == status)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = (
            query.order_by(DietPlan.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await db.execute(query)
        diet_plans = list(result.scalars().all())

        return diet_plans, total

    @staticmethod
    async def get_diet_plan_detail(
        db: AsyncSession,
        diet_plan_id: UUID,
        user_id: UUID,
    ) -> DietPlan:
        """获取饮食计划详情（含饮食日和餐食）"""
        result = await db.execute(
            select(DietPlan)
            .options(selectinload(DietPlan.days).selectinload(DietPlanDay.meals))
            .where(DietPlan.id == diet_plan_id)
            # 会话 expire_on_commit=False：增删饮食日/餐食后，identity map 中的 DietPlan
            # 仍持有旧的 days 集合；populate_existing 强制用本次查询结果覆盖，保证返回最新
            .execution_options(populate_existing=True)
        )
        diet_plan = result.scalar_one_or_none()

        if not diet_plan:
            raise NotFoundException("饮食计划不存在")
        if diet_plan.user_id != user_id:
            raise ForbiddenException("无权访问此饮食计划")

        return diet_plan

    @staticmethod
    async def get_active_diet_plan(
        db: AsyncSession,
        user_id: UUID,
    ) -> Optional[DietPlan]:
        """获取用户当前活跃饮食计划"""
        result = await db.execute(
            select(DietPlan)
            .where(DietPlan.user_id == user_id, DietPlan.status == "active")
            .order_by(DietPlan.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_diet_plan(
        db: AsyncSession,
        diet_plan_id: UUID,
        user_id: UUID,
        data: DietPlanUpdate,
    ) -> DietPlan:
        """更新饮食计划"""
        diet_plan = await DietPlanService.get_diet_plan_detail(db, diet_plan_id, user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(diet_plan, field, value)

        await db.flush()
        await db.refresh(diet_plan)
        return diet_plan

    @staticmethod
    async def delete_diet_plan(
        db: AsyncSession,
        diet_plan_id: UUID,
        user_id: UUID,
    ) -> None:
        """软删除饮食计划（设为 archived）"""
        diet_plan = await DietPlanService.get_diet_plan_detail(db, diet_plan_id, user_id)
        diet_plan.status = "archived"
        await db.flush()

    @staticmethod
    async def add_diet_day(
        db: AsyncSession,
        diet_plan_id: UUID,
        user_id: UUID,
        data: DietDayCreate,
    ) -> DietPlanDay:
        """为饮食计划添加饮食日"""
        await DietPlanService.get_diet_plan_detail(db, diet_plan_id, user_id)
        diet_day = await DietPlanService._create_diet_day(db, diet_plan_id, data)
        await db.flush()
        return diet_day

    @staticmethod
    async def update_diet_day(
        db: AsyncSession,
        diet_day_id: UUID,
        user_id: UUID,
        data: DietDayUpdate,
    ) -> DietPlanDay:
        """更新饮食日"""
        diet_day, _ = await DietPlanService._verify_diet_day_ownership(
            db, diet_day_id, user_id
        )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(diet_day, field, value)

        await db.flush()
        await db.refresh(diet_day)
        return diet_day

    @staticmethod
    async def add_meal(
        db: AsyncSession,
        diet_day_id: UUID,
        user_id: UUID,
        data: DietMealCreate,
    ) -> Tuple[DietPlanMeal, DietPlan]:
        """为饮食日添加餐食，返回 (meal, diet_plan)"""
        _, diet_plan = await DietPlanService._verify_diet_day_ownership(db, diet_day_id, user_id)

        meal = DietPlanMeal(
            id=uuid4(),
            diet_plan_day_id=diet_day_id,
            meal_type=data.meal_type,
            food_name=data.food_name,
            calories=data.calories,
            protein_g=data.protein_g,
            carbs_g=data.carbs_g,
            fat_g=data.fat_g,
            portion=data.portion,
            sort_order=data.sort_order,
            metadata_=data.metadata_ or {},
        )
        db.add(meal)
        await db.flush()
        await db.refresh(meal)
        return meal, diet_plan

    @staticmethod
    async def update_meal(
        db: AsyncSession,
        meal_id: UUID,
        user_id: UUID,
        data: DietMealUpdate,
    ) -> Tuple[DietPlanMeal, DietPlan]:
        """更新餐食，返回 (meal, diet_plan)"""
        meal, _, diet_plan = await DietPlanService._verify_meal_ownership(
            db, meal_id, user_id
        )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(meal, field, value)

        await db.flush()
        await db.refresh(meal)
        return meal, diet_plan

    @staticmethod
    async def delete_meal(
        db: AsyncSession,
        meal_id: UUID,
        user_id: UUID,
    ) -> Tuple[DietPlanMeal, DietPlan]:
        """删除餐食，返回 (meal, diet_plan)"""
        meal, _, diet_plan = await DietPlanService._verify_meal_ownership(
            db, meal_id, user_id
        )

        await db.delete(meal)
        await db.flush()
        return meal, diet_plan

    @staticmethod
    async def generate_diet_plan_from_goal(
        db: AsyncSession,
        user_id: UUID,
        goal: str,
        target_calories: Optional[int] = None,
        days_per_week: int = 7,
        preferences: Optional[str] = None,
        user_data: Optional[dict] = None,
        activity_level: Optional[str] = None,
    ) -> DietPlan:
        """根据目标智能生成饮食计划（Agent 调用）。

        target_calories 为空时优先用 Mifflin-St Jeor + TDEE（含活动水平档位）换算，
        身体数据不全则回退旧的体重×系数估算，再兜底 2000。
        """
        ud = user_data or {}
        daily_macros: Optional[dict] = None
        if target_calories is None:
            targets = activity_level_service.compute_daily_targets(
                weight_kg=ud.get("weight_kg"),
                height_cm=ud.get("height_cm"),
                age=ud.get("age"),
                gender=ud.get("gender"),
                activity_level=activity_level,
                goal=goal,
            )
            if targets["target_calories"] is not None:
                target_calories = targets["target_calories"]
                daily_macros = {
                    "protein_g": targets["protein_g"],
                    "carbs_g": targets["carbs_g"],
                    "fat_g": targets["fat_g"],
                }
            else:
                weight = ud.get("weight_kg")
                if weight:
                    factor = {"lose_fat": 22, "gain_muscle": 33}.get(goal, 28)
                    target_calories = int(weight * factor)
                else:
                    target_calories = 2000

        if daily_macros is None:
            daily_macros = activity_level_service.calculate_macros(target_calories, goal)

        goal_names = {
            "lose_fat": "减脂饮食",
            "gain_muscle": "增肌饮食",
            "maintain": "均衡饮食",
            "improve_health": "健康饮食",
        }
        goal_name = goal_names.get(goal, "综合饮食")

        diet_plan = DietPlan(
            user_id=user_id,
            name=f"{goal_name}计划",
            target_calories=target_calories,
            goal=goal,
            status="active",
        )
        db.add(diet_plan)
        await db.flush()

        meal_calories = {
            "breakfast": int(target_calories * 0.3),
            "lunch": int(target_calories * 0.35),
            "dinner": int(target_calories * 0.25),
            "snack": int(target_calories * 0.1),
        }

        day_focuses = {
            1: "高蛋白低碳水",
            2: "均衡营养",
            3: "轻食日",
            4: "高蛋白",
            5: "均衡营养",
            6: "自由餐",
            7: "轻食恢复",
        }

        meal_templates = {
            "breakfast": [
                {"food_name": "燕麦粥 + 鸡蛋", "portion": "1碗 + 2个"},
                {"food_name": "全麦面包 + 牛奶", "portion": "2片 + 1杯"},
            ],
            "lunch": [
                {"food_name": "鸡胸肉 + 糙米饭 + 蔬菜", "portion": "150g + 1碗 + 适量"},
                {"food_name": "牛肉 + 意面 + 沙拉", "portion": "120g + 1份 + 适量"},
            ],
            "dinner": [
                {"food_name": "清蒸鱼 + 蔬菜 + 少量主食", "portion": "200g + 适量 + 半碗"},
                {"food_name": "豆腐 + 蔬菜汤", "portion": "150g + 1碗"},
            ],
            "snack": [
                {"food_name": "坚果 + 水果", "portion": "一小把 + 1个"},
                {"food_name": "酸奶", "portion": "1杯"},
            ],
        }

        num_days = min(days_per_week, 7)
        for day_num in range(1, num_days + 1):
            day_id = uuid4()
            diet_day = DietPlanDay(
                id=day_id,
                diet_plan_id=diet_plan.id,
                day_of_week=day_num,
                focus=day_focuses.get(day_num, "均衡饮食"),
            )
            db.add(diet_day)

            for meal_type, calories in meal_calories.items():
                templates = meal_templates.get(meal_type, [])
                template = (
                    templates[(day_num - 1) % len(templates)]
                    if templates
                    else {"food_name": "健康餐食", "portion": "适量"}
                )

                protein_g = round(daily_macros["protein_g"] * (calories / target_calories), 1)
                carbs_g = round(daily_macros["carbs_g"] * (calories / target_calories), 1)
                fat_g = round(daily_macros["fat_g"] * (calories / target_calories), 1)

                meal = DietPlanMeal(
                    id=uuid4(),
                    diet_plan_day_id=day_id,
                    meal_type=meal_type,
                    food_name=template["food_name"],
                    calories=calories,
                    protein_g=protein_g,
                    carbs_g=carbs_g,
                    fat_g=fat_g,
                    portion=template.get("portion"),
                    sort_order=list(meal_calories.keys()).index(meal_type),
                )
                db.add(meal)

        await db.flush()
        # 预加载 days -> meals，避免工具层访问关系触发异步懒加载
        # （async SQLAlchemy 下同步访问关系会抛 greenlet_spawn has not been called）
        result = await db.execute(
            select(DietPlan)
            .options(selectinload(DietPlan.days).selectinload(DietPlanDay.meals))
            .where(DietPlan.id == diet_plan.id)
        )
        return result.scalar_one()
