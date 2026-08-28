"""
目标闯关知识层路由 /api/goal-knowledge/*

- GET /goal-knowledge：身材原型目录（按用户性别过滤）+ 力量标准表（按体重换算 kg）+ 当前体重。
  供前端训练计划页「身材与力量」tab 展示：每种身材的达成目标与所需重量统计。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel
from src.fitme.services.goal_service import GoalKnowledgeService
from src.fitme.services.user_service import UserService

router = APIRouter(prefix="/goal-knowledge", tags=["goal-knowledge"])


@router.get("", response_model=ResponseModel[dict], operation_id="get_goal_knowledge")
async def get_goal_knowledge(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取身材原型目录 + 力量标准（按用户体重换算 kg）+ 当前体重/性别。"""
    gender = (user.gender or "male").lower()
    if gender not in ("male", "female"):
        gender = "male"

    body = await UserService.get_body_summary(db, user.id)
    weight = body.get("weight_kg")

    archetypes = await GoalKnowledgeService.get_archetypes(db, gender)
    standards = await GoalKnowledgeService.get_strength_standards(db, gender, weight)

    return ResponseModel(
        data={
            "gender": gender,
            "bodyweight_kg": weight,
            "archetypes": archetypes,
            "strength_standards": standards,
        }
    )
