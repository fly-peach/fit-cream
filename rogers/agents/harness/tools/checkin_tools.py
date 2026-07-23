"""打卡相关 Tools"""

from datetime import date as date_type
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.database import async_session_factory
from app.schemas.checkin import CheckinCreate, CheckinExerciseCreate
from app.services.checkin_service import CheckinService
from app.services.exercise_service import ExerciseService


class ExerciseRecord(BaseModel):
    """单个动作的打卡记录"""

    name: str = Field(description="动作名称")
    sets_done: int = Field(ge=1, description="完成组数")
    reps_done: int = Field(ge=1, description="每组次数")
    weight_kg: Optional[float] = Field(default=None, description="重量（kg）")


class CheckinInput(BaseModel):
    """打卡输入参数"""

    exercises: List[ExerciseRecord] = Field(description="完成的动作列表")
    duration_min: int = Field(ge=1, description="训练时长（分钟）")
    mood: Optional[int] = Field(default=None, ge=1, le=5, description="心情评分 1-5")
    note: Optional[str] = Field(default=None, description="备注")
    checkin_date: Optional[str] = Field(
        default=None, description="打卡日期 YYYY-MM-DD，默认今天"
    )


@tool(args_schema=CheckinInput)
async def checkin_tool(
    exercises: List[dict],
    duration_min: int,
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
    # 从 config 获取 user_id
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "无法获取用户信息"}

    async with async_session_factory() as db:
        try:
            # 解析日期
            target_date = (
                date_type.fromisoformat(checkin_date)
                if checkin_date
                else date_type.today()
            )

            # 匹配动作名称到动作库
            matched_exercises = []
            for ex in exercises:
                exercise = await ExerciseService.search_by_name(db, ex["name"])
                if exercise:
                    matched_exercises.append(
                        CheckinExerciseCreate(
                            exercise_id=exercise.id,
                            sets_done=ex["sets_done"],
                            reps_done=ex["reps_done"],
                            weight_kg=ex.get("weight_kg"),
                        )
                    )

            # 创建打卡记录
            checkin_data = CheckinCreate(
                date=target_date,
                plan_day_id=None,
                duration_min=duration_min,
                mood=mood,
                note=note,
                exercises=matched_exercises,
            )

            checkin = await CheckinService.create_checkin(
                db=db,
                user_id=user_id,
                data=checkin_data,
            )

            # 获取连续打卡天数
            streak = await CheckinService.get_streak(db, user_id)

            await db.commit()

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
            await db.rollback()
            return {"success": False, "error": str(e)}


@tool
async def get_streak_tool(config: "RunnableConfig" = None) -> dict:  # type: ignore[assignment]
    """
    获取当前用户的连续打卡天数统计。

    当用户问"我连续练了几天"、"打卡天数"等时调用。

    Returns:
        当前连续天数、最长连续天数、最后打卡日期
    """
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "无法获取用户信息"}

    async with async_session_factory() as db:
        streak = await CheckinService.get_streak(db, user_id)

        return {
            "success": True,
            "current_streak": streak["current_streak"],
            "longest_streak": streak["longest_streak"],
            "last_checkin_date": str(streak["last_checkin_date"])
            if streak["last_checkin_date"]
            else None,
        }