"""动作库路由 /api/exercises/*"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user, get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import PaginatedResponse, ResponseModel
from src.fitme.schemas.exercise import (
    CategoryStats,
    EquipmentStats,
    ExerciseCreate,
    ExerciseOut,
    ExerciseUpdate,
    MuscleGroupStats,
)
from src.fitme.services.exercise_service import ExerciseService
from utils.exceptions import NotFoundException

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=ResponseModel[list[ExerciseOut]], operation_id="list_exercises")
async def list_exercises(
    muscle_group: Optional[str] = Query(None),
    equipment: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    body_part: Optional[str] = Query(None),
    target: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exercises, total = await ExerciseService.search_with_count(
        db,
        muscle_group=muscle_group,
        equipment=equipment,
        keyword=keyword,
        difficulty=difficulty,
        category=category,
        body_part=body_part,
        target=target,
        limit=limit,
        offset=offset,
    )
    return ResponseModel(data=[ExerciseOut.model_validate(e) for e in exercises],
                         message=f"共 {total} 个动作")


@router.get("/categories", response_model=ResponseModel[list[CategoryStats]], operation_id="list_exercise_categories")
async def list_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await ExerciseService.list_categories(db)
    return ResponseModel(data=[CategoryStats(**d) for d in data])


@router.get("/muscle-groups", response_model=ResponseModel[list[MuscleGroupStats]], operation_id="list_exercise_muscle_groups")
async def list_muscle_groups(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await ExerciseService.list_muscle_groups(db)
    return ResponseModel(data=[MuscleGroupStats(**d) for d in data])


@router.get("/equipments", response_model=ResponseModel[list[EquipmentStats]], operation_id="list_exercise_equipments")
async def list_equipments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按器械分组统计（dataset 含 28 种器械值，前端筛选取动态值）。"""
    data = await ExerciseService.list_equipments(db)
    return ResponseModel(data=[EquipmentStats(**d) for d in data])


@router.get("/favorites/list", response_model=ResponseModel[PaginatedResponse[ExerciseOut]], operation_id="list_exercise_favorites")
async def list_exercise_favorites(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户收藏的动作列表"""
    offset = (page - 1) * size
    items, total = await ExerciseService.list_favorites(db, user.id, limit=size, offset=offset)
    return ResponseModel(data=PaginatedResponse(
        items=[ExerciseOut.model_validate(e) for e in items],
        total=total,
        page=page,
        size=size,
    ))


@router.get("/favorites/ids", response_model=ResponseModel[list[str]], operation_id="get_exercise_favorite_ids")
async def get_exercise_favorite_ids(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户收藏的动作 ID 集合（用于前端批量标记）"""
    ids = await ExerciseService.get_favorite_ids(db, user.id)
    return ResponseModel(data=[str(i) for i in ids])


@router.get("/{exercise_id}", response_model=ResponseModel[ExerciseOut], operation_id="get_exercise")
async def get_exercise(
    exercise_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exercise = await ExerciseService.get_by_id(db, exercise_id)
    if not exercise:
        raise NotFoundException("动作不存在")
    return ResponseModel(data=ExerciseOut.model_validate(exercise))


@router.post("", response_model=ResponseModel[ExerciseOut], operation_id="create_exercise")
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


@router.put("/{exercise_id}", response_model=ResponseModel[ExerciseOut], operation_id="update_exercise")
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


@router.delete("/{exercise_id}", response_model=ResponseModel[None], operation_id="delete_exercise")
async def delete_exercise(
    exercise_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    await ExerciseService.delete_exercise(db, exercise_id)
    await db.commit()
    return ResponseModel(message="动作已删除")


@router.post("/{exercise_id}/favorite", response_model=ResponseModel[dict], operation_id="toggle_exercise_favorite")
async def toggle_exercise_favorite(
    exercise_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """收藏/取消收藏动作（toggle）"""
    exercise = await ExerciseService.get_by_id(db, exercise_id)
    if not exercise:
        raise NotFoundException("动作不存在")
    is_favorited = await ExerciseService.toggle_favorite(db, user.id, exercise_id)
    return ResponseModel(
        data={"favorited": is_favorited},
        message="已收藏" if is_favorited else "已取消收藏",
    )
