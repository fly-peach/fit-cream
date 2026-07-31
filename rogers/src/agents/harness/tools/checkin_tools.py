"""
打卡相关 Tools

供 Agent 调用，完成训练打卡和连续天数查询：
- checkin_tool: 自然语言打卡（解析动作名称、组数、次数，匹配动作库后写入数据库）
- get_streak_tool: 查询当前/最长连续打卡天数

直接调用 CheckinService / ExerciseService（同进程融合，不走 HTTP）。
"""

from datetime import date as date_type
from typing import List, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.tools._common import error_response, extract_user_id, session_scope
from src.fitme.schemas.checkin import CheckinCreate, CheckinExerciseCreate
from src.fitme.services.checkin_service import CheckinService
from src.fitme.services.exercise_service import ExerciseService


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
    exercises: List[dict],
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
    会解析用户描述的动作、组数、次数、重量，写入数据库。

    Returns:
        打卡确认信息 + 当前连续打卡天数
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "无法获取用户信息"}

    target_date = (
        date_type.fromisoformat(checkin_date) if checkin_date else date_type.today()
    )

    try:
        async with session_scope() as db:
            matched = await ExerciseService.match_names(
                db, [ex["name"] for ex in exercises]
            )

            matched_exercises = [
                CheckinExerciseCreate(
                    exercise_id=matched[ex["name"]].id,
                    sets_done=ex["sets_done"],
                    reps_done=ex["reps_done"],
                    weight_kg=ex.get("weight_kg"),
                    rpe=ex.get("rpe"),
                    notes=ex.get("notes"),
                )
                for ex in exercises
                if matched.get(ex["name"])
            ]

            checkin = await CheckinService.create_checkin(
                db=db,
                user_id=user_id,
                data=CheckinCreate(
                    date=target_date,
                    plan_day_id=None,
                    duration_min=duration_min,
                    actual_intensity=actual_intensity,
                    calories_burned=calories_burned,
                    mood=mood,
                    note=note,
                    exercises=matched_exercises,
                ),
            )

            streak = await CheckinService.get_streak(db, user_id)

            return {
                "success": True,
                "checkin_id": str(checkin.id),
                "date": str(target_date),
                "exercises_count": len(matched_exercises),
                "duration_min": duration_min,
                "current_streak": streak["current_streak"],
                "message": f"打卡成功！已连续训练 {streak['current_streak']} 天 🔥",
            }
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
