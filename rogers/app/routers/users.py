"""
用户路由 /api/users/*

提供当前用户信息查询和资料更新端点。
所有端点需要 JWT 认证（Bearer Token）。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel
from src.fitme.schemas.user import UserOut, UserUpdate
from src.fitme.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ResponseModel[UserOut])
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return ResponseModel(data=UserOut.model_validate(current_user))


@router.put("/me", response_model=ResponseModel[UserOut])
async def update_me(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新当前用户资料"""
    user = await UserService.update_profile(db, current_user.id, data)
    return ResponseModel(data=UserOut.model_validate(user))