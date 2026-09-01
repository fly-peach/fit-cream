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
    AdminResetPasswordOut,
    AdminUserDetail,
    AdminUserListItem,
    AdminUserUpdate,
)
from src.fitme.schemas.billing import BillingAccountOut, BillingGrantIn
from src.fitme.schemas.common import PaginatedResponse, ResponseModel
from src.fitme.schemas.usage import UserTokenUsageOut
from src.fitme.services.admin_service import AdminService
from src.fitme.services.billing_service import BillingService
from src.fitme.services.usage_service import UsageService

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


@router.get(
    "/{user_id}/token-usage",
    response_model=ResponseModel[UserTokenUsageOut],
    operation_id="admin_get_user_token_usage",
)
async def admin_get_user_token_usage(
    user_id: UUID,
    days: int = Query(30, ge=1, le=365),
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """用户 token 用量（admin）"""
    summary = await UsageService.get_user_summary(db, user_id, days)
    return ResponseModel(data=summary)


@router.get(
    "/{user_id}/billing",
    response_model=ResponseModel[BillingAccountOut],
    operation_id="admin_get_user_billing",
)
async def admin_get_user_billing(
    user_id: UUID,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """用户余额（admin）"""
    account = await BillingService.get_balance(db, user_id)
    return ResponseModel(data=BillingAccountOut(
        balance=account.balance or 0,
        total_recharged=account.total_recharged or 0,
        total_granted=account.total_granted or 0,
        total_consumed=account.total_consumed or 0,
        status=account.status,
    ))


@router.post(
    "/{user_id}/billing/grant",
    response_model=ResponseModel[BillingAccountOut],
    operation_id="admin_grant_user_billing",
)
async def admin_grant_user_billing(
    user_id: UUID,
    data: BillingGrantIn,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员给指定用户单独加量（赠送余额）"""
    account = await BillingService.credit(
        db,
        user_id=user_id,
        amount=data.amount,
        txn_type="grant",
        source="admin_grant",
        description=data.reason or "管理员加量",
    )
    return ResponseModel(data=BillingAccountOut(
        balance=account.balance or 0,
        total_recharged=account.total_recharged or 0,
        total_granted=account.total_granted or 0,
        total_consumed=account.total_consumed or 0,
        status=account.status,
    ), message=f"已加量 {data.amount} 元")


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


@router.delete(
    "/{user_id}",
    response_model=ResponseModel[None],
    operation_id="admin_delete_user",
)
async def admin_delete_user(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """停用账号（软删：置 deleted_at + is_active=False，不硬删数据，admin，含自保护）

    与用户本人注销（/auth/deactivate 立即硬删）区分：管理员停用走软删，
    从而绕开知识库 owner_id / KBDocument.created_by 的级联与外键冲突。
    """
    await AdminService.deactivate_user(db, user_id, admin)
    await db.commit()
    return ResponseModel(message="已注销该用户")


@router.post(
    "/{user_id}/reset-password",
    response_model=ResponseModel[AdminResetPasswordOut],
    operation_id="admin_reset_password",
)
async def admin_reset_password(
    user_id: UUID,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """重置用户密码（返回一次性临时密码）"""
    _user, temp = await AdminService.reset_password(db, user_id)
    await db.commit()
    return ResponseModel(data=AdminResetPasswordOut(new_password=temp))
