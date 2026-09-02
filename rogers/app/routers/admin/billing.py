"""
管理端计费路由 /api/admin/billing/*

充值申请核销（个人收款码人工确认）、单价热更新、全局收入/成本概览。
所有端点要求管理员权限（get_admin_user）。
"""
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user
from src.agents.models.billing import BillingPricing, BillingTransaction, RechargeApplication
from src.fitme.models.user import User
from src.fitme.schemas.billing import (
    BillingPricingOut,
    RechargeApplicationOut,
    RechargeReviewIn,
)
from src.fitme.schemas.common import PaginatedResponse, ResponseModel
from src.fitme.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["admin-billing"])


def _app_out(app: RechargeApplication) -> RechargeApplicationOut:
    return RechargeApplicationOut(
        id=str(app.id),
        app_no=app.app_no,
        amount=app.amount,
        method=app.method,
        note=app.note,
        status=app.status,
        review_note=app.review_note,
        created_at=app.created_at,
        reviewed_at=app.reviewed_at,
    )


@router.get(
    "/applications",
    response_model=ResponseModel[PaginatedResponse[RechargeApplicationOut]],
    operation_id="admin_list_recharge_applications",
)
async def admin_list_applications(
    status: Optional[str] = Query(None, pattern="^(pending|confirmed|rejected)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """充值申请列表（默认全部，可按状态筛选）"""
    rows, total = await BillingService.list_applications(db, status, page, size)
    return ResponseModel(data=PaginatedResponse(
        items=[_app_out(a) for a in rows],
        total=total,
        page=page,
        size=size,
    ))


@router.post(
    "/applications/{app_id}/review",
    response_model=ResponseModel[RechargeApplicationOut],
    operation_id="admin_review_recharge_application",
)
async def admin_review_application(
    app_id: UUID,
    data: RechargeReviewIn,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """核销充值申请：approve=true 确认到账给用户加余额，false 拒绝"""
    app = await BillingService.review_application(
        db, app_id, admin, approve=data.approve, review_note=data.review_note
    )
    return ResponseModel(data=_app_out(app), message="已确认充值" if data.approve else "已拒绝")


@router.get(
    "/pricing",
    response_model=ResponseModel[BillingPricingOut],
    operation_id="admin_get_billing_pricing",
)
async def admin_get_pricing(
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """当前计费单价"""
    pricing = await BillingService.get_pricing(db)
    return ResponseModel(data=BillingPricingOut(
        model="qwen3.8-flash",
        input_price=pricing["input_price"],
        output_price=pricing["output_price"],
        cache_read_price=pricing["cache_read_price"],
        embedding_price=pricing["embedding_price"],
        rerank_price=pricing["rerank_price"],
    ))


@router.put(
    "/pricing",
    response_model=ResponseModel[BillingPricingOut],
    operation_id="admin_update_billing_pricing",
)
async def admin_update_pricing(
    data: BillingPricingOut,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新计费单价（元/百万 token，消费价已含加价）"""
    row = (
        await db.execute(
            select(BillingPricing).where(BillingPricing.active.is_(True)).order_by(BillingPricing.id).limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        row = BillingPricing(
            model=data.model,
            input_price=data.input_price,
            output_price=data.output_price,
            cache_read_price=data.cache_read_price,
            cost_input_price=data.cost_input_price,
            cost_output_price=data.cost_output_price,
            cost_cache_read_price=data.cost_cache_read_price,
            embedding_price=data.embedding_price,
            rerank_price=data.rerank_price,
            active=True,
        )
        db.add(row)
    else:
        row.input_price = data.input_price
        row.output_price = data.output_price
        row.cache_read_price = data.cache_read_price
        row.cost_input_price = data.cost_input_price
        row.cost_output_price = data.cost_output_price
        row.cost_cache_read_price = data.cost_cache_read_price
        row.embedding_price = data.embedding_price
        row.rerank_price = data.rerank_price
    await db.commit()
    return ResponseModel(data=data)


@router.get("/overview", response_model=ResponseModel[dict], operation_id="admin_billing_overview")
async def admin_billing_overview(
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """全局收入 / 赠送 / 消费 / 成本估算概览"""
    async def _sum(where, col):
        return (
            await db.execute(select(func.coalesce(func.sum(col), 0)).where(where))
        ).scalar_one()

    recharged = Decimal(
        await _sum(BillingTransaction.type == "recharge", BillingTransaction.amount)
    )
    granted = Decimal(
        await _sum(BillingTransaction.type == "grant", BillingTransaction.amount)
    )
    consumed = Decimal(
        await _sum(BillingTransaction.billed.is_(True), -BillingTransaction.amount)
    )
    # 成本估算：仅 qwen（我方付费）计成本，按成本单价×token
    pricing = await BillingService.get_pricing(db)
    M = Decimal("1000000")
    cost_input = Decimal("0.8")
    cost_output = Decimal("2.7")
    cost_cache = Decimal("0.1")
    totals = (
        await db.execute(
            select(
                func.coalesce(func.sum(BillingTransaction.input_tokens), 0),
                func.coalesce(func.sum(BillingTransaction.output_tokens), 0),
                func.coalesce(func.sum(BillingTransaction.cache_read_tokens), 0),
            ).where(
                BillingTransaction.billed.is_(True),
                BillingTransaction.type == "consume",
            )
        )
    ).one()
    in_tok, out_tok, cache_tok = (int(v or 0) for v in totals)
    est_cost = (
        Decimal(in_tok) * cost_input / M
        + Decimal(out_tok) * cost_output / M
        - Decimal(cache_tok) * (cost_input - cost_cache) / M
    )
    pending = (
        await db.execute(
            select(func.count()).select_from(RechargeApplication).where(
                RechargeApplication.status == "pending"
            )
        )
    ).scalar_one()
    return ResponseModel(data={
        "recharged": str(recharged),
        "granted": str(granted),
        "consumed": str(consumed),
        "estimated_cost": str(est_cost.quantize(Decimal("0.01"))),
        "pending_applications": int(pending),
        "pricing": {
            "input_price": str(pricing["input_price"]),
            "output_price": str(pricing["output_price"]),
            "cache_read_price": str(pricing["cache_read_price"]),
        },
    })
