"""
FitCream Agent Tools

导出所有 LangChain Tools，供 Agent 调用。
每个 Tool 直接调用 Service 层函数（同进程融合，不走 HTTP）。

工具列表：
- create_plan_tool: 创建训练计划
- create_diet_plan_tool: 创建饮食计划
- adjust_plan_tool: 调整现有计划
- list_plans_tool: 查看计划列表
- checkin_tool: 记录训练打卡
- get_streak_tool: 查询连续打卡天数
- query_stats_tool: 查询统计数据
- get_exercises_tool: 查询动作库
- get_user_profile_tool: 获取用户信息
- update_user_profile_tool: 更新用户资料

记忆工具（由 memory/tools.py 单独导出）：
- recall_memory / save_preference / save_user_fact / list_user_profile / save_event
"""

from src.agents.harness.tools.plan_tools import create_plan_tool, create_diet_plan_tool, adjust_plan_tool, list_plans_tool
from src.agents.harness.tools.checkin_tools import checkin_tool, get_streak_tool
from src.agents.harness.tools.stats_tools import query_stats_tool
from src.agents.harness.tools.exercise_tools import get_exercises_tool
from src.agents.harness.tools.user_tools import get_user_profile_tool, update_user_profile_tool
from src.agents.harness.tools.knowledge_tools import search_knowledge_base, read_kb_document

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
]
