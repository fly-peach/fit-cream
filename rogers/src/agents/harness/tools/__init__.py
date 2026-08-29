"""
FitCream Agent Tools

导出所有 LangChain Tools，供 Agent 调用。
每个 Tool 直接调用 Service 层函数（同进程融合，不走 HTTP）。

目录结构（按业务域分包）：
- plan/      计划类（create_plan / create_diet_plan / list_plans / get_plan_detail / update_plan / delete_plan / add_plan_day / remove_plan_day / add_exercise / update_exercise / remove_exercise / present_plan / present_form）
- training/  训练类（checkin / get_streak / get_exercises / query_stats）
- diet/      饮食类（record_meal / query_diet_summary / manage_meal / set_nutrition_goals）
- user/      用户类（get_user_profile / update_user_profile / update_fitness_profile /
             get_user_summary）
- knowledge/ 知识库（search_knowledge_base / read_kb_document / list_my_knowledge_bases）
- memory/    记忆工具（create_memory_tools：recall_memory / save_preference / save_user_fact / list_user_profile / save_event）
- skill/     技能加载（skill_load_tool）
"""

from src.agents.harness.tools.plan import (
    add_exercise_tool,
    add_plan_day_tool,
    create_diet_plan_tool,
    create_plan_tool,
    delete_plan_tool,
    get_plan_detail_tool,
    list_plans_tool,
    present_plan_tool,
    present_form_tool,
    present_plan_queue_tool,
    present_outline_tool,
    present_day_design_tool,
    update_plan_queue_item_tool,
    remove_exercise_tool,
    remove_plan_day_tool,
    sync_plan_day_tool,
    update_exercise_tool,
    update_plan_tool,
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
    update_fitness_profile_tool,
    update_user_profile_tool,
    get_user_summary_tool,
)
from src.agents.harness.tools.knowledge import (
    list_my_knowledge_bases,
    read_kb_document,
    search_knowledge_base,
)
from src.agents.harness.tools.skill import skill_load_tool
from src.agents.harness.tools.goal import (
    check_milestone_tool,
    create_roadmap_tool,
    get_goal_knowledge_tool,
    get_roadmap_tool,
    present_roadmap_tool,
    record_baseline_tool,
)

__all__ = [
    "create_plan_tool",
    "create_diet_plan_tool",
    "list_plans_tool",
    "get_plan_detail_tool",
    "update_plan_tool",
    "delete_plan_tool",
    "add_plan_day_tool",
    "remove_plan_day_tool",
    "sync_plan_day_tool",
    "add_exercise_tool",
    "update_exercise_tool",
    "remove_exercise_tool",
    "checkin_tool",
    "get_streak_tool",
    "query_stats_tool",
    "get_exercises_tool",
    "get_user_profile_tool",
    "update_user_profile_tool",
    "update_fitness_profile_tool",
    "search_knowledge_base",
    "read_kb_document",
    "list_my_knowledge_bases",
    "record_meal_tool",
    "query_diet_summary_tool",
    "manage_meal_tool",
    "set_nutrition_goals_tool",
    "skill_load_tool",
    "get_user_summary_tool",
    "present_plan_tool",
    "present_form_tool",
    "present_plan_queue_tool",
    "present_outline_tool",
    "present_day_design_tool",
    "update_plan_queue_item_tool",
    "get_goal_knowledge_tool",
    "present_roadmap_tool",
    "create_roadmap_tool",
    "get_roadmap_tool",
    "record_baseline_tool",
    "check_milestone_tool",
]
