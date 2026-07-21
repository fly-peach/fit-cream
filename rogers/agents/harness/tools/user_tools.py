"""用户相关 Tools"""

from typing import Optional

from langchain_core.tools import tool

from app.database import async_session_factory
from app.services.user_service import UserService


def _calculate_bmi(height_cm: Optional[float], weight_kg: Optional[float]) -> Optional[float]:
    """计算 BMI"""
    if not height_cm or not weight_kg:
        return None
    height_m = height_cm / 100
    return round(weight_kg / (height_m**2), 1)


@tool
async def get_user_profile_tool(config: Optional[dict] = None) -> dict:
    """
    获取当前用户的个人资料和身体数据。

    当需要了解用户信息以提供个性化建议时调用。

    Returns:
        用户基本信息、身体数据、健身目标
    """
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "无法获取用户信息"}

    async with async_session_factory() as db:
        user = await UserService.get_by_id(db, user_id)

        if not user:
            return {"success": False, "error": "用户不存在"}

        height = float(user.height_cm) if user.height_cm else None
        weight = float(user.weight_kg) if user.weight_kg else None

        return {
            "success": True,
            "profile": {
                "name": user.name,
                "height_cm": height,
                "weight_kg": weight,
                "age": user.age,
                "gender": user.gender,
                "goal": user.goal,
                "bmi": _calculate_bmi(height, weight),
            },
        }