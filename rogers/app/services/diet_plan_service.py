"""
饮食计划服务

提供饮食计划的完整 CRUD 和智能生成逻辑：
- 手动创建/更新/删除饮食计划
- 根据用户目标自动生成饮食计划（Agent create_diet_plan_tool 调用）
"""
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diet_plan import DietPlan, DietPlanDay, DietPlanMeal
from app.schemas.diet_plan import DietDayCreate, DietMealUpdate, DietPlanCreate, DietPlanUpdate
from app.utils.exceptions import ForbiddenException, NotFoundException


class DietPlanService:
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

        # 如果包含饮食日，一并创建
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
        diet_day = DietPlanDay(
            diet_plan_id=diet_plan_id,
            day_of_week=data.day_of_week,
            focus=data.focus,
        )
        db.add(diet_day)
        await db.flush()

        # 创建餐食
        for i, meal_data in enumerate(data.meals):
            meal = DietPlanMeal(
                diet_plan_day_id=diet_day.id,
                meal_type=meal_data.meal_type,
                food_name=meal_data.food_name,
                calories=meal_data.calories,
                protein_g=meal_data.protein_g,
                carbs_g=meal_data.carbs_g,
                fat_g=meal_data.fat_g,
                portion=meal_data.portion,
                sort_order=meal_data.sort_order or i,
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

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
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
            select(DietPlan).where(DietPlan.id == diet_plan_id)
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
        # 验证饮食计划归属
        await DietPlanService.get_diet_plan_detail(db, diet_plan_id, user_id)
        diet_day = await DietPlanService._create_diet_day(db, diet_plan_id, data)
        await db.flush()
        return diet_day

    @staticmethod
    async def update_meal(
        db: AsyncSession,
        meal_id: UUID,
        user_id: UUID,
        data: DietMealUpdate,
    ) -> DietPlanMeal:
        """更新餐食"""
        result = await db.execute(
            select(DietPlanMeal).where(DietPlanMeal.id == meal_id)
        )
        meal = result.scalar_one_or_none()

        if not meal:
            raise NotFoundException("餐食不存在")

        # 验证归属
        day_result = await db.execute(
            select(DietPlanDay).where(DietPlanDay.id == meal.diet_plan_day_id)
        )
        day = day_result.scalar_one()
        plan_result = await db.execute(
            select(DietPlan).where(DietPlan.id == day.diet_plan_id)
        )
        plan = plan_result.scalar_one()
        if plan.user_id != user_id:
            raise ForbiddenException("无权修改此餐食")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(meal, field, value)

        await db.flush()
        await db.refresh(meal)
        return meal

    @staticmethod
    async def delete_meal(
        db: AsyncSession,
        meal_id: UUID,
        user_id: UUID,
    ) -> None:
        """删除餐食"""
        result = await db.execute(
            select(DietPlanMeal).where(DietPlanMeal.id == meal_id)
        )
        meal = result.scalar_one_or_none()

        if not meal:
            raise NotFoundException("餐食不存在")

        # 验证归属
        day_result = await db.execute(
            select(DietPlanDay).where(DietPlanDay.id == meal.diet_plan_day_id)
        )
        day = day_result.scalar_one()
        plan_result = await db.execute(
            select(DietPlan).where(DietPlan.id == day.diet_plan_id)
        )
        plan = plan_result.scalar_one()
        if plan.user_id != user_id:
            raise ForbiddenException("无权删除此餐食")

        await db.delete(meal)
        await db.flush()

    @staticmethod
    async def generate_diet_plan_from_goal(
        db: AsyncSession,
        user_id: UUID,
        goal: str,
        target_calories: int = 2000,
        preferences: Optional[str] = None,
        user_data: Optional[dict] = None,
    ) -> DietPlan:
        """根据目标智能生成饮食计划（Agent 调用）"""
        # 目标名称映射
        goal_names = {
            "lose_fat": "减脂饮食",
            "gain_muscle": "增肌饮食",
            "maintain": "均衡饮食",
            "improve_health": "健康饮食",
        }
        goal_name = goal_names.get(goal, "综合饮食")

        # 创建饮食计划
        diet_plan = DietPlan(
            user_id=user_id,
            name=f"{goal_name}计划",
            target_calories=target_calories,
            goal=goal,
            status="active",
        )
        db.add(diet_plan)
        await db.flush()

        # 根据目标设置宏量素比例
        macro_ratios = {
            "lose_fat": {"protein": 0.4, "carbs": 0.3, "fat": 0.3},
            "gain_muscle": {"protein": 0.35, "carbs": 0.45, "fat": 0.2},
            "maintain": {"protein": 0.3, "carbs": 0.4, "fat": 0.3},
            "improve_health": {"protein": 0.3, "carbs": 0.4, "fat": 0.3},
        }
        ratios = macro_ratios.get(goal, macro_ratios["maintain"])

        # 计算每餐大概热量分配（早餐30%，午餐35%，晚餐25%，加餐10%）
        meal_calories = {
            "breakfast": int(target_calories * 0.3),
            "lunch": int(target_calories * 0.35),
            "dinner": int(target_calories * 0.25),
            "snack": int(target_calories * 0.1),
        }

        # 默认7天饮食计划
        day_focuses = {
            1: "高蛋白低碳水",
            2: "均衡营养",
            3: "轻食日",
            4: "高蛋白",
            5: "均衡营养",
            6: "自由餐",
            7: "轻食恢复",
        }

        # 默认餐食模板
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

        for day_num in range(1, 8):
            diet_day = DietPlanDay(
                diet_plan_id=diet_plan.id,
                day_of_week=day_num,
                focus=day_focuses.get(day_num, "均衡饮食"),
            )
            db.add(diet_day)
            await db.flush()

            # 为每天添加餐食
            for meal_type, calories in meal_calories.items():
                templates = meal_templates.get(meal_type, [])
                template = templates[(day_num - 1) % len(templates)] if templates else {"food_name": "健康餐食", "portion": "适量"}

                protein_g = round(calories * ratios["protein"] / 4, 1)
                carbs_g = round(calories * ratios["carbs"] / 4, 1)
                fat_g = round(calories * ratios["fat"] / 9, 1)

                meal = DietPlanMeal(
                    diet_plan_day_id=diet_day.id,
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
        await db.refresh(diet_plan)
        return diet_plan