"""
计费模型（钱包 / 流水 / 单价 / 套餐 / 充值申请）

金额一律以「元」为单位的 NUMERIC(12,4)（Python Decimal），避免浮点误差。
用户 token 用量仍走 user_token_usages（计量），金额与余额走本模块（计费），
两者通过 billing_transactions 关联（source 对齐 chat / memory_extraction /
memory_consolidation）。
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BillingAccount(Base):
    """用户钱包（一人一行，余额按元存 4 位小数）。"""

    __tablename__ = "billing_accounts"

    id: Mapped[PyUUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), nullable=False
    )
    total_recharged: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), nullable=False
    )
    total_granted: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), nullable=False
    )
    total_consumed: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), nullable=False
    )
    # normal / frozen（frozen 禁止发起对话，管理端封禁）
    status: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BillingTransaction(Base):
    """账单流水：充值 / 消费 / 赠送 / 退款（amount 正=入账，负=消费）。"""

    __tablename__ = "billing_transactions"

    id: Mapped[PyUUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # recharge / consume / grant / refund
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # chat / memory_extraction / memory_consolidation / recharge / admin_grant / coupon
    # 成本归属：qwen（我方付费）/ deepseek（BYOK 用户自费，仅记录不计费）
    model_provider: Mapped[str] = mapped_column(String(20), default="qwen", nullable=False)
    # BYOK 请求（有 ds_key 且未回退 qwen）billed=False：只记流水不动余额
    billed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    description: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class BillingPricing(Base):
    """计费单价（元/百万 token，消费价已含加价；管理端热更新）。"""

    __tablename__ = "billing_pricing"

    id: Mapped[PyUUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    model: Mapped[str] = mapped_column(String(50), default="qwen3.8-flash", nullable=False)
    input_price: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    output_price: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    cache_read_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    cache_write_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    # 成本价参考（仅报表/展示，不参与计算）
    cost_input_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0.8"), nullable=False
    )
    cost_output_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("2.7"), nullable=False
    )
    cost_cache_read_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0.1"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BillingPackage(Base):
    """充值套餐（支付渠道后接后启用，现仅占位展示）。"""

    __tablename__ = "billing_packages"

    id: Mapped[PyUUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    bonus: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RechargeApplication(Base):
    """充值申请单：用户扫码付款后提交，管理员人工核销（个人收款码方案）。"""

    __tablename__ = "recharge_applications"

    id: Mapped[PyUUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[PyUUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # 收款备注单号（用户转账时填写，便于管理员对账；虎皮椒下单时作为商户订单号）
    app_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 虎皮椒商户订单号（= app_no，冗余字段便于按回调参数索引查询）
    trade_order_id: Mapped[str | None] = mapped_column(String(32), index=True)
    # 支付平台交易号（虎皮椒回调 transaction_id）
    pay_transaction_id: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), default="wechat", nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))
    # pending=待支付（订单已创建） / confirmed=已支付到账 / rejected=失败关闭
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    review_note: Mapped[str | None] = mapped_column(String(255))
    reviewed_by: Mapped[PyUUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
