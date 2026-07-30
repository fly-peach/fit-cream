"""
饮食记录工具

供 Agent 调用，记录/查询/管理每日饮食。
直接调用 DietMealService / UserService（同进程融合）。
"""

from datetime import date as date_type
from typing import Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.database import async_session_factory
from src.fitme.schemas.user import UserSettingsUpdate
from src.fitme.services.diet_meal_service import DietMealService
from src.fitme.services.user_service import UserService


class RecordMealInput(BaseModel):
    """记录一餐的输入参数"""

    meal_type: str = Field(
        pattern="^(breakfast|lunch|dinner|snack)$",
        description="餐次：breakfast/lunch/dinner/snack",
    )
    food_name: str = Field(min_length=1, max_length=200, description="食物名称")
    calories: int = Field(default=0, ge=0, description="热量（kcal）")
    protein_g: Optional[float] = Field(default=None, ge=0, description="蛋白质（g）")
    carbs_g: Optional[float] = Field(default=None, ge=0, description="碳水（g）")
    fat_g: Optional[float] = Field(default=None, ge=0, description="脂肪（g）")
    portion: Optional[str] = Field(default=None, max_length=100, description="份量，如 150g")
    note: Optional[str] = Field(default=None, max_length=500, description="备注")
    meal_date: Optional[str] = Field(
        default=None, description="日期 YYYY-MM-DD，不填默认今天"
    )


@tool(args_schema=RecordMealInput)
async def record_meal_tool(
    meal_type: str,
    food_name: str,
    calories: int = 0,
    protein_g: Optional[float] = None,
    carbs_g: Optional[float] = None,
    fat_g: Optional[float] = None,
    portion: Optional[str] = None,
    note: Optional[str] = None,
    meal_date: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    记录用户的一餐饮食。

    使用场景：
    - 用户说"我刚吃了一碗牛肉面"→ food_name="牛肉面", meal_type 根据时间推断
    - 用户说"早餐吃了两个鸡蛋和一杯牛奶"→ 分两次调用或合并记录
    - 用户说"帮我记录午餐，米饭+红烧肉，大概600大卡"→ calories=600

    Returns:
        记录结果，包含餐食详情
    """
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    parsed_date = date_type.fromisoformat(meal_date) if meal_date else date_type.today()

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)
            meal = await DietMealService.create_meal(
                db,
                uid,
                {
                    "meal_date": parsed_date,
                    "meal_type": meal_type,
                    "food_name": food_name,
                    "calories": calories,
                    "protein_g": protein_g,
                    "carbs_g": carbs_g,
                    "fat_g": fat_g,
                    "portion": portion,
                    "note": note,
                },
            )
            await db.commit()
            return {
                "success": True,
                "meal": {
                    "id": str(meal.id),
                    "meal_date": str(meal.meal_date),
                    "meal_type": meal.meal_type,
                    "food_name": meal.food_name,
                    "calories": meal.calories,
                    "protein_g": float(meal.protein_g) if meal.protein_g else None,
                    "carbs_g": float(meal.carbs_g) if meal.carbs_g else None,
                    "fat_g": float(meal.fat_g) if meal.fat_g else None,
                    "portion": meal.portion,
                },
                "message": f"已记录{food_name}（{meal.calories} kcal）",
            }
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}


class QueryDietSummaryInput(BaseModel):
    """查询当日营养汇总的输入参数"""

    date: Optional[str] = Field(
        default=None, description="查询日期 YYYY-MM-DD，不填默认今天"
    )


@tool(args_schema=QueryDietSummaryInput)
async def query_diet_summary_tool(
    date: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    查询用户某日的饮食营养汇总，包含摄入总量、营养目标和达标状态。

    使用场景：
    - 用户说"我今天吃了多少"→ 查今天
    - 用户说"昨天营养达标了吗"→ date=昨天
    - 用户说"看看我的饮食情况"→ 查今天

    Returns:
        当日摄入总量、营养目标、各宏量达标状态
    """
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    query_date = date_type.fromisoformat(date) if date else date_type.today()

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)
            summary = await DietMealService.get_summary(db, uid, query_date)
            settings = await UserService.get_user_settings(db, uid)
            await db.commit()
            return {
                "success": True,
                "date": str(query_date),
                "intake": {
                    "total_calories": summary.total_calories,
                    "total_protein_g": float(summary.total_protein_g),
                    "total_carbs_g": float(summary.total_carbs_g),
                    "total_fat_g": float(summary.total_fat_g),
                    "meal_count": summary.meal_count,
                },
                "goals": {
                    "calorie_goal": settings.calorie_goal,
                    "protein_goal_g": settings.protein_goal_g,
                    "carbs_goal_g": settings.carbs_goal_g,
                    "fat_goal_g": settings.fat_goal_g,
                },
                "goal_met": {
                    "protein": summary.protein_goal_met,
                    "carbs": summary.carbs_goal_met,
                    "fat": summary.fat_goal_met,
                },
            }
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}


class ManageMealInput(BaseModel):
    """修改/删除饮食记录的输入参数"""

    action: str = Field(
        pattern="^(update|delete)$", description="操作类型：update 或 delete"
    )
    meal_id: str = Field(description="饮食记录 ID（UUID 字符串）")
    meal_type: Optional[str] = Field(
        default=None, pattern="^(breakfast|lunch|dinner|snack)$", description="餐次"
    )
    food_name: Optional[str] = Field(default=None, max_length=200, description="食物名称")
    calories: Optional[int] = Field(default=None, ge=0, description="热量（kcal）")
    protein_g: Optional[float] = Field(default=None, ge=0, description="蛋白质（g）")
    carbs_g: Optional[float] = Field(default=None, ge=0, description="碳水（g）")
    fat_g: Optional[float] = Field(default=None, ge=0, description="脂肪（g）")
    portion: Optional[str] = Field(default=None, max_length=100, description="份量")
    note: Optional[str] = Field(default=None, max_length=500, description="备注")


@tool(args_schema=ManageMealInput)
async def manage_meal_tool(
    action: str,
    meal_id: str,
    meal_type: Optional[str] = None,
    food_name: Optional[str] = None,
    calories: Optional[int] = None,
    protein_g: Optional[float] = None,
    carbs_g: Optional[float] = None,
    fat_g: Optional[float] = None,
    portion: Optional[str] = None,
    note: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    修改或删除一条饮食记录。

    使用场景：
    - 用户说"把刚才那条记录的热量改成500"→ action="update", calories=500
    - 用户说"删掉今天早餐那条记录"→ action="delete"（需先确认 meal_id）
    - 用户说"把午餐改成米饭"→ action="update", food_name="米饭"

    注意：meal_id 必须是有效的 UUID 字符串，可通过 query_diet_summary_tool 或前端获取。

    Returns:
        操作结果
    """
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        mid = UUID(meal_id)
    except ValueError:
        return {"success": False, "error": f"无效的 meal_id：{meal_id}"}

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)
            if action == "delete":
                await DietMealService.delete_meal(db, mid, uid)
                await db.commit()
                return {"success": True, "message": "饮食记录已删除"}

            update_fields = {
                k: v
                for k, v in {
                    "meal_type": meal_type,
                    "food_name": food_name,
                    "calories": calories,
                    "protein_g": protein_g,
                    "carbs_g": carbs_g,
                    "fat_g": fat_g,
                    "portion": portion,
                    "note": note,
                }.items()
                if v is not None
            }
            if not update_fields:
                return {"success": False, "error": "未提供任何需要更新的字段"}

            meal = await DietMealService.update_meal(db, mid, uid, update_fields)
            await db.commit()
            return {
                "success": True,
                "meal": {
                    "id": str(meal.id),
                    "food_name": meal.food_name,
                    "calories": meal.calories,
                    "meal_type": meal.meal_type,
                },
                "message": f"已更新饮食记录：{meal.food_name}",
            }
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}


class SetNutritionGoalsInput(BaseModel):
    """设定营养目标的输入参数"""

    calorie_goal: Optional[int] = Field(
        default=None, ge=500, le=10000, description="每日目标热量（kcal）"
    )
    protein_goal_g: Optional[int] = Field(
        default=None, ge=0, le=500, description="每日蛋白质目标（g）"
    )
    carbs_goal_g: Optional[int] = Field(
        default=None, ge=0, le=1000, description="每日碳水目标（g）"
    )
    fat_goal_g: Optional[int] = Field(
        default=None, ge=0, le=300, description="每日脂肪目标（g）"
    )


@tool(args_schema=SetNutritionGoalsInput)
async def set_nutrition_goals_tool(
    calorie_goal: Optional[int] = None,
    protein_goal_g: Optional[int] = None,
    carbs_goal_g: Optional[int] = None,
    fat_goal_g: Optional[int] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    设定用户的每日营养目标（热量、蛋白质、碳水、脂肪）。

    使用场景：
    - 用户说"把我的蛋白质目标改成150g"→ protein_goal_g=150
    - 用户说"我每天想吃2200大卡"→ calorie_goal=2200
    - 用户说"帮我设置营养目标：热量2000，蛋白质140，碳水250，脂肪65"

    只需传入要修改的字段，未传入的字段保持不变。

    Returns:
        更新后的营养目标
    """
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    update_data = {
        k: v
        for k, v in {
            "calorie_goal": calorie_goal,
            "protein_goal_g": protein_goal_g,
            "carbs_goal_g": carbs_goal_g,
            "fat_goal_g": fat_goal_g,
        }.items()
        if v is not None
    }
    if not update_data:
        return {"success": False, "error": "未提供任何需要更新的目标字段"}

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)
            settings = await UserService.update_user_settings(
                db, uid, UserSettingsUpdate(**update_data)
            )
            await db.commit()
            return {
                "success": True,
                "goals": {
                    "calorie_goal": settings.calorie_goal,
                    "protein_goal_g": settings.protein_goal_g,
                    "carbs_goal_g": settings.carbs_goal_g,
                    "fat_goal_g": settings.fat_goal_g,
                },
                "message": "营养目标已更新",
            }
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}
