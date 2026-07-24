"""
统计相关 Tools

供 Agent 调用，查询多维度训练统计数据：
- query_stats_tool: 按周期（周/月/全部/体重）查询统计，返回结构化数据 + 自然语言分析

直接调用 StatsService（同进程融合，不走 HTTP）。
"""

from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.database import async_session_factory
from app.services.stats_service import StatsService


class QueryStatsInput(BaseModel):
    """查询统计的输入参数"""

    period: str = Field(
        default="weekly",
        description="查询周期: weekly(本周) / monthly(本月) / all(全部)",
    )
    metric: Optional[str] = Field(
        default=None,
        description="关注指标: workouts(训练次数) / duration(时长) / body(体重)",
    )


@tool(args_schema=QueryStatsInput)
async def query_stats_tool(
    period: str = "weekly",
    metric: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    查询训练统计数据。

    当用户问"这周练得怎么样"、"看看我的进度"、"统计一下"等时调用。

    Args:
        period: 查询周期 - weekly（本周）/ monthly（本月）/ all（全部）
        metric: 关注的指标 - workouts（训练次数）/ duration（时长）/ body（体重）

    Returns:
        统计数据和自然语言分析
    """
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "无法获取用户信息"}

    async with async_session_factory() as db:
        if period == "weekly":
            stats = await StatsService.get_weekly_stats(db, user_id)
            analysis = _generate_weekly_analysis(stats)
        elif period == "monthly":
            stats = await StatsService.get_monthly_trend(db, user_id)
            analysis = _generate_monthly_analysis(stats)
        elif period == "body":
            stats = await StatsService.get_body_trend(db, user_id)
            analysis = _generate_body_analysis(stats)
        else:
            stats = await StatsService.get_all_stats(db, user_id)
            analysis = _generate_all_analysis(stats)

        return {
            "success": True,
            "period": period,
            "stats": stats,
            "analysis": analysis,
        }


def _generate_weekly_analysis(stats: dict) -> str:
    """生成周分析文本"""
    workouts = stats.get("total_workouts", 0)
    duration = stats.get("total_duration_min", 0)

    if workouts == 0:
        return "本周还没有训练记录，开始今天的训练吧！💪"

    analysis = f"本周已完成 {workouts} 次训练，总时长 {duration} 分钟。"

    if workouts >= 4:
        analysis += "训练频率很棒，继续保持！🔥"
    elif workouts >= 2:
        analysis += "不错的开始，可以尝试增加训练频率。"
    else:
        analysis += "本周训练较少，建议每周至少训练 3 次。"

    return analysis


def _generate_monthly_analysis(stats: dict) -> str:
    """生成月分析文本"""
    workouts = stats.get("total_workouts", 0)
    duration = stats.get("total_duration_min", 0)
    avg_mood = stats.get("average_mood")

    analysis = f"本月已完成 {workouts} 次训练，总时长 {duration} 分钟。"

    if avg_mood:
        analysis += f" 平均心情评分 {avg_mood}/5。"

    if workouts >= 16:
        analysis += "训练非常规律，太棒了！🏆"
    elif workouts >= 8:
        analysis += "保持得不错，继续加油！"
    else:
        analysis += "训练频率可以提高，建议每周 3-4 次。"

    return analysis


def _generate_body_analysis(stats: dict) -> str:
    """生成体重分析文本"""
    weight = stats.get("current_weight_kg")
    height = stats.get("height_cm")
    goal = stats.get("goal")

    if not weight:
        return "还没有记录体重数据，可以在个人资料中更新。"

    analysis = f"当前体重 {weight}kg"

    if height:
        bmi = weight / ((height / 100) ** 2)
        analysis += f"，BMI {bmi:.1f}"

        if bmi < 18.5:
            analysis += "（偏瘦）"
        elif bmi < 24:
            analysis += "（正常）"
        elif bmi < 28:
            analysis += "（偏胖）"
        else:
            analysis += "（肥胖）"

    if goal:
        goal_map = {
            "lose_fat": "减脂",
            "gain_muscle": "增肌",
            "maintain": "维持",
            "improve_health": "健康",
        }
        analysis += f"。目标是{goal_map.get(goal, goal)}。"

    return analysis


def _generate_all_analysis(stats: dict) -> str:
    """生成全部统计分析文本"""
    total = stats.get("total_workouts", 0)
    duration = stats.get("total_duration_min", 0)
    streak = stats.get("current_streak", 0)
    longest = stats.get("longest_streak", 0)

    analysis = f"累计训练 {total} 次，总时长 {duration} 分钟。"
    analysis += f" 当前连续 {streak} 天，最长连续 {longest} 天。"

    if total >= 100:
        analysis += " 已经是训练达人了！🏆"
    elif total >= 50:
        analysis += " 训练习惯已经养成，继续保持！"
    elif total >= 10:
        analysis += " 正在养成训练习惯，加油！"

    return analysis