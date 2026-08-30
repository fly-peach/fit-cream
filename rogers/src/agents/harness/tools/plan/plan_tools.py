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
from sqlalchemy import select

from src.agents.harness.tools._common import error_response, extract_user_id, session_scope
from src.fitme.models.exercise import Exercise
from src.fitme.schemas.diet_plan import DietDayCreate, DietPlanCreate
from src.fitme.schemas.plan import (
    PlanCreate,
    PlanDayCreate,
    PlanExerciseCreate,
    PlanExerciseUpdate,
    PlanOut,
    PlanUpdate,
)
from src.fitme.services.diet_plan_service import DietPlanService
from src.fitme.services.plan_service import PlanService
from src.fitme.services.user_service import UserService
from utils.exceptions import BusinessException, ErrorCode, NotFoundException


_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


async def _ensure_exercise_ids_exist(db, exercises) -> None:
    """批量校验各 exercise_id 均存在于动作库；缺失则抛友好业务异常。

    只卡 exercise_id 指向库中不存在动作的情况（避免 commit 时裸 IntegrityError）；
    custom_name 动作不校验存在性（保留「用户点名库外动作」能力），仅由服务层打标 source。
    """
    ids = list(dict.fromkeys(ex.exercise_id for ex in exercises if ex.exercise_id))
    if not ids:
        return
    result = await db.execute(select(Exercise.id).where(Exercise.id.in_(ids)))
    found = {row[0] for row in result.all()}
    missing = [str(uid) for uid in ids if uid not in found]
    if missing:
        raise BusinessException(
            ErrorCode.BAD_REQUEST,
            f"以下动作在动作库中不存在，请重新调用 get_exercises_tool 检索后再设计："
            f"{', '.join(missing)}",
        )


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
        description="用户偏好说明，如'不喜欢跑步'、'没有器械'、'膝盖有伤'。"
        "仅当未提供 days 时用于后端模板生成；提供 days 时本字段忽略。",
    )
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="计划名称。提供 days 时建议传入自定义名称；不传则自动生成。",
    )
    weeks: Optional[int] = Field(
        default=None, ge=1, le=52, description="计划周期(周)。提供 days 时可指定。"
    )
    days: Optional[List[PlanDayCreate]] = Field(
        default=None,
        description=(
            "逐日设计的完整训练日结构（计划设计待办队列流程产出）。"
            "提供时后端直接按此落库，不再用后端模板重新生成，确保提案与落库一致。"
            "未提供时走后端 generate_plan_from_goal 模板生成（向后兼容）。"
        ),
    )
    milestone_id: Optional[str] = Field(
        default=None,
        description="关联闯关关卡 ID（goal_milestones.id），有 active 路线图时传当前关",
    )


@tool(args_schema=CreatePlanInput)
async def create_plan_tool(
    goal: str,
    days_per_week: int,
    difficulty: str = "beginner",
    preferences: Optional[str] = None,
    name: Optional[str] = None,
    weeks: Optional[int] = None,
    days: Optional[List[PlanDayCreate]] = None,
    milestone_id: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    根据用户的健身目标创建个性化训练计划。

    使用场景：
    - 用户说"我想减脂，每周练4天"-> goal="lose_fat", days_per_week=4
    - 用户说"帮我制定一个增肌计划"-> goal="gain_muscle"
    - 用户说"我是新手，想开始健身"-> goal="improve_health", difficulty="beginner"
    - 计划设计待办队列流程：逐日协同设计完成后，传入 days（各日动作设计）直接落库

    会考虑用户的身体数据（身高、体重、年龄）生成合适的计划。
    若提供 days 参数，则按 agent 设计的逐日结构直接落库（不再后端模板生成），
    确保提案与落库内容一致；未提供 days 时走后端智能生成。

    Returns:
        包含计划详情、训练日安排的结构化数据
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            if days:
                # 队列流程：按 agent 逐日协同设计的结构直接落库，跳过后端模板生成
                await _ensure_exercise_ids_exist(
                    db, [ex for day in days for ex in day.exercises]
                )
                plan_name = name or f"{goal}计划 - 每周{days_per_week}天"
                created = await PlanService.create_plan(
                    db,
                    user_id,
                    PlanCreate(
                        name=plan_name,
                        goal=goal,
                        difficulty=difficulty,
                        weeks=weeks,
                        days=days,
                        milestone_id=UUID(milestone_id) if milestone_id else None,
                    ),
                )
                # 预加载 days->exercises->exercise，避免 plan_data 访问关系触发异步懒加载
                plan = await PlanService.get_plan_detail(db, created.id, user_id)
                mode = "days"
            else:
                # 旧路径：后端模板智能生成（向后兼容）。
                # 注意：未传 days 时，落库内容由后端模板生成，可能与
                # present_plan_tool 提案不一致；通过 mode 标记以便审计。
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
                mode = "template_generated"

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

            msg = f"已为你创建{goal_name}计划，每周训练{days_per_week}天，难度{difficulty}。"
            if mode == "template_generated":
                msg += "（本次按目标由系统模板生成，未按逐日提案落库）"

            return {
                "success": True,
                "plan": plan_data,
                "persisted_plan": plan_data,
                "mode": mode,
                "message": msg,
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
    activity_level: Optional[str] = Field(
        default=None,
        description=(
            "用户每周运动时长档位：light(每周2-3小时)/moderate(每周4-5小时)/"
            "active(每周6-7小时)/very_active(每周8-9小时)。"
            "不填则按默认 moderate 换算（用于自动计算热量目标）。"
        ),
    )
    preferences: Optional[str] = Field(
        default=None,
        description="饮食偏好或禁忌，如'不吃辣'、'素食'、'乳糖不耐'",
    )
    days: Optional[List[DietDayCreate]] = Field(
        default=None,
        description=(
            "逐日设计的完整饮食日结构（含每日各餐 food_name/热量/宏量素）。"
            "提供时后端直接按此落库，确保提案与落库一致；"
            "未提供时走后端模板生成（向后兼容）。"
        ),
    )


@tool(args_schema=CreateDietPlanInput)
async def create_diet_plan_tool(
    goal: str,
    target_calories: Optional[int] = None,
    activity_level: Optional[str] = None,
    preferences: Optional[str] = None,
    days: Optional[List[DietDayCreate]] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    根据用户的健身目标创建个性化饮食计划。

    使用场景：
    - 用户说"帮我制定一个减脂饮食计划"-> goal="lose_fat"
    - 用户说"我想增肌，每天吃2500大卡"-> goal="gain_muscle", target_calories=2500
    - 用户说"帮我安排健康饮食"-> goal="improve_health"

    会根据用户身体数据自动计算合适的热量和宏量素比例。
    若提供 days 参数，则按 agent 设计的逐日结构直接落库（不再后端模板生成），
    确保提案与落库内容一致；未提供 days 时走后端模板生成（向后兼容）。

    Returns:
        包含饮食计划详情、每日餐食安排的结构化数据
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            if days:
                # 逐日设计流程：按 agent 设计的结构直接落库，跳过后端模板生成
                plan_name = f"{goal}饮食计划"
                diet_plan = await DietPlanService.create_diet_plan(
                    db,
                    user_id,
                    DietPlanCreate(
                        name=plan_name,
                        target_calories=target_calories,
                        goal=goal,
                        days=days,
                    ),
                )
                # 预加载 days->meals，避免访问关系触发异步懒加载
                diet_plan = await DietPlanService.get_diet_plan_detail(
                    db, diet_plan.id, user_id
                )
                mode = "days"
            else:
                # 旧路径：后端模板智能生成（向后兼容）
                user_data = await UserService.get_body_summary(db, user_id)
                diet_plan = await DietPlanService.generate_diet_plan_from_goal(
                    db=db,
                    user_id=user_id,
                    goal=goal,
                    target_calories=target_calories,
                    preferences=preferences,
                    user_data=user_data,
                    activity_level=activity_level,
                )
                mode = "template_generated"

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
                "persisted_plan": plan_data,
                "mode": mode,
                "message": f"已为你创建{goal_name}饮食计划，每日目标热量 {diet_plan.target_calories} kcal，包含{len(diet_plan.days)}天完整餐食安排。",
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

    注意：同星期已存在训练日时，会与该训练日并存（打卡 plan_match 会合并比对）。
    若用户意图是覆盖而非新增，应先与用户确认是否重复，避免同星期出现多个训练日。
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            pid = await _resolve_plan_id(db, user_id, plan_id)
            if exercises:
                await _ensure_exercise_ids_exist(db, exercises)
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


class SyncPlanDayInput(BaseModel):
    """同步训练日（把源星期复制到目标星期）"""

    plan_id: Optional[str] = Field(default=None, description="计划ID，不填则用活跃计划")
    source_day_of_week: int = Field(ge=1, le=7, description="源训练日星期，1=周一...7=周日")
    target_day_of_week: int = Field(ge=1, le=7, description="目标训练日星期，1=周一...7=周日")


@tool(args_schema=SyncPlanDayInput)
async def sync_plan_day_tool(
    source_day_of_week: int = 1,
    target_day_of_week: int = 1,
    plan_id: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    同步训练日：把计划中某一星期的训练日整体复制到另一星期（含动作）。

    使用场景：
    - 用户说"把周三的训练复制到周五" -> source_day_of_week=3, target_day_of_week=5
    - 用户说"同步计划，把周一的胸部训练套到今天" -> source_day_of_week=1, target_day_of_week=<今天>

    Returns:
        同步后的完整计划
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            pid = await _resolve_plan_id(db, user_id, plan_id)
            plan = await PlanService.copy_plan_day(
                db,
                pid,
                user_id,
                source_day_of_week=source_day_of_week,
                target_day_of_week=target_day_of_week,
            )
            src = _WEEKDAYS[source_day_of_week - 1]
            dst = _WEEKDAYS[target_day_of_week - 1]
            return {
                "success": True,
                "plan_id": str(pid),
                "plan": PlanOut.model_validate(plan).model_dump(mode="json"),
                "message": f"已把{src}训练日同步到{dst}",
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
            await _ensure_exercise_ids_exist(db, [data])
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
            # 只收集非 None 字段：全部字段（含 None）直接塞进 PlanExerciseUpdate，
            # model_dump(exclude_unset=True) 排不掉，会把 sort_order 等未指定字段
            # 置 NULL，触发 plan_day_exercises.sort_order NOT NULL 约束（与 更新健身画像
            # 同一反模式，2026-08-30 工具测试暴露）。
            field_values = {
                "exercise_type": exercise_type,
                "sets": sets,
                "reps": reps,
                "weight_kg": weight_kg,
                "duration_min": duration_min,
                "distance_km": distance_km,
                "calories_per_min": calories_per_min,
                "sort_order": sort_order,
                "notes": notes,
            }
            data = PlanExerciseUpdate(
                **{k: v for k, v in field_values.items() if v is not None}
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
