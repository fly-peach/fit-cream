"""
FitCream Agent Tools

导出所有 LangChain Tools，供 Agent 调用。
每个 Tool 直接调用 Service 层函数（同进程融合，不走 HTTP）。

工具列表：
- create_plan_tool: 创建训练计划
- adjust_plan_tool: 调整现有计划
- checkin_tool: 记录训练打卡
- query_stats_tool: 查询统计数据
- get_exercises_tool: 查询动作库
- get_user_profile_tool: 获取用户信息
"""

from agents.harness.tools.plan_tools import create_plan_tool, adjust_plan_tool
from agents.harness.tools.checkin_tools import checkin_tool
from agents.harness.tools.stats_tools import query_stats_tool
from agents.harness.tools.exercise_tools import get_exercises_tool
from agents.harness.tools.user_tools import get_user_profile_tool

__all__ = [
    "create_plan_tool",
    "adjust_plan_tool",
    "checkin_tool",
    "query_stats_tool",
    "get_exercises_tool",
    "get_user_profile_tool",
]
