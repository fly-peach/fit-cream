"""
独立心情记录路由 /api/moods/*

提供独立心情记录的查询与 upsert 端点。
所有端点需要 JWT 认证（Bearer Token）。
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel
from src.fitme.schemas.mood import MoodOut, MoodUpsert
from src.fitme.services.mood_service import MoodService

router = APIRouter(prefix="/moods", tags=["moods"])


@router.get("", response_model=ResponseModel[list[MoodOut]], operation_id="list_moods")
async def list_moods(
    start: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取独立心情记录（按日期升序）"""
    moods = await MoodService.list_by_range(db, user.id, start=start, end=end)
    return ResponseModel(data=[MoodOut.model_validate(m) for m in moods])


@router.put("", response_model=ResponseModel[MoodOut], operation_id="upsert_mood")
async def upsert_mood(
    data: MoodUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录/更新心情（按日期 upsert，同日覆盖）"""
    mood = await MoodService.upsert(db, user.id, data)
    await db.commit()
    await db.refresh(mood)
    return ResponseModel(data=MoodOut.model_validate(mood))
