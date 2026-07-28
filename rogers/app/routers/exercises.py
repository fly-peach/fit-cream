"""动作库路由 /api/exercises/*"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel
from src.fitme.schemas.exercise import (
    CategoryStats,
    ExerciseCreate,
    ExerciseOut,
    ExerciseUpdate,
    MuscleGroupStats,
)
from src.fitme.services.exercise_service import ExerciseService
from utils.exceptions import NotFoundException

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=ResponseModel[list[ExerciseOut]])
async def list_exercises(
    muscle_group: Optional[str] = Query(None),
    equipment: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exercises = await ExerciseService.search(
        db,
        muscle_group=muscle_group,
        equipment=equipment,
        keyword=keyword,
        difficulty=difficulty,
        category=category,
        limit=limit,
        offset=offset,
    )
    total = await ExerciseService.count(
        db,
        muscle_group=muscle_group,
        equipment=equipment,
        difficulty=difficulty,
        category=category,
        keyword=keyword,
    )
    return ResponseModel(data=[ExerciseOut.model_validate(e) for e in exercises],
                         message=f"共 {total} 个动作")


@router.get("/categories", response_model=ResponseModel[list[CategoryStats]])
async def list_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await ExerciseService.list_categories(db)
    return ResponseModel(data=[CategoryStats(**d) for d in data])


@router.get("/muscle-groups", response_model=ResponseModel[list[MuscleGroupStats]])
async def list_muscle_groups(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await ExerciseService.list_muscle_groups(db)
    return ResponseModel(data=[MuscleGroupStats(**d) for d in data])


@router.get("/{exercise_id}", response_model=ResponseModel[ExerciseOut])
async def get_exercise(
    exercise_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exercise = await ExerciseService.get_by_id(db, exercise_id)
    if not exercise:
        raise NotFoundException("动作不存在")
    return ResponseModel(data=ExerciseOut.model_validate(exercise))


@router.post("", response_model=ResponseModel[ExerciseOut])
async def create_exercise(
    data: ExerciseCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    exercise = await ExerciseService.create_exercise(
        db, data.model_dump()
    )
    await db.commit()
    await db.refresh(exercise)
    return ResponseModel(data=ExerciseOut.model_validate(exercise))


@router.put("/{exercise_id}", response_model=ResponseModel[ExerciseOut])
async def update_exercise(
    exercise_id: UUID,
    data: ExerciseUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    exercise = await ExerciseService.update_exercise(
        db, exercise_id, data.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ResponseModel(data=ExerciseOut.model_validate(exercise))


@router.delete("/{exercise_id}", response_model=ResponseModel[None])
async def delete_exercise(
    exercise_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    await ExerciseService.delete_exercise(db, exercise_id)
    await db.commit()
    return ResponseModel(message="动作已删除")
