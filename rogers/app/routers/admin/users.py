"""
管理端用户路由 /api/admin/users/*

提供管理员专用的用户列表（搜索/筛选/分页）、详情、近期打卡与状态变更端点。
状态变更含自保护：不能禁用或降级自己。
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user
from src.fitme.models.user import User
from src.fitme.schemas.admin import (
    AdminCheckinOut,
    AdminUserDetail,
    AdminUserListItem,
    AdminUserUpdate,
)
from src.fitme.schemas.common import PaginatedResponse, ResponseModel
from src.fitme.services.admin_service import AdminService

router = APIRouter(prefix="/users", tags=["admin-users"])


@router.get(
    "",
    response_model=ResponseModel[PaginatedResponse[AdminUserListItem]],
    operation_id="admin_list_users",
)
async def admin_list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, max_length=100, description="手机号/姓名/邮箱模糊搜索"),
    role: Optional[str] = Query(None, pattern="^(user|admin)$"),
    is_active: Optional[bool] = Query(None),
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """用户列表（admin）"""
    items, total = await AdminService.list_users(
        db, page=page, size=size, keyword=keyword, role=role, is_active=is_active
    )
    return ResponseModel(
        data=PaginatedResponse(items=items, total=total, page=page, size=size)
    )


@router.get(
    "/{user_id}",
    response_model=ResponseModel[AdminUserDetail],
    operation_id="admin_get_user",
)
async def admin_get_user(
    user_id: UUID,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """用户详情（admin）"""
    item = await AdminService.get_user_detail(db, user_id)
    return ResponseModel(data=item)


@router.get(
    "/{user_id}/checkins",
    response_model=ResponseModel[list[AdminCheckinOut]],
    operation_id="admin_list_user_checkins",
)
async def admin_list_user_checkins(
    user_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """用户近期打卡（admin）"""
    items = await AdminService.list_user_checkins(db, user_id, limit=limit)
    return ResponseModel(data=items)


@router.patch(
    "/{user_id}",
    response_model=ResponseModel[AdminUserListItem],
    operation_id="admin_update_user",
)
async def admin_update_user(
    user_id: UUID,
    data: AdminUserUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """变更用户状态（禁用/启用、角色切换）（admin，含自保护）"""
    item = await AdminService.update_user(
        db,
        user_id,
        admin_user=admin,
        is_active=data.is_active,
        role=data.role,
    )
    await db.commit()
    return ResponseModel(data=item)
