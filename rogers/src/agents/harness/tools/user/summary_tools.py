"""
用户画像摘要工具

供 Agent 快速获取用户全貌（身体数据 + 计划 + 打卡 + 饮食 + 健身画像），
激活条件/解读规则/缺字段引导写在 prompts/agent.md（L0 静态层）。

聚合来源：
- UserService.get_profile_summary（身体数据）
- UserFitnessProfile（健身画像 / Intake 五维，只读不创建）
- PlanService.get_active_plan（活跃计划）
- CheckinService.get_streak（连续打卡）
- StatsService.get_weekly_stats（本周打卡天数）
- DietMealService.get_summary_with_goals（当日饮食）
"""

from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy import select

from src.agents.harness.tools._common import error_response, extract_user_id, session_scope
from src.fitme.models.user_fitness_profile import UserFitnessProfile
from utils.timeutil import today as tz_today

# 健身画像字段集合（与 user_fitness_profiles 表 / form-templates.ts 全链路统一命名）
FITNESS_INTAKE_FIELDS = [
    # health_safety
    "medical_history", "injuries", "allergies", "pregnancy", "medication",
    "parq_result", "doctor_advice",
    # fitness_level
    "training_experience", "cardio_level", "strength_level", "flexibility",
    "body_fat_pct",
    # exercise_history
    "weekly_frequency", "session_duration", "preferred_types", "past_results",
    # lifestyle
    "occupation_schedule", "diet_habits", "sleep_quality", "stress_level",
    "equipment", "preferred_time",
    # diet_profile
    "diet_preferences", "food_allergies", "cooking_condition", "meals_per_day",
    "eating_out_ratio", "budget",
]

# 各维度必填字段（完整度判定，与 form-templates.ts 的 required 一致）
FITNESS_INTAKE_DIMENSIONS = {
    "health_safety": ["medical_history", "injuries", "medication", "parq_result"],
    "fitness_level": ["training_experience", "cardio_level", "strength_level"],
    "exercise_history": ["weekly_frequency"],
    "lifestyle": ["sleep_quality", "stress_level", "equipment"],
    "diet_profile": ["diet_preferences", "meals_per_day"],
}


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

    返回 missing_fields 标记缺失的必要字段，profile_complete 标记资料是否完整；
    intake 返回健身画像（Intake 五维全字段），intake_dimensions 返回各维度完整度。

    Returns:
        用户画像摘要（body/plan/streak/weekly_checkins/diet/intake/intake_dimensions/missing_fields/profile_complete）
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
                    db, user_id, tz_today()
                )
            except Exception:
                pass

            # 6. 缺失字段检测
            required_fields = ["height_cm", "weight_kg", "birth_date", "gender", "goal"]
            missing_fields = [
                f for f in required_fields if profile.get(f) is None
            ]
            profile_complete = len(missing_fields) == 0

            # 7. 健身画像（Intake 五维，只读不创建：不存在时返回全 None + 全 missing）
            fp_result = await db.execute(
                select(UserFitnessProfile).where(UserFitnessProfile.user_id == user_id)
            )
            fp = fp_result.scalar_one_or_none()
            intake = (
                {f: getattr(fp, f) for f in FITNESS_INTAKE_FIELDS}
                if fp
                else {f: None for f in FITNESS_INTAKE_FIELDS}
            )
            if intake.get("body_fat_pct") is not None:
                intake["body_fat_pct"] = float(intake["body_fat_pct"])
            intake_dimensions = {}
            for dim, fields in FITNESS_INTAKE_DIMENSIONS.items():
                missing = [f for f in fields if intake.get(f) is None]
                intake_dimensions[dim] = {
                    "complete": len(missing) == 0,
                    "missing": missing,
                }

            return {
                "success": True,
                "body": profile,
                "plan": plan_summary,
                "streak": streak,
                "weekly_checkins": weekly_checkins,
                "diet": diet,
                "intake": intake,
                "intake_dimensions": intake_dimensions,
                "missing_fields": missing_fields,
                "profile_complete": profile_complete,
            }
    except Exception as e:
        return error_response(e)
