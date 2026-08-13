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


@tool(args_schema=CheckinInput)
async def checkin_tool(
    exercises: List[ExerciseRecord],
    duration_min: int,
    actual_intensity: Optional[str] = None,
    calories_burned: Optional[int] = None,
    mood: Optional[int] = None,
    note: Optional[str] = None,
    checkin_date: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    记录今日训练打卡。

    当用户说"今天练了..."、"打卡"、"完成了训练"等表达时调用。
    会解析用户描述的动作、组数、次数、重量，写入数据库，
    并自动按星期关联当前活跃计划的训练日。

    Returns:
        打卡确认信息 + 当前连续打卡天数；
        若打卡日期命中活跃计划的训练日，额外返回 plan_match（计划/已完成/未完成/计划外动作对比）；
        若部分动作无法匹配动作库，则不落库，返回 success=False + unmatched + suggestions 候选动作
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
            matched = await ExerciseService.match_names(
                db, [ex.name for ex in exercises]
            )

            unmatched = [name for name, ex_ in matched.items() if ex_ is None]
            if unmatched:
                suggestions = {}
                for name in unmatched:
                    candidates = await ExerciseService.search(db, keyword=name, limit=5)
                    if not candidates:
                        candidates = await _semantic_candidates(db, name)
                    suggestions[name] = [c.name for c in candidates]
                return {
                    "success": False,
                    "error": "部分动作未匹配到动作库，本次打卡未记录",
                    "unmatched": unmatched,
                    "suggestions": suggestions,
                    "message": (
                        f"以下动作未匹配到动作库：{'、'.join(unmatched)}。"
                        "请根据 suggestions 候选与用户确认正确动作名（或询问是否去掉该动作），"
                        "确认后重新调用 checkin_tool。不要编造打卡结果。"
                    ),
                }

            matched_exercises = [
                CheckinExerciseCreate(
                    exercise_id=matched[ex.name].id,
                    sets_done=ex.sets_done,
                    reps_done=ex.reps_done,
                    weight_kg=ex.weight_kg,
                    rpe=ex.rpe,
                    notes=ex.notes,
                )
                for ex in exercises
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
                plan, plan_day = plan_match
                planned_map = {
                    pex.exercise_id: (
                        pex.exercise.name if pex.exercise else pex.custom_name
                    )
                    for pex in plan_day.exercises
                    if pex.exercise_id
                }
                done_ids = {matched[ex.name].id for ex in exercises}
                completed = [n for eid, n in planned_map.items() if eid in done_ids]
                skipped = [n for eid, n in planned_map.items() if eid not in done_ids]
                extra = sorted(
                    {
                        matched[ex.name].name
                        for ex in exercises
                        if matched[ex.name].id not in planned_map
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
