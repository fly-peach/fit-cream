"""
成就系统路由 /api/achievements/*

提供用户成就徽章的查询端点。
所有端点需要 JWT 认证（Bearer Token）。
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.achievement import Achievement
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel

router = APIRouter(prefix="/achievements", tags=["achievements"])

# 成就类型定义
ACHIEVEMENT_DEFINITIONS = {
    "streak_7": {"name": "坚持一周", "description": "连续打卡 7 天", "icon": "🔥"},
    "streak_30": {"name": "月度达人", "description": "连续打卡 30 天", "icon": "💪"},
    "streak_100": {"name": "百日坚持", "description": "连续打卡 100 天", "icon": "🏆"},
    "first_plan": {"name": "初次规划", "description": "首次创建训练计划", "icon": "📋"},
    "total_50_workouts": {"name": "半百训练", "description": "累计完成 50 次训练", "icon": "⭐"},
    "total_100_workouts": {"name": "百炼成钢", "description": "累计完成 100 次训练", "icon": "🌟"},
}


class AchievementOut(BaseModel):
    """已解锁成就输出"""

    id: UUID
    type: str
    name: str
    description: str
    icon: str
    unlocked_at: datetime

    model_config = {"from_attributes": True}


class AchievementProgressOut(BaseModel):
    """成就进度输出"""

    type: str
    name: str
    description: str
    icon: str
    unlocked: bool
    unlocked_at: Optional[datetime] = None


@router.get("", response_model=ResponseModel[List[AchievementOut]])
async def list_achievements(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户已解锁的成就列表"""
    result = await db.execute(
        select(Achievement)
        .where(Achievement.user_id == user.id)
        .order_by(Achievement.unlocked_at.desc())
    )
    achievements = list(result.scalars().all())

    data = []
    for a in achievements:
        defn = ACHIEVEMENT_DEFINITIONS.get(a.type, {})
        data.append(
            AchievementOut(
                id=a.id,
                type=a.type,
                name=defn.get("name", a.type),
                description=defn.get("description", ""),
                icon=defn.get("icon", "🎖️"),
                unlocked_at=a.unlocked_at,
            )
        )

    return ResponseModel(data=data)


@router.get("/all", response_model=ResponseModel[List[AchievementProgressOut]])
async def list_all_achievements(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有成就及解锁状态"""
    # 查询用户已解锁的成就
    result = await db.execute(
        select(Achievement).where(Achievement.user_id == user.id)
    )
    unlocked = {a.type: a for a in result.scalars().all()}

    data = []
    for ach_type, defn in ACHIEVEMENT_DEFINITIONS.items():
        ach = unlocked.get(ach_type)
        data.append(
            AchievementProgressOut(
                type=ach_type,
                name=defn["name"],
                description=defn["description"],
                icon=defn["icon"],
                unlocked=ach is not None,
                unlocked_at=ach.unlocked_at if ach else None,
            )
        )

    return ResponseModel(data=data)