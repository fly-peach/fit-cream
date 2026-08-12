"""
用户画像摘要工具

供 Agent 快速获取用户全貌（身体数据 + 计划 + 打卡 + 饮食），
激活条件/解读规则/缺字段引导写在 prompts/agent.md（L0 静态层）。

聚合来源：
- UserService.get_profile_summary（身体数据）
- PlanService.get_active_plan（活跃计划）
- CheckinService.get_streak（连续打卡）
- StatsService.get_weekly_stats（本周打卡天数）
- DietMealService.get_summary_with_goals（当日饮食）
"""

from datetime import date
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from src.agents.harness.tools._common import error_response, extract_user_id, session_scope


@tool
async def get_user_summary_tool(config: RunnableConfig) -> dict:
    """
    获取当前用户的完整画像摘要（身体数据 + 活跃计划 + 打卡 + 饮食）。

    使用场景：
    - 新建会话首次交互
    - 用户重新编辑资料/计划后
    - 询问进度状态时
    - 设计/调整计划或饮食前
    - 个性化问题缺上下文时

    返回 missing_fields 标记缺失的必要字段，profile_complete 标记资料是否完整。

    Returns:
        用户画像摘要（body/plan/streak/weekly_checkins/diet/missing_fields/profile_complete）
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            from src.fitme.services.checkin_service import CheckinService
            from src.fitme.services.diet_meal_service import DietMealService
            from src.fitme.services.plan_service import PlanService
            from src.fitme.services.stats_service import StatsService
            from src.fitme.services.user_service import UserService

            # 1. 身体数据（必需 -- 失败则整体失败；get_profile_summary 已把 birth_date 转为 ISO 字符串）
            profile = await UserService.get_profile_summary(db, user_id)

            # 2. 活跃计划（可选）
            plan_summary: Optional[dict] = None
            try:
                active_plan = await PlanService.get_active_plan(db, user_id)
                if active_plan:
                    plan_summary = {
                        "name": active_plan.name,
                        "goal": active_plan.goal,
                        "difficulty": active_plan.difficulty,
                        "weeks": active_plan.weeks,
                    }
            except Exception:
                pass

            # 3. 连续打卡（可选）
            streak: Optional[dict] = None
            try:
                raw_streak = await CheckinService.get_streak(db, user_id)
                if raw_streak:
                    streak = {
                        "current_streak": raw_streak.get("current_streak"),
                        "longest_streak": raw_streak.get("longest_streak"),
                        "last_checkin_date": (
                            raw_streak.get("last_checkin_date").isoformat()
                            if raw_streak.get("last_checkin_date")
                            else None
                        ),
                    }
            except Exception:
                pass

            # 4. 本周打卡天数（可选）
            weekly_checkins: Optional[int] = None
            try:
                weekly = await StatsService.get_weekly_stats(db, user_id)
                weekly_checkins = weekly.get("total_workouts")
            except Exception:
                pass

            # 5. 当日饮食（可选）
            diet: Optional[dict] = None
            try:
                diet = await DietMealService.get_summary_with_goals(
                    db, user_id, date.today()
                )
            except Exception:
                pass

            # 6. 缺失字段检测
            required_fields = ["height_cm", "weight_kg", "birth_date", "gender", "goal"]
            missing_fields = [
                f for f in required_fields if profile.get(f) is None
            ]
            profile_complete = len(missing_fields) == 0

            return {
                "success": True,
                "body": profile,
                "plan": plan_summary,
                "streak": streak,
                "weekly_checkins": weekly_checkins,
                "diet": diet,
                "missing_fields": missing_fields,
                "profile_complete": profile_complete,
            }
    except Exception as e:
        return error_response(e)
