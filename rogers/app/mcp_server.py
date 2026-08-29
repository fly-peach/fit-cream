"""
fastapi-mcp 集成（2 端点）

- /mcp/user   用户 MCP（健身全域 + 知识库用户态，认证: 用户 API Key）
- /mcp/admin  知识库管理 MCP（认证: 管理员 JWT）

外部接入：
1. 在 App 个人中心创建用户 API Key（一人一把，明文仅返回一次）。
2. MCP 客户端配置 HTTP transport，url 指向 /mcp/user，
   headers.Authorization = "Bearer <key>"。
3. 响应包了 ResponseModel 外壳（{code, message, data}），client 需剥一层取 data。

排除项：exercises 写端点（curated 数据）不纳入 MCP；API Key 管理路由不纳入 MCP。
JWT 仅服务 App，MCP 约定使用用户 API Key（服务端因共享路由仍接受 JWT）。
"""
import logging

from fastapi import FastAPI

from fastapi_mcp import FastApiMCP

from app.config import settings

logger = logging.getLogger("fitcream")

FITME_OPERATIONS = [
    # plans
    "list_plans",
    "get_active_plan",
    "get_plan",
    "create_plan",
    "update_plan",
    "delete_plan",
    "add_plan_day",
    "update_plan_day",
    "delete_plan_day",
    "add_plan_exercise",
    "update_plan_exercise",
    "delete_plan_exercise",
    # diet plans
    "list_diet_plans",
    "get_active_diet_plan",
    "get_diet_plan",
    "create_diet_plan",
    "update_diet_plan",
    "delete_diet_plan",
    "add_diet_day",
    "update_diet_day",
    "add_diet_plan_meal",
    "update_diet_plan_meal",
    "delete_diet_plan_meal",
    # diet meals
    "list_meals",
    "get_meal",
    "get_daily_summary",
    "list_daily_summaries",
    "list_custom_foods",
    "create_meal",
    "batch_create_meals",
    "update_meal",
    "delete_meal",
    "create_custom_food",
    "update_custom_food",
    "delete_custom_food",
    # checkins
    "list_checkins",
    "get_checkin",
    "get_streak",
    "create_checkin",
    "update_checkin",
    "delete_checkin",
    # stats
    "get_weekly_stats",
    "get_monthly_stats",
    "get_body_stats",
    "get_overview_stats",
    "get_diet_trend",
    # goal roadmap / knowledge（只读 + 出关判定）
    "get_goal_roadmap",
    "check_goal_roadmap",
    "get_goal_knowledge",
    # exercises（仅读，写端点为 curated 数据不暴露）
    "list_exercises",
    "get_exercise",
    "list_exercise_categories",
    "list_exercise_muscle_groups",
    "list_exercise_equipments",
    # users
    "get_me",
    "update_me",
    "get_settings",
    "update_settings",
    "list_health_metrics",
    "get_latest_health_metric",
    "get_health_metric",
    "create_health_metric",
    "update_health_metric",
    "delete_health_metric",
]

KB_USER_OPERATIONS = [
    "list_knowledge_bases",
    "list_my_subscriptions",
    "get_knowledge_base",
    "list_documents",
    "get_document",
    "read_document",
    "search_documents",
    "get_graph",
    "get_document_references",
    "subscribe_kb",
    "unsubscribe_kb",
]

KB_ADMIN_EXTRA_OPERATIONS = [
    "create_knowledge_base",
    "update_knowledge_base",
    "delete_knowledge_base",
    "create_document",
    "update_document_content",
    "update_document_metadata",
    "delete_document",
    "reindex_knowledge_base",
    "rebuild_graph",
    "lint_knowledge_base",
    "rebuild_lint",
    "list_subscribers",
    "remove_subscriber",
]

KB_ADMIN_OPERATIONS = KB_USER_OPERATIONS + KB_ADMIN_EXTRA_OPERATIONS

USER_MCP_OPERATIONS = FITME_OPERATIONS + KB_USER_OPERATIONS


def _mount(app: FastAPI, name: str, description: str, operations: list[str], mount_path: str) -> None:
    try:
        FastApiMCP(
            app,
            name=name,
            description=description,
            include_operations=operations,
        ).mount_http(mount_path=mount_path)
        logger.info("MCP 已挂载: %s (%d operations)", mount_path, len(operations))
    except Exception as e:
        logger.error("MCP 挂载失败 %s: %s", mount_path, e)


def setup_mcp(app: FastAPI) -> None:
    _mount(
        app,
        "FitCream MCP",
        "健身+知识库用户态 MCP（用户 API Key）",
        USER_MCP_OPERATIONS,
        settings.MCP_USER_MOUNT_PATH,
    )
    _mount(
        app,
        "FitCream KB Admin",
        "知识库管理 MCP（管理员 JWT）",
        KB_ADMIN_OPERATIONS,
        settings.MCP_ADMIN_MOUNT_PATH,
    )
