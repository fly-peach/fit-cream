"""
FitCream Agent Tools

导出所有 LangChain Tools，供 Agent 调用。
每个 Tool 直接调用 Service 层函数（同进程融合，不走 HTTP）。

目录结构（按业务域分包）：
- plan/      计划类（create_plan / create_diet_plan / adjust_plan / list_plans / present_plan）
- training/  训练类（checkin / get_streak / get_exercises / query_stats）
- diet/      饮食类（record_meal / query_diet_summary / manage_meal / set_nutrition_goals）
- user/      用户类（get_user_profile / update_user_profile / get_user_summary）
- knowledge/ 知识库（search_knowledge_base / read_kb_document）
- memory/    记忆工具（create_memory_tools：recall_memory / save_preference / save_user_fact / list_user_profile / save_event）
- skill/     技能加载（skill_load_tool）
"""

from src.agents.harness.tools.plan import (
    create_plan_tool,
    create_diet_plan_tool,
    adjust_plan_tool,
    list_plans_tool,
    present_plan_tool,
)
from src.agents.harness.tools.training import (
    checkin_tool,
    get_streak_tool,
    get_exercises_tool,
    query_stats_tool,
)
from src.agents.harness.tools.diet import (
    record_meal_tool,
    query_diet_summary_tool,
    manage_meal_tool,
    set_nutrition_goals_tool,
)
from src.agents.harness.tools.user import (
    get_user_profile_tool,
    update_user_profile_tool,
    get_user_summary_tool,
)
from src.agents.harness.tools.knowledge import search_knowledge_base, read_kb_document
from src.agents.harness.tools.skill import skill_load_tool

__all__ = [
    "create_plan_tool",
    "create_diet_plan_tool",
    "adjust_plan_tool",
    "list_plans_tool",
    "checkin_tool",
    "get_streak_tool",
    "query_stats_tool",
    "get_exercises_tool",
    "get_user_profile_tool",
    "update_user_profile_tool",
    "search_knowledge_base",
    "read_kb_document",
    "record_meal_tool",
    "query_diet_summary_tool",
    "manage_meal_tool",
    "set_nutrition_goals_tool",
    "skill_load_tool",
    "get_user_summary_tool",
    "present_plan_tool",
]
