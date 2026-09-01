"""
计费 Schemas（余额 / 流水 / 充值申请 / 单价 / 套餐）
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class BillingAccountOut(BaseModel):
    balance: Decimal = Decimal("0")
    total_recharged: Decimal = Decimal("0")
    total_granted: Decimal = Decimal("0")
    total_consumed: Decimal = Decimal("0")
    status: str = "normal"


class BillingTransactionOut(BaseModel):
    id: str
    type: str
    amount: Decimal
    balance_after: Decimal
    source: str
    description: Optional[str] = None
    model_provider: str = "qwen"
    billed: bool = True
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    estimated: bool = False
    created_at: datetime


class BillingPricingOut(BaseModel):
    model: str = "qwen3.8-flash"
    input_price: Decimal
    output_price: Decimal
    cache_read_price: Decimal
    cost_input_price: Decimal = Decimal("0.8")
    cost_output_price: Decimal = Decimal("2.7")
    cost_cache_read_price: Decimal = Decimal("0.1")


class BillingPackageOut(BaseModel):
    id: str
    name: str
    price: Decimal
    bonus: Decimal = Decimal("0")


class BillingMeOut(BaseModel):
    user_id: str = ""
    balance: Decimal
    total_recharged: Decimal
    total_granted: Decimal
    total_consumed: Decimal
    status: str
    pricing: Optional[BillingPricingOut] = None
    qr_code_url: str = ""


class RechargeApplicationCreate(BaseModel):
    amount: Decimal = Field(gt=0, le=10000)
    method: str = Field(default="wechat", pattern="^(wechat|alipay)$")
    note: Optional[str] = Field(default=None, max_length=255)


class RechargeApplicationOut(BaseModel):
    id: str
    app_no: str
    amount: Decimal
    method: str
    note: Optional[str] = None
    status: str
    review_note: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None


class RechargeOrderOut(BaseModel):
    """充值下单响应：app 为订单/申请单；qr_code_url/pay_url 为虎皮椒支付信息。

    qr_code_url 为空表示未配置支付网关（走备用流程，app.status 已到账或待核销）。
    """
    app: RechargeApplicationOut
    qr_code_url: str = ""
    pay_url: str = ""


class RechargeReviewIn(BaseModel):
    approve: bool
    review_note: Optional[str] = Field(default=None, max_length=255)


class BillingGrantIn(BaseModel):
    amount: Decimal = Field(gt=0)
    reason: Optional[str] = Field(default=None, max_length=255)
