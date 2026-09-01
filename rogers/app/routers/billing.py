"""
计费路由 /api/billing/*（用户端）

提供余额查询、账单流水、充值下单（虎皮椒订单机制 + 备用流程）、支付回调。
- 配置虎皮椒网关：下单返回二维码 → 用户扫码付款 → /pay/notify 回调自动到账。
- 未配置网关：回退 RECHARGE_AUTO_CONFIRM 逻辑（提交即到账 / 人工核销）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from src.agents.models.billing import BillingTransaction, RechargeApplication
from src.fitme.models.user import User
from src.fitme.schemas.billing import (
    BillingAccountOut,
    BillingMeOut,
    BillingPackageOut,
    BillingPricingOut,
    BillingTransactionOut,
    RechargeApplicationCreate,
    RechargeApplicationOut,
    RechargeOrderOut,
)
from src.fitme.schemas.common import PaginatedResponse, ResponseModel
from src.fitme.services.billing_service import BillingService
from src.fitme.services.payment_gateway import payment_gateway

router = APIRouter(prefix="/billing", tags=["billing"])


def _account_out(account) -> BillingAccountOut:
    return BillingAccountOut(
        balance=account.balance or 0,
        total_recharged=account.total_recharged or 0,
        total_granted=account.total_granted or 0,
        total_consumed=account.total_consumed or 0,
        status=account.status,
    )


def _txn_out(tx: BillingTransaction) -> BillingTransactionOut:
    return BillingTransactionOut(
        id=str(tx.id),
        type=tx.type,
        amount=tx.amount,
        balance_after=tx.balance_after,
        source=tx.source,
        description=tx.description,
        model_provider=tx.model_provider,
        billed=tx.billed,
        input_tokens=tx.input_tokens,
        output_tokens=tx.output_tokens,
        cache_read_tokens=tx.cache_read_tokens,
        cache_write_tokens=tx.cache_write_tokens,
        reasoning_tokens=tx.reasoning_tokens,
        estimated=tx.estimated,
        created_at=tx.created_at,
    )


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
        paid_at=app.paid_at,
    )


@router.get("/me", response_model=ResponseModel[BillingMeOut], operation_id="get_my_billing")
async def get_my_billing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """余额 + 单价说明 + 收款码（个人收款码方案）"""
    account = await BillingService.get_balance(db, current_user.id)
    pricing = await BillingService.get_pricing(db)
    pricing_out = BillingPricingOut(
        model="qwen3.8-flash",
        input_price=pricing["input_price"],
        output_price=pricing["output_price"],
        cache_read_price=pricing["cache_read_price"],
    )
    return ResponseModel(data=BillingMeOut(
        user_id=str(current_user.id),
        **_account_out(account).model_dump(),
        pricing=pricing_out,
        qr_code_url=settings.PAYMENT_QR_CODE_URL,
    ))


@router.get(
    "/transactions",
    response_model=ResponseModel[PaginatedResponse[BillingTransactionOut]],
    operation_id="list_my_billing_transactions",
)
async def list_my_transactions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """我的账单流水（分页，最近在前）"""
    rows, total = await BillingService.list_transactions(db, current_user.id, page, size)
    return ResponseModel(data=PaginatedResponse(
        items=[_txn_out(t) for t in rows],
        total=total,
        page=page,
        size=size,
    ))


@router.get(
    "/packages",
    response_model=ResponseModel[list[BillingPackageOut]],
    operation_id="list_billing_packages",
)
async def list_packages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """充值套餐（当前为展示占位，充值走人工核销）"""
    rows = await BillingService.list_active_packages(db)
    return ResponseModel(data=[BillingPackageOut(
        id=str(p.id), name=p.name, price=p.price, bonus=p.bonus
    ) for p in rows])


@router.post(
    "/recharge-applications",
    response_model=ResponseModel[RechargeOrderOut],
    operation_id="create_recharge_application",
)
async def create_recharge_application(
    data: RechargeApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """充值下单（虎皮椒订单机制 / 未配置网关回退自动到账）

    配置网关时返回二维码（qr_code_url），用户扫码付款后回调自动到账；
    未配置时 qr_code_url 为空，app.status 已到账（自动模式）或待核销（审核模式）。
    """
    app, qr_url, pay_url = await BillingService.create_recharge_order(
        db, current_user.id, data.amount, data.method, data.note
    )
    message = "已下单，请扫码支付" if qr_url else "充值已到账"
    return ResponseModel(data=RechargeOrderOut(
        app=_app_out(app),
        qr_code_url=qr_url,
        pay_url=pay_url,
    ), message=message)


@router.post("/pay/notify", include_in_schema=False)
async def pay_notify(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """虎皮椒支付回调（无需认证；验签通过后发放额度，返回 success 停止重试）。

    回调参数（form 表单）：trade_order_id / total_fee / transaction_id /
    status（OD=已支付）/ attach / time / nonce_str / hash。
    """
    form = await request.form()
    params: dict[str, str] = {k: str(v) for k, v in form.items()}
    if not payment_gateway.verify_notify(params):
        return PlainTextResponse("error")
    trade_order_id = params.get("trade_order_id", "")
    transaction_id = params.get("transaction_id", "")
    status = params.get("status", "")
    if status != "OD":
        # 非支付成功（如退款中）暂不入账，返回 success 避免无谓重试
        return PlainTextResponse("success")
    ok = await BillingService.settle_order(db, trade_order_id, transaction_id)
    return PlainTextResponse("success" if ok else "error")


@router.get(
    "/recharge-applications",
    response_model=ResponseModel[list[RechargeApplicationOut]],
    operation_id="list_my_recharge_applications",
)
async def list_my_applications(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """我的充值申请记录"""
    rows = await BillingService.list_my_applications(db, current_user.id, limit)
    return ResponseModel(data=[_app_out(a) for a in rows])
