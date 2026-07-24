"""
训练计划工具

供 Agent 调用，创建和调整训练计划。
直接调用 PlanService（同进程融合）。
"""

from typing import Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.database import async_session_factory
from app.services.diet_plan_service import DietPlanService
from app.services.plan_service import PlanService
from app.services.user_service import UserService


@tool
async def list_plans_tool(config: RunnableConfig) -> dict:
    """
    查看当前用户的所有训练计划列表。

    使用场景：
    - 用户问"看看我的计划"、"我的计划是什么"、"有哪些计划"

    Returns:
        计划列表，包含每个计划的名称、目标、状态和创建时间
    """
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_id")

    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)
            plans, total = await PlanService.list_plans(db, uid, page=1, size=20)

            if total == 0:
                return {"success": True, "total": 0, "plans": [], "message": "你还没有创建过训练计划，需要我帮你创建一个吗？"}

            plan_list = []
            for plan in plans:
                plan_list.append({
                    "id": str(plan.id),
                    "name": plan.name,
                    "goal": plan.goal,
                    "difficulty": plan.difficulty,
                    "weeks": plan.weeks,
                    "status": plan.status,
                    "created_at": plan.created_at.isoformat() if plan.created_at else None,
                })

            goal_names = {
                "lose_fat": "减脂",
                "gain_muscle": "增肌",
                "maintain": "保持健康",
                "improve_health": "体能提升",
            }

            active_plan = next((p for p in plan_list if p["status"] == "active"), None)
            msg = f"共有 {total} 个计划"
            if active_plan:
                goal_name = goal_names.get(active_plan["goal"], "综合训练")
                msg += f"，当前活跃计划：{active_plan['name']}（{goal_name}）"

            return {
                "success": True,
                "total": total,
                "plans": plan_list,
                "message": msg,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class CreatePlanInput(BaseModel):
    """创建训练计划的输入参数"""

    goal: str = Field(
        description=(
            "健身目标。可选值：lose_fat(减脂)、gain_muscle(增肌)、"
            "maintain(维持)、improve_health(提升健康)"
        )
    )
    days_per_week: int = Field(
        ge=1, le=7, description="每周训练天数，1-7天"
    )
    difficulty: Optional[str] = Field(
        default="beginner",
        description="难度级别：beginner(初级)、intermediate(中级)、advanced(高级)",
    )
    preferences: Optional[str] = Field(
        default=None,
        description="用户偏好说明，如'不喜欢跑步'、'没有器械'、'膝盖有伤'",
    )


@tool(args_schema=CreatePlanInput)
async def create_plan_tool(
    goal: str,
    days_per_week: int,
    difficulty: str = "beginner",
    preferences: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    根据用户的健身目标创建个性化训练计划。

    使用场景：
    - 用户说"我想减脂，每周练4天"→ goal="lose_fat", days_per_week=4
    - 用户说"帮我制定一个增肌计划"→ goal="gain_muscle"
    - 用户说"我是新手，想开始健身"→ goal="improve_health", difficulty="beginner"

    会考虑用户的身体数据（身高、体重、年龄）生成合适的计划。

    Returns:
        包含计划详情、训练日安排的结构化数据
    """
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)

            # 获取用户信息
            user = await UserService.get_by_id(db, uid)
            user_data = None
            if user:
                user_data = {
                    "height_cm": float(user.height_cm) if user.height_cm else None,
                    "weight_kg": float(user.weight_kg) if user.weight_kg else None,
                    "age": user.age,
                    "gender": user.gender,
                }

            # 生成计划
            plan = await PlanService.generate_plan_from_goal(
                db=db,
                user_id=uid,
                goal=goal,
                days_per_week=days_per_week,
                difficulty=difficulty,
                preferences=preferences,
                user_data=user_data,
            )

            await db.commit()

            # 构建返回数据
            plan_data = {
                "id": str(plan.id),
                "name": plan.name,
                "goal": plan.goal,
                "difficulty": plan.difficulty,
                "weeks": plan.weeks,
                "status": plan.status,
                "days": [
                    {
                        "day_of_week": day.day_of_week,
                        "focus": day.focus,
                        "rest_seconds": day.rest_seconds,
                        "exercises": [
                            {
                                "name": ex.exercise.name if ex.exercise else "未知动作",
                                "sets": ex.sets,
                                "reps": ex.reps,
                                "weight_kg": float(ex.weight_kg) if ex.weight_kg else None,
                            }
                            for ex in day.exercises
                        ],
                    }
                    for day in plan.days
                ],
            }

            goal_names = {
                "lose_fat": "减脂",
                "gain_muscle": "增肌",
                "maintain": "保持健康",
                "improve_health": "体能提升",
            }
            goal_name = goal_names.get(goal, "综合训练")

            return {
                "success": True,
                "plan": plan_data,
                "message": f"已为你创建{goal_name}计划，每周训练{days_per_week}天，难度{difficulty}。",
            }
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}


class CreateDietPlanInput(BaseModel):
    """创建饮食计划的输入参数"""

    goal: str = Field(
        description=(
            "饮食目标。可选值：lose_fat(减脂)、gain_muscle(增肌)、"
            "maintain(维持)、improve_health(提升健康)"
        )
    )
    target_calories: Optional[int] = Field(
        default=None,
        ge=1000,
        le=5000,
        description="每日目标热量（kcal），不填则根据用户数据自动计算",
    )
    preferences: Optional[str] = Field(
        default=None,
        description="饮食偏好或禁忌，如'不吃辣'、'素食'、'乳糖不耐'",
    )


@tool(args_schema=CreateDietPlanInput)
async def create_diet_plan_tool(
    goal: str,
    target_calories: Optional[int] = None,
    preferences: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    根据用户的健身目标创建个性化饮食计划。

    使用场景：
    - 用户说"帮我制定一个减脂饮食计划"→ goal="lose_fat"
    - 用户说"我想增肌，每天吃2500大卡"→ goal="gain_muscle", target_calories=2500
    - 用户说"帮我安排健康饮食"→ goal="improve_health"

    会根据用户身体数据自动计算合适的热量和宏量素比例。

    Returns:
        包含饮食计划详情、每日餐食安排的结构化数据
    """
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)

            # 获取用户信息以计算热量
            user = await UserService.get_by_id(db, uid)
            user_data = None
            calculated_calories = target_calories or 2000

            if user:
                user_data = {
                    "height_cm": float(user.height_cm) if user.height_cm else None,
                    "weight_kg": float(user.weight_kg) if user.weight_kg else None,
                    "age": user.age,
                    "gender": user.gender,
                }
                # 如果没有指定热量，根据用户数据估算
                if not target_calories and user_data["weight_kg"]:
                    weight = user_data["weight_kg"]
                    if goal == "lose_fat":
                        calculated_calories = int(weight * 22)  # 减脂：体重×22
                    elif goal == "gain_muscle":
                        calculated_calories = int(weight * 33)  # 增肌：体重×33
                    else:
                        calculated_calories = int(weight * 28)  # 维持：体重×28

            # 生成饮食计划
            diet_plan = await DietPlanService.generate_diet_plan_from_goal(
                db=db,
                user_id=uid,
                goal=goal,
                target_calories=calculated_calories,
                preferences=preferences,
                user_data=user_data,
            )

            await db.commit()

            # 构建返回数据
            plan_data = {
                "id": str(diet_plan.id),
                "name": diet_plan.name,
                "target_calories": diet_plan.target_calories,
                "goal": diet_plan.goal,
                "status": diet_plan.status,
                "days": [
                    {
                        "day_of_week": day.day_of_week,
                        "focus": day.focus,
                        "meals": [
                            {
                                "meal_type": meal.meal_type,
                                "food_name": meal.food_name,
                                "calories": meal.calories,
                                "protein_g": float(meal.protein_g) if meal.protein_g else None,
                                "carbs_g": float(meal.carbs_g) if meal.carbs_g else None,
                                "fat_g": float(meal.fat_g) if meal.fat_g else None,
                                "portion": meal.portion,
                            }
                            for meal in day.meals
                        ],
                    }
                    for day in diet_plan.days
                ],
            }

            goal_names = {
                "lose_fat": "减脂",
                "gain_muscle": "增肌",
                "maintain": "维持健康",
                "improve_health": "改善体质",
            }
            goal_name = goal_names.get(goal, "综合")

            return {
                "success": True,
                "diet_plan": plan_data,
                "message": f"已为你创建{goal_name}饮食计划，每日目标热量 {calculated_calories} kcal，包含7天完整餐食安排。",
            }
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}


class AdjustPlanInput(BaseModel):
    """调整计划的输入参数"""

    action: str = Field(
        description=(
            "调整类型：add_day(增加训练日)、remove_day(减少训练日)、"
            "modify_exercise(修改动作)、change_difficulty(调整难度)"
        )
    )
    details: str = Field(
        description="调整详情描述，如'把难度改为中级'、'减少一天训练'"
    )
    plan_id: Optional[str] = Field(
        default=None, description="要调整的计划ID，不填则调整当前活跃计划"
    )


@tool(args_schema=AdjustPlanInput)
async def adjust_plan_tool(
    action: str,
    details: str,
    plan_id: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    调整现有训练计划。

    使用场景：
    - 用户说"太累了，减一天"→ action="remove_day", details="减少一天训练"
    - 用户说"把难度调高一点"→ action="change_difficulty", details="调整为中级"
    - 用户说"周三改成休息日"→ action="remove_day", details="移除周三训练"

    Returns:
        调整后的计划变更说明
    """
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)

            # 获取计划
            if plan_id:
                plan = await PlanService.get_plan_detail(db, UUID(plan_id), uid)
            else:
                plan = await PlanService.get_active_plan(db, uid)

            if not plan:
                return {"success": False, "error": "没有找到需要调整的计划，请先创建一个计划。"}

            # 执行调整
            changes = await PlanService.adjust_plan(db, plan, action, details)
            await db.commit()

            return {
                "success": True,
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "action": action,
                "changes": changes,
                "message": f"计划已调整：{changes['summary']}",
            }
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}