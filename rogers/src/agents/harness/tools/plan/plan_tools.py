"""
训练计划工具

供 Agent 调用，查看、创建、编辑、删除训练计划。
直接调用 PlanService（同进程融合）。
"""
from typing import List, Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.tools._common import error_response, extract_user_id, session_scope
from src.fitme.schemas.plan import (
    PlanDayCreate,
    PlanExerciseCreate,
    PlanExerciseUpdate,
    PlanOut,
    PlanUpdate,
)
from src.fitme.services.diet_plan_service import DietPlanService
from src.fitme.services.plan_service import PlanService
from src.fitme.services.user_service import UserService
from utils.exceptions import NotFoundException


_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


async def _resolve_plan_id(db, user_id: UUID, plan_id: Optional[str]) -> UUID:
    """plan_id 非空则解析 UUID，否则取当前活跃计划 id。无活跃计划抛 NotFoundException。"""
    if plan_id:
        return UUID(plan_id)
    plan = await PlanService.get_active_plan(db, user_id)
    if not plan:
        raise NotFoundException("没有活跃训练计划，请先创建一个，或显式指定 plan_id。")
    return plan.id


@tool
async def list_plans_tool(config: RunnableConfig) -> dict:
    """
    查看当前用户的所有训练计划列表。

    使用场景：
    - 用户问"看看我的计划"、"我的计划是什么"、"有哪些计划"

    Returns:
        计划列表，包含每个计划的名称、目标、状态和创建时间
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            plans, total = await PlanService.list_plans(db, user_id, page=1, size=20)

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
        return error_response(e)


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
    - 用户说"我想减脂，每周练4天"-> goal="lose_fat", days_per_week=4
    - 用户说"帮我制定一个增肌计划"-> goal="gain_muscle"
    - 用户说"我是新手，想开始健身"-> goal="improve_health", difficulty="beginner"

    会考虑用户的身体数据（身高、体重、年龄）生成合适的计划。

    Returns:
        包含计划详情、训练日安排的结构化数据
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            user_data = await UserService.get_body_summary(db, user_id)

            plan = await PlanService.generate_plan_from_goal(
                db=db,
                user_id=user_id,
                goal=goal,
                days_per_week=days_per_week,
                difficulty=difficulty,
                preferences=preferences,
                user_data=user_data,
            )

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
        return error_response(e)


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
    - 用户说"帮我制定一个减脂饮食计划"-> goal="lose_fat"
    - 用户说"我想增肌，每天吃2500大卡"-> goal="gain_muscle", target_calories=2500
    - 用户说"帮我安排健康饮食"-> goal="improve_health"

    会根据用户身体数据自动计算合适的热量和宏量素比例。

    Returns:
        包含饮食计划详情、每日餐食安排的结构化数据
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            user_data = await UserService.get_body_summary(db, user_id)

            diet_plan = await DietPlanService.generate_diet_plan_from_goal(
                db=db,
                user_id=user_id,
                goal=goal,
                target_calories=target_calories,
                preferences=preferences,
                user_data=user_data,
            )

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
                "message": f"已为你创建{goal_name}饮食计划，每日目标热量 {diet_plan.target_calories} kcal，包含7天完整餐食安排。",
            }
    except Exception as e:
        return error_response(e)


# ===== 计划详情（只读，编辑/删除动作前用它拿 ID） =====


class GetPlanDetailInput(BaseModel):
    """查看训练计划详情"""

    plan_id: Optional[str] = Field(
        default=None, description="计划ID，不填则查当前活跃计划"
    )


@tool(args_schema=GetPlanDetailInput)
async def get_plan_detail_tool(
    plan_id: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    查看训练计划详情（含训练日与动作，含可编辑的 exercise_id / plan_day_id）。

    使用场景：
    - 用户问"我的计划里有哪些动作"、"周三练什么"
    - 在编辑/删除动作前，先用本工具获取 exercise_id（动作ID）与 plan_day_id（训练日ID）

    Returns:
        计划完整结构：days[].id 为 plan_day_id，days[].exercises[].id 为 exercise_id
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            pid = await _resolve_plan_id(db, user_id, plan_id)
            plan = await PlanService.get_plan_detail(db, pid, user_id)
            return {
                "success": True,
                "plan": PlanOut.model_validate(plan).model_dump(mode="json"),
            }
    except Exception as e:
        return error_response(e)


# ===== 计划元信息更新 =====


class UpdatePlanInput(BaseModel):
    """更新训练计划元信息（名称/目标/难度/周期）"""

    plan_id: Optional[str] = Field(default=None, description="计划ID，不填则改活跃计划")
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    goal: Optional[str] = Field(
        default=None, pattern="^(lose_fat|gain_muscle|maintain|improve_health)$"
    )
    difficulty: Optional[str] = Field(
        default=None, pattern="^(beginner|intermediate|advanced)$"
    )
    weeks: Optional[int] = Field(default=None, ge=1, le=52)


@tool(args_schema=UpdatePlanInput)
async def update_plan_tool(
    plan_id: Optional[str] = None,
    name: Optional[str] = None,
    goal: Optional[str] = None,
    difficulty: Optional[str] = None,
    weeks: Optional[int] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    更新训练计划元信息（名称、目标、难度、周期）。不中断，直接执行。

    使用场景：
    - 用户说"把难度改成中级" -> difficulty="intermediate"
    - 用户说"计划改名叫增肌期" -> name="增肌期"
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            pid = await _resolve_plan_id(db, user_id, plan_id)
            data = PlanUpdate(name=name, goal=goal, difficulty=difficulty, weeks=weeks)
            plan = await PlanService.update_plan(db, pid, user_id, data)
            return {
                "success": True,
                "plan_id": str(pid),
                "plan_name": plan.name,
                "message": f"已更新计划「{plan.name}」",
            }
    except Exception as e:
        return error_response(e)


# ===== 计划归档（软删除，HITL 审批） =====


class DeletePlanInput(BaseModel):
    """归档训练计划"""

    plan_id: Optional[str] = Field(default=None, description="计划ID，不填则归档活跃计划")


@tool(args_schema=DeletePlanInput)
async def delete_plan_tool(
    plan_id: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    归档（软删除）训练计划：计划与训练日/动作保留、可恢复，不再作为活跃计划。

    使用场景：
    - 用户说"这个计划不要了"、"删掉当前计划"

    执行前会要求用户审批确认。
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            pid = await _resolve_plan_id(db, user_id, plan_id)
            plan = await PlanService.get_plan_detail(db, pid, user_id)
            await PlanService.delete_plan(db, pid, user_id)
            return {
                "success": True,
                "plan_id": str(pid),
                "plan_name": plan.name,
                "message": f"已归档计划「{plan.name}」，可重新激活",
            }
    except Exception as e:
        return error_response(e)


# ===== 训练日（按星期） =====


class AddPlanDayInput(BaseModel):
    """为计划增加训练日（按星期）"""

    plan_id: Optional[str] = Field(default=None, description="计划ID，不填则加到活跃计划")
    day_of_week: int = Field(ge=1, le=7, description="1=周一 ... 7=周日")
    focus: Optional[str] = Field(default=None, max_length=100, description="训练重点，如 胸+三头")
    rest_seconds: int = Field(default=60, ge=0, description="组间休息(秒)")
    exercises: Optional[List[PlanExerciseCreate]] = Field(
        default=None, description="可选，预置动作列表"
    )


@tool(args_schema=AddPlanDayInput)
async def add_plan_day_tool(
    plan_id: Optional[str] = None,
    day_of_week: int = 1,
    focus: Optional[str] = None,
    rest_seconds: int = 60,
    exercises: Optional[List[PlanExerciseCreate]] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    为训练计划增加一个训练日（按星期）。不中断，直接执行。

    使用场景：
    - 用户说"加一个周五的训练日" -> day_of_week=5
    - 用户说"周一改成推日" -> day_of_week=1, focus="胸+肩+三头"
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            pid = await _resolve_plan_id(db, user_id, plan_id)
            data = PlanDayCreate(
                day_of_week=day_of_week,
                focus=focus,
                rest_seconds=rest_seconds,
                exercises=exercises or [],
            )
            await PlanService.add_plan_day(db, pid, user_id, data)
            weekday = _WEEKDAYS[day_of_week - 1]
            return {
                "success": True,
                "plan_id": str(pid),
                "day_of_week": day_of_week,
                "message": f"已添加{weekday}训练日",
            }
    except Exception as e:
        return error_response(e)


class RemovePlanDayInput(BaseModel):
    """删除训练日（按星期定位）"""

    plan_id: Optional[str] = Field(default=None, description="计划ID，不填则改活跃计划")
    day_of_week: int = Field(ge=1, le=7, description="要删除的训练日星期，1=周一...7=周日")


@tool(args_schema=RemovePlanDayInput)
async def remove_plan_day_tool(
    plan_id: Optional[str] = None,
    day_of_week: int = 1,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    删除训练计划中指定星期的训练日（按星期定位）。

    使用场景：
    - 用户说"周三改成休息日" -> day_of_week=3
    - 用户说"删掉周五的训练" -> day_of_week=5

    执行前会要求用户审批确认。
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            pid = await _resolve_plan_id(db, user_id, plan_id)
            plan = await PlanService.get_plan_detail(db, pid, user_id)
            matching = [d for d in plan.days if d.day_of_week == day_of_week]
            if not matching:
                weekday = _WEEKDAYS[day_of_week - 1]
                raise NotFoundException(f"该计划没有{weekday}训练日")
            day = matching[0]
            note = "（找到多个同星期训练日，已删除第一个）" if len(matching) > 1 else ""
            await PlanService.delete_plan_day(db, day.id, user_id)
            weekday = _WEEKDAYS[day_of_week - 1]
            return {
                "success": True,
                "plan_id": str(pid),
                "removed_day_of_week": day_of_week,
                "message": f"已删除{weekday}训练日{note}",
            }
    except Exception as e:
        return error_response(e)


# ===== 训练日动作（按 exercise_id / plan_day_id） =====


class AddExerciseInput(BaseModel):
    """为指定训练日添加动作"""

    plan_day_id: str = Field(description="目标训练日ID（先用 get_plan_detail_tool 获取）")
    exercise_id: Optional[str] = Field(
        default=None, description="动作库动作ID（与 custom_name 二选一）"
    )
    custom_name: Optional[str] = Field(
        default=None, max_length=200, description="自定义动作名（与 exercise_id 二选一）"
    )
    exercise_type: Optional[str] = Field(
        default=None, pattern="^(strength|cardio)$", description="动作类型，默认 strength"
    )
    sets: Optional[int] = Field(default=None, ge=1, le=20, description="力量动作组数")
    reps: Optional[int] = Field(default=None, ge=1, le=100, description="力量动作次数")
    weight_kg: Optional[float] = Field(default=None, ge=0)
    duration_min: Optional[int] = Field(default=None, ge=1, description="有氧时长(分钟)")
    distance_km: Optional[float] = Field(default=None, ge=0, description="有氧距离(km)")
    calories_per_min: Optional[float] = Field(default=None, ge=0, description="每分钟消耗(kcal)")
    notes: Optional[str] = Field(default=None, max_length=500)


@tool(args_schema=AddExerciseInput)
async def add_exercise_tool(
    plan_day_id: str,
    exercise_id: Optional[str] = None,
    custom_name: Optional[str] = None,
    exercise_type: Optional[str] = None,
    sets: Optional[int] = None,
    reps: Optional[int] = None,
    weight_kg: Optional[float] = None,
    duration_min: Optional[int] = None,
    distance_km: Optional[float] = None,
    calories_per_min: Optional[float] = None,
    notes: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    为指定训练日添加一个动作（力量或自定义有氧均可）。不中断，直接执行。

    使用场景：
    - 用户说"周三加个卧推 4组8次" -> plan_day_id=..., custom_name="卧推", sets=4, reps=8
    - 用户说"加个跑步30分钟" -> custom_name="跑步", exercise_type="cardio", duration_min=30

    需先用 get_plan_detail_tool 获取目标训练日的 plan_day_id。
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            data = PlanExerciseCreate(
                exercise_id=UUID(exercise_id) if exercise_id else None,
                custom_name=custom_name,
                exercise_type=exercise_type,
                sets=sets,
                reps=reps,
                weight_kg=weight_kg,
                duration_min=duration_min,
                distance_km=distance_km,
                calories_per_min=calories_per_min,
                notes=notes,
            )
            await PlanService.add_exercise_to_day(db, UUID(plan_day_id), user_id, data)
            return {
                "success": True,
                "plan_day_id": plan_day_id,
                "message": "已添加动作到训练日",
            }
    except Exception as e:
        return error_response(e)


class UpdateExerciseInput(BaseModel):
    """修改训练日动作"""

    exercise_id: str = Field(description="要修改的动作ID（先用 get_plan_detail_tool 获取）")
    exercise_type: Optional[str] = Field(
        default=None, pattern="^(strength|cardio)$", description="切换动作类型"
    )
    sets: Optional[int] = Field(default=None, ge=1, le=20)
    reps: Optional[int] = Field(default=None, ge=1, le=100)
    weight_kg: Optional[float] = Field(default=None, ge=0)
    duration_min: Optional[int] = Field(default=None, ge=1, description="有氧时长(分钟)")
    distance_km: Optional[float] = Field(default=None, ge=0, description="有氧距离(km)")
    calories_per_min: Optional[float] = Field(default=None, ge=0, description="每分钟消耗(kcal)")
    sort_order: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=500)


@tool(args_schema=UpdateExerciseInput)
async def update_exercise_tool(
    exercise_id: str,
    exercise_type: Optional[str] = None,
    sets: Optional[int] = None,
    reps: Optional[int] = None,
    weight_kg: Optional[float] = None,
    duration_min: Optional[int] = None,
    distance_km: Optional[float] = None,
    calories_per_min: Optional[float] = None,
    sort_order: Optional[int] = None,
    notes: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    修改训练日中的一个动作（组次/重量/有氧参数/排序等）。不中断，直接执行。

    使用场景：
    - 用户说"卧推重量改成60kg" -> exercise_id=..., weight_kg=60
    - 用户说"跑步加到40分钟" -> exercise_id=..., duration_min=40

    需先用 get_plan_detail_tool 获取 exercise_id。
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            data = PlanExerciseUpdate(
                exercise_type=exercise_type,
                sets=sets,
                reps=reps,
                weight_kg=weight_kg,
                duration_min=duration_min,
                distance_km=distance_km,
                calories_per_min=calories_per_min,
                sort_order=sort_order,
                notes=notes,
            )
            await PlanService.update_exercise(db, UUID(exercise_id), user_id, data)
            return {
                "success": True,
                "exercise_id": exercise_id,
                "message": "已更新动作",
            }
    except Exception as e:
        return error_response(e)


class RemoveExerciseInput(BaseModel):
    """删除训练日动作"""

    exercise_id: str = Field(description="要删除的动作ID（先用 get_plan_detail_tool 获取）")


@tool(args_schema=RemoveExerciseInput)
async def remove_exercise_tool(
    exercise_id: str,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    删除训练日中的一个动作。

    使用场景：
    - 用户说"删掉二头弯举" -> exercise_id=...
    - 用户说"周三去掉那个动作" -> exercise_id=...

    需先用 get_plan_detail_tool 获取 exercise_id。执行前会要求用户审批确认。
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            await PlanService.delete_exercise(db, UUID(exercise_id), user_id)
            return {
                "success": True,
                "exercise_id": exercise_id,
                "message": "已删除动作",
            }
    except Exception as e:
        return error_response(e)
