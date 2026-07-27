"""
用户相关 Tools

供 Agent 调用，查询和更新用户个人资料：
- get_user_profile_tool: 获取用户身体数据和健身目标（数据库实时数据）
- update_user_profile_tool: 部分更新用户资料（身高、体重、年龄、性别、目标）

直接调用 UserService（同进程融合，不走 HTTP）。
"""

from typing import Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.database import async_session_factory
from src.fitme.schemas.user import UserUpdate
from src.fitme.services.user_service import UserService


def _calculate_bmi(height_cm: Optional[float], weight_kg: Optional[float]) -> Optional[float]:
    """计算 BMI"""
    if not height_cm or not weight_kg:
        return None
    height_m = height_cm / 100
    return round(weight_kg / (height_m**2), 1)


@tool
async def get_user_profile_tool(config: RunnableConfig) -> dict:
    """
    获取当前用户的个人资料和身体数据。

    当需要了解用户信息以提供个性化建议时调用。

    Returns:
        用户基本信息、身体数据、健身目标
    """
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_id")

    if not user_id:
        return {"success": False, "error": "无法获取用户信息（未登录或会话无效）"}

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


class UpdateUserProfileInput(BaseModel):
    """更新用户资料的输入参数"""

    name: Optional[str] = Field(default=None, description="昵称")
    height_cm: Optional[float] = Field(default=None, description="身高（厘米）")
    weight_kg: Optional[float] = Field(default=None, description="体重（公斤）")
    age: Optional[int] = Field(default=None, description="年龄")
    gender: Optional[str] = Field(
        default=None, description="性别：male(男)、female(女)、other(其他)"
    )
    goal: Optional[str] = Field(
        default=None,
        description=(
            "健身目标：lose_fat(减脂)、gain_muscle(增肌)、"
            "maintain(保持健康)、improve_health(改善体质)"
        ),
    )


@tool(args_schema=UpdateUserProfileInput)
async def update_user_profile_tool(
    name: Optional[str] = None,
    height_cm: Optional[float] = None,
    weight_kg: Optional[float] = None,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    goal: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    更新当前用户的个人资料和身体数据。

    使用场景：
    - 用户说"我身高175，体重70公斤"→ height_cm=175, weight_kg=70
    - 用户说"我今年25岁，男"→ age=25, gender="male"
    - 用户说"我的目标是减脂"→ goal="lose_fat"
    - 用户说"帮我改一下体重为68"→ weight_kg=68

    只更新传入的字段，未传入的字段保持不变。

    Returns:
        更新后的用户资料
    """
    configurable = config.get("configurable", {}) if config else {}
    user_id = configurable.get("user_id")

    if not user_id:
        return {"success": False, "error": "无法获取用户信息（未登录或会话无效）"}

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)

            update_data = UserUpdate(
                name=name,
                height_cm=height_cm,
                weight_kg=weight_kg,
                age=age,
                gender=gender,
                goal=goal,
            )

            user = await UserService.update_profile(db, uid, update_data)
            await db.commit()

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
                "message": "用户资料已更新。",
            }
        except Exception as e:
            await db.rollback()
            return {"success": False, "error": str(e)}
