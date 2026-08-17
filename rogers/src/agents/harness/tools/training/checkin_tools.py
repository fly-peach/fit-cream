"""
打卡相关 Tools

供 Agent 调用，完成训练打卡和连续天数查询：
- checkin_tool: 自然语言打卡（解析动作名称、组数、次数，匹配动作库后写入数据库），
  自动按星期关联活跃计划的训练日（plan_day_id），并返回计划 vs 实际的完成度对比
- get_streak_tool: 查询当前/最长连续打卡天数

直接调用 CheckinService / ExerciseService / PlanService（同进程融合，不走 HTTP）。
"""

from datetime import date as date_type
from typing import List, Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.runtime.memory.embeddings import get_embedding_model
from src.agents.harness.tools._common import error_response, extract_user_id, session_scope
from src.fitme.schemas.checkin import CheckinCreate, CheckinExerciseCreate
from src.fitme.services.checkin_service import CheckinService
from src.fitme.services.exercise_service import ExerciseService
from src.fitme.services.plan_service import PlanService
from utils.timeutil import today as tz_today


async def _semantic_candidates(db, name: str, limit: int = 5) -> list:
    """关键词检索未命中时，按语义向量召回近似动作（尽力而为，失败返回空列表）。"""
    try:
        query_embedding = await get_embedding_model().aget_text_embedding(name)
        scored = await ExerciseService.semantic_search(db, query_embedding, limit=limit)
        return [ex for ex, _ in scored]
    except Exception:
        return []


async def _match_user_custom_names(
    db, user_id: UUID, names: List[str]
) -> set[str]:
    """从用户历史打卡与计划动作中召回已建立的自定义动作名（大小写不敏感全等匹配）。

    命中说明该名字是用户长期使用的自定义动作，可直接按 custom_name 记录，
    无需再让 Agent 与用户反复确认。
    """
    lowered = {n.strip().lower() for n in names if n and n.strip()}
    if not lowered:
        return set()

    from sqlalchemy import select

    from src.fitme.models.checkin import Checkin, CheckinExercise
    from src.fitme.models.plan import Plan, PlanDay, PlanDayExercise

    custom_set: set[str] = set()
    queries = (
        select(CheckinExercise.custom_name)
        .join(Checkin, Checkin.id == CheckinExercise.checkin_id)
        .where(Checkin.user_id == user_id, CheckinExercise.custom_name.isnot(None)),
        select(PlanDayExercise.custom_name)
        .join(PlanDay, PlanDay.id == PlanDayExercise.plan_day_id)
        .join(Plan, Plan.id == PlanDay.plan_id)
        .where(Plan.user_id == user_id, PlanDayExercise.custom_name.isnot(None)),
    )
    for query in queries:
        rows = (await db.execute(query)).all()
        custom_set.update({r[0].strip().lower() for r in rows if r[0] and r[0].strip()})
    return {n for n in names if n.strip().lower() in custom_set}


class ExerciseRecord(BaseModel):
    """单个动作的打卡记录（agent-facing，按名称输入）。

    例外说明（方案 C2 + D6）：CRUD schema CheckinExerciseCreate 必须保持 id-only，
    而 agent 入参按名称更自然，故此处保留极简 name-based 输入 schema；
    名称→ID 匹配委托 ExerciseService.match_names，再组装 id-based 服务 schema。
    """

    name: str = Field(description="动作名称")
    sets_done: int = Field(ge=1, description="完成组数")
    reps_done: int = Field(ge=1, description="每组次数")
    weight_kg: Optional[float] = Field(default=None, description="重量（kg）")
    duration_min: Optional[int] = Field(
        default=None, ge=1, description="有氧实际时长（分钟），跑步/骑行等有氧动作填写"
    )
    distance_km: Optional[float] = Field(
        default=None, ge=0, description="有氧实际距离（km），跑步/骑行等有氧动作填写"
    )
    rpe: Optional[int] = Field(default=None, ge=1, le=10, description="自感用力等级 1-10")
    notes: Optional[str] = Field(default=None, description="动作备注")


class CheckinInput(BaseModel):
    """打卡输入参数"""

    exercises: List[ExerciseRecord] = Field(description="完成的动作列表")
    duration_min: int = Field(ge=1, description="训练时长（分钟）")
    actual_intensity: Optional[str] = Field(default=None, description="实际强度: low/medium/high")
    calories_burned: Optional[int] = Field(default=None, description="估算消耗热量(kcal)")
    mood: Optional[int] = Field(default=None, ge=1, le=5, description="心情评分 1-5")
    note: Optional[str] = Field(default=None, description="备注")
    checkin_date: Optional[str] = Field(
        default=None, description="打卡日期 YYYY-MM-DD，默认今天"
    )
    allow_custom: bool = Field(
        default=False,
        description=(
            "是否允许把未匹配动作库的动作按自定义动作（custom_name）记录。"
            "用户明确表示该动作是自定义动作（非动作库动作）后置 true"
        ),
    )
    allow_custom_names: Optional[List[str]] = Field(
        default=None,
        description=(
            "自定义动作白名单：这些名称即便未匹配动作库也可直接按自定义动作记录，"
            "无需置 allow_custom。用户已明确表示用这些名字记录后填写"
        ),
    )


@tool(args_schema=CheckinInput)
async def checkin_tool(
    exercises: List[ExerciseRecord],
    duration_min: int,
    actual_intensity: Optional[str] = None,
    calories_burned: Optional[int] = None,
    mood: Optional[int] = None,
    note: Optional[str] = None,
    checkin_date: Optional[str] = None,
    allow_custom: bool = False,
    allow_custom_names: Optional[List[str]] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    记录今日训练打卡。

    当用户说"今天练了..."、"打卡"、"完成了训练"等表达时调用。
    会解析用户描述的动作、组数、次数、重量，写入数据库，
    并自动按星期关联当前活跃计划的训练日。

    动作匹配三级策略：
    1. 动作库命中 -> 记录为动作库动作（exercise_id）
    2. 用户历史自定义动作（历史打卡/计划中的 custom_name）-> 直接按自定义动作记录
    3. 全新未匹配动作 -> 默认不落库返回 unmatched+suggestions；用户确认是自定义
       动作后，以 allow_custom=true 重新调用，按自定义动作记录

    Returns:
        打卡确认信息 + 当前连续打卡天数 + custom_actions（本次按自定义记录的动作）；
        若打卡日期命中活跃计划的训练日，额外返回 plan_match（计划/已完成/未完成/计划外动作对比）；
        若存在用户未确认的全新未匹配动作，则不落库，返回 success=False + unmatched + suggestions
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "无法获取用户信息"}

    try:
        target_date = (
            date_type.fromisoformat(checkin_date) if checkin_date else tz_today()
        )
    except ValueError:
        return {
            "success": False,
            "error": f"打卡日期格式无效：{checkin_date}，应为 YYYY-MM-DD",
        }

    try:
        async with session_scope() as db:
            names = [ex.name for ex in exercises]
            matched = await ExerciseService.match_names(db, names)

            # 未命中动作库的名字：先按用户历史自定义动作召回 + 白名单（allow_custom_names），
            # 剩余为全新未匹配
            unmatched = [n for n, ex_ in matched.items() if ex_ is None]
            known_custom: set[str] = set()
            novel: List[str] = []
            if unmatched:
                known_custom = await _match_user_custom_names(db, user_id, unmatched)
                approved = {
                    n.strip().lower() for n in (allow_custom_names or []) if n and n.strip()
                }
                known_custom.update(
                    n for n in unmatched if n.strip().lower() in approved
                )
                novel = [n for n in unmatched if n not in known_custom]

            if novel and not allow_custom:
                suggestions = {}
                for name in novel:
                    candidates = await ExerciseService.search(db, keyword=name, limit=5)
                    if not candidates:
                        candidates = await _semantic_candidates(db, name)
                    suggestions[name] = [c.name for c in candidates]
                return {
                    "success": False,
                    "error": "部分动作未匹配到动作库，本次打卡未记录",
                    "unmatched": novel,
                    "suggestions": suggestions,
                    "message": (
                        f"以下动作未匹配到动作库：{'、'.join(novel)}。"
                        "请与用户确认：若为动作库动作，用 suggestions 候选名重新调用；"
                        "若用户确认是自定义动作，以 allow_custom=true 重新调用 checkin_tool 记录。"
                        "不要编造打卡结果。"
                    ),
                }

            # 组装打卡动作：库命中用 exercise_id，其余（历史自定义 + 用户确认的自定义）用 custom_name
            checked: List[tuple[Optional[UUID], Optional[str], ExerciseRecord]] = []
            custom_actions: List[str] = []
            for ex in exercises:
                lib = matched.get(ex.name)
                if lib is not None:
                    checked.append((lib.id, None, ex))
                else:
                    checked.append((None, ex.name, ex))
                    custom_actions.append(ex.name)

            matched_exercises = [
                CheckinExerciseCreate(
                    exercise_id=exercise_id,
                    custom_name=custom_name,
                    sets_done=ex.sets_done,
                    reps_done=ex.reps_done,
                    weight_kg=ex.weight_kg,
                    duration_min=ex.duration_min,
                    distance_km=ex.distance_km,
                    rpe=ex.rpe,
                    notes=ex.notes,
                )
                for exercise_id, custom_name, ex in checked
            ]

            plan_match = await PlanService.get_plan_day_for_date(db, user_id, target_date)
            plan_day_id = plan_match[1].id if plan_match else None

            checkin = await CheckinService.create_checkin(
                db=db,
                user_id=user_id,
                data=CheckinCreate(
                    date=target_date,
                    plan_day_id=plan_day_id,
                    duration_min=duration_min,
                    actual_intensity=actual_intensity,
                    calories_burned=calories_burned,
                    mood=mood,
                    note=note,
                    exercises=matched_exercises,
                ),
            )

            streak = await CheckinService.get_streak(db, user_id)

            plan_feedback = None
            if plan_match:
                plan, plan_day, plan_exercises = plan_match
                done_ids = {eid for eid, _, _ in checked if eid is not None}
                done_custom = {
                    cn.strip().lower() for _, cn, _ in checked if cn is not None
                }
                completed: List[str] = []
                skipped: List[str] = []
                for pex in plan_exercises:
                    pname = pex.exercise.name if pex.exercise else pex.custom_name
                    if not pname:
                        continue
                    if (pex.exercise_id and pex.exercise_id in done_ids) or (
                        pex.custom_name
                        and pex.custom_name.strip().lower() in done_custom
                    ):
                        completed.append(pname)
                    else:
                        skipped.append(pname)
                planned_lib_ids = {
                    pex.exercise_id for pex in plan_exercises if pex.exercise_id
                }
                planned_custom_names = {
                    pex.custom_name.strip().lower()
                    for pex in plan_exercises
                    if pex.custom_name
                }
                extra = sorted(
                    {
                        (matched[ex.name].name if eid else cn)
                        for eid, cn, ex in checked
                        if (eid is not None and eid not in planned_lib_ids)
                        or (
                            cn is not None
                            and cn.strip().lower() not in planned_custom_names
                        )
                    }
                )
                plan_feedback = {
                    "plan_name": plan.name,
                    "focus": plan_day.focus,
                    "completed": completed,
                    "skipped": skipped,
                    "extra": extra,
                }

            message = f"打卡成功！已连续训练 {streak['current_streak']} 天 🔥"
            if custom_actions:
                message += (
                    f" 其中 {'、'.join(custom_actions)} 是自定义动作，已按自定义动作记录。"
                )
            if plan_feedback:
                if plan_feedback["skipped"]:
                    message += (
                        f" 今日计划（{plan_feedback['focus']}）还有未完成动作："
                        + "、".join(plan_feedback["skipped"])
                    )
                elif plan_feedback["completed"]:
                    message += f" 今日计划（{plan_feedback['focus']}）已全部完成 💪"

            result = {
                "success": True,
                "checkin_id": str(checkin.id),
                "date": str(target_date),
                "exercises_count": len(matched_exercises),
                "custom_actions": custom_actions or None,
                "duration_min": duration_min,
                "current_streak": streak["current_streak"],
                "message": message,
            }
            if plan_feedback:
                result["plan_match"] = plan_feedback
            return result
    except Exception as e:
        return error_response(e)


@tool
async def get_streak_tool(config: "RunnableConfig" = None) -> dict:  # type: ignore[assignment]
    """
    获取当前用户的连续打卡天数统计。

    当用户问"我连续练了几天"、"打卡天数"等时调用。

    Returns:
        当前连续天数、最长连续天数、最后打卡日期
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "无法获取用户信息"}

    try:
        async with session_scope() as db:
            streak = await CheckinService.get_streak(db, user_id)

            return {
                "success": True,
                "current_streak": streak["current_streak"],
                "longest_streak": streak["longest_streak"],
                "last_checkin_date": str(streak["last_checkin_date"])
                if streak["last_checkin_date"]
                else None,
            }
    except Exception as e:
        return error_response(e)
