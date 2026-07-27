"""
动作库路由 /api/exercises/*

提供健身动作的查询端点。
所有端点需要 JWT 认证（Bearer Token）。
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel
from src.fitme.services.exercise_service import ExerciseService
from utils.exceptions import NotFoundException

router = APIRouter(prefix="/exercises", tags=["exercises"])


class ExerciseOut(BaseModel):
    """动作输出"""

    id: UUID
    name: str
    name_en: Optional[str] = None
    muscle_group: Optional[str] = None
    equipment: Optional[str] = None
    difficulty: Optional[str] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("", response_model=ResponseModel[list[ExerciseOut]])
async def list_exercises(
    muscle_group: Optional[str] = Query(
        None,
        description="肌群筛选: chest/back/legs/shoulders/arms/core/full_body",
    ),
    equipment: Optional[str] = Query(
        None,
        description="器械筛选: barbell/dumbbell/machine/bodyweight/cable/kettlebell",
    ),
    difficulty: Optional[str] = Query(
        None,
        description="难度筛选: beginner/intermediate/advanced",
    ),
    keyword: Optional[str] = Query(None, description="关键词搜索（匹配名称或描述）"),
    limit: int = Query(20, ge=1, le=100, description="返回数量上限"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询动作库（支持多条件筛选）"""
    exercises = await ExerciseService.search(
        db,
        muscle_group=muscle_group,
        equipment=equipment,
        keyword=keyword,
        difficulty=difficulty,
        limit=limit,
    )
    return ResponseModel(data=[ExerciseOut.model_validate(e) for e in exercises])


@router.get("/{exercise_id}", response_model=ResponseModel[ExerciseOut])
async def get_exercise(
    exercise_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取动作详情"""
    exercise = await ExerciseService.get_by_id(db, exercise_id)
    if not exercise:
        raise NotFoundException("动作不存在")
    return ResponseModel(data=ExerciseOut.model_validate(exercise))