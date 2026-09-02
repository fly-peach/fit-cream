"""
计费服务（BillingService）

预充值余额 + 按真实用量扣费（区分输入/输出/缓存命中单价）。

- 计量仍走 user_token_usages（UsageService），金额/余额走本模块。
- 计费点：对话流结束（chat.py _upsert_user_token_usage）、记忆后台任务
  （usage_service.record_background）。
- BYOK（用户自备 DeepSeek key）请求：billed=False 只记流水不动余额，
  成本由用户自己的 key 承担；key 失效回退 qwen（我方付费）时照常计费。
- 金额一律 Decimal（元，4 位小数），避免浮点误差。
- 计费公式：charge = input×输入价 + output×输出价 − cache_read×(输入价−缓存价)
  （input_tokens 已含 cache_read/cache_write，缓存命中部分按缓存价计，
   其余输入与 cache_write 按输入价计）。

首次注册前 N 名用户自动发放代金券（grant_registration_bonus，注册时调用）。
"""
import logging
import random
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from src.agents.models.billing import (
    BillingAccount,
    BillingPackage,
    BillingPricing,
    BillingTransaction,
    RechargeApplication,
)
from src.fitme.models.user import User
from src.fitme.services.payment_gateway import payment_gateway
from utils.exceptions import BusinessException, ErrorCode

logger = logging.getLogger("fitcream.billing")

# 默认单价（元/百万 token，消费价已含加价；billing_pricing 表存在时以表为准）
DEFAULT_PRICING = {
    "input_price": Decimal("3.0"),
    "output_price": Decimal("10.0"),
    "cache_read_price": Decimal("0.3"),
    # 检索类模型（仅输入计费）：text-embedding-v3 成本 0.5、qwen3-rerank 成本 0.6
    "embedding_price": Decimal("0.5"),
    "rerank_price": Decimal("0.6"),
}

# 记账来源（与 user_token_usages.source 对齐）
SOURCE_CHAT = "chat"
SOURCE_MEMORY_EXTRACTION = "memory_extraction"
SOURCE_MEMORY_CONSOLIDATION = "memory_consolidation"

_QUANT = Decimal("0.0001")


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _gen_app_no() -> str:
    return f"RC{int(time.time())}{random.randint(1000, 9999)}"


class BillingService:
    # ================= 单价 =================

    @staticmethod
    async def get_pricing(db: AsyncSession) -> dict[str, Decimal]:
        """读取生效单价（billing_pricing 首条 active 行），缺失/表不存在时回退默认。"""
        try:
            row = (
                await db.execute(
                    select(BillingPricing)
                    .where(BillingPricing.active.is_(True))
                    .order_by(BillingPricing.id)
                    .limit(1)
                )
            ).scalar_one_or_none()
        except Exception:
            return dict(DEFAULT_PRICING)
        if row is None:
            return dict(DEFAULT_PRICING)
        return {
            "input_price": row.input_price,
            "output_price": row.output_price,
            "cache_read_price": row.cache_read_price,
            "embedding_price": row.embedding_price or DEFAULT_PRICING["embedding_price"],
            "rerank_price": row.rerank_price or DEFAULT_PRICING["rerank_price"],
        }

    @staticmethod
    def compute_charge(
        pricing: dict[str, Decimal],
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> Decimal:
        """按单价计算消费金额（元，4 位小数）。"""
        M = Decimal("1000000")
        total = (
            Decimal(input_tokens) * pricing["input_price"]
            + Decimal(output_tokens) * pricing["output_price"]
            - Decimal(cache_read_tokens) * (pricing["input_price"] - pricing["cache_read_price"])
        )
        if total < 0:
            total = Decimal("0")
        return _round(total / M)

    # ================= 账户 =================

    @staticmethod
    async def get_or_create_account(db: AsyncSession, user_id) -> BillingAccount:
        """获取钱包，不存在则创建（user_id 接受 UUID 或字符串）。"""
        result = await db.execute(select(BillingAccount).where(BillingAccount.user_id == user_id))
        account = result.scalar_one_or_none()
        if account is None:
            account = BillingAccount(user_id=user_id, balance=Decimal("0"))
            db.add(account)
            await db.flush()
            await db.refresh(account)
        return account

    @staticmethod
    async def get_balance(db: AsyncSession, user_id) -> BillingAccount:
        """读取余额（缺钱包时返回零余额占位，不落库）。"""
        result = await db.execute(select(BillingAccount).where(BillingAccount.user_id == user_id))
        account = result.scalar_one_or_none()
        if account is None:
            # status 显式置 normal：列 default 在 flush 时才生效，未落库的占位对象需自给
            return BillingAccount(user_id=user_id, balance=Decimal("0"), status="normal")
        return account

    @staticmethod
    async def check_can_chat(db: AsyncSession, user: User) -> None:
        """对话入口余额门控：admin 豁免；frozen 或余额<=0 拒绝。"""
        if user.role == "admin":
            return
        account = await BillingService.get_balance(db, user.id)
        if account.status == "frozen":
            raise BusinessException(ErrorCode.ACCOUNT_FROZEN, "账号已被冻结，无法发起对话")
        if (account.balance or Decimal("0")) <= 0:
            raise BusinessException(ErrorCode.INSUFFICIENT_BALANCE, "余额不足，请先充值")

    # ================= 记账 =================

    @staticmethod
    async def _adjust_balance(
        db: AsyncSession,
        user_id,
        delta: Decimal,
        *,
        granted: bool = False,
        recharged: bool = False,
    ) -> Decimal:
        """原子增减余额，返回新余额（不 commit，由调用方决定）。"""
        account = await BillingService.get_or_create_account(db, user_id)
        values = {"balance": BillingAccount.balance + delta}
        if granted:
            values["total_granted"] = BillingAccount.total_granted + delta
        if recharged:
            values["total_recharged"] = BillingAccount.total_recharged + delta
        if delta < 0:
            values["total_consumed"] = BillingAccount.total_consumed + delta
        stmt = (
            update(BillingAccount)
            .where(BillingAccount.id == account.id)
            .values(**values)
            .returning(BillingAccount.balance)
        )
        new_balance = (await db.execute(stmt)).scalar_one()
        return new_balance

    @staticmethod
    async def _record_txn(
        db: AsyncSession,
        *,
        user_id,
        txn_type: str,
        amount: Decimal,
        balance_after: Decimal,
        source: str,
        description: Optional[str] = None,
        model_provider: str = "qwen",
        billed: bool = True,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
        estimated: bool = False,
    ) -> None:
        db.add(BillingTransaction(
            user_id=user_id,
            type=txn_type,
            amount=amount,
            balance_after=balance_after,
            source=source,
            description=description,
            model_provider=model_provider,
            billed=billed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            reasoning_tokens=reasoning_tokens,
            estimated=estimated,
        ))

    @staticmethod
    async def consume(
        db: AsyncSession,
        *,
        user_id,
        source: str = SOURCE_CHAT,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
        estimated: bool = False,
        billed: bool = True,
        description: Optional[str] = None,
    ) -> Decimal:
        """按真实用量扣费并记流水（含 commit）。

        billed=False：BYOK 请求只记流水不动余额（成本归用户自己的 key）。
        """
        pricing = await BillingService.get_pricing(db)
        charge = BillingService.compute_charge(
            pricing, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens
        )
        try:
            if billed and charge > 0:
                new_balance = await BillingService._adjust_balance(db, user_id, -charge)
            else:
                account = await BillingService.get_balance(db, user_id)
                new_balance = account.balance or Decimal("0")
            await BillingService._record_txn(
                db,
                user_id=user_id,
                txn_type="consume",
                amount=-charge if billed else Decimal("0"),
                balance_after=new_balance,
                source=source,
                description=description,
                billed=billed,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                cache_read_tokens=int(cache_read_tokens),
                cache_write_tokens=int(cache_write_tokens),
                reasoning_tokens=int(reasoning_tokens),
                estimated=estimated,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.warning(
                f"[Billing] consume failed | user={str(user_id)[:8]} | source={source}",
                exc_info=True,
            )
            charge = Decimal("0")
        # billed=False（BYOK）不扣费，返回实际扣款金额 0
        return charge if billed else Decimal("0")

    @staticmethod
    async def consume_search_cost(
        db: AsyncSession,
        *,
        user_id,
        source: str,
        embedding_tokens: int = 0,
        rerank_tokens: int = 0,
        description: Optional[str] = None,
    ) -> Decimal:
        """按检索类模型单价记账（用户对话触发的 embedding/rerank 成本）。

        - embedding 用 text-embedding-v3 单价、rerank 用 qwen3-rerank 单价（元/百万输入 token）。
        - token 由调用方用 estimate_tokens 估算（检索响应不暴露 usage）。
        - 失败仅告警不抛错（不阻断检索本身），返回实际扣款金额。
        """
        try:
            pricing = await BillingService.get_pricing(db)
            M = Decimal("1000000")
            charge = _round(
                Decimal(int(embedding_tokens)) * pricing["embedding_price"] / M
                + Decimal(int(rerank_tokens)) * pricing["rerank_price"] / M
            )
            if charge <= 0:
                return Decimal("0")
            new_balance = await BillingService._adjust_balance(db, user_id, -charge)
            await BillingService._record_txn(
                db,
                user_id=user_id,
                txn_type="consume",
                amount=-charge,
                balance_after=new_balance,
                source=source,
                description=description,
                input_tokens=int(embedding_tokens) + int(rerank_tokens),
            )
            await db.commit()
            return charge
        except Exception:
            logger.warning(
                f"[Billing] consume_search_cost failed | user={str(user_id)[:8]} | source={source}",
                exc_info=True,
            )
            return Decimal("0")

    @staticmethod
    async def credit(
        db: AsyncSession,
        *,
        user_id,
        amount: Decimal,
        txn_type: str = "grant",
        source: str = "admin_grant",
        description: Optional[str] = None,
        commit: bool = True,
    ) -> BillingAccount:
        """入账（充值核销 / 管理员赠送），含 commit（默认）。"""
        if amount <= 0:
            raise BusinessException(ErrorCode.BAD_REQUEST, "金额必须大于 0")
        amount = _round(amount)
        new_balance = await BillingService._adjust_balance(
            db,
            user_id,
            amount,
            granted=(txn_type == "grant"),
            recharged=(txn_type == "recharge"),
        )
        await BillingService._record_txn(
            db,
            user_id=user_id,
            txn_type=txn_type,
            amount=amount,
            balance_after=new_balance,
            source=source,
            description=description,
        )
        if commit:
            await db.commit()
        return await BillingService.get_balance(db, user_id)

    @staticmethod
    async def grant_registration_bonus(db: AsyncSession, user: User) -> bool:
        """前 N 名注册用户发放代金券（注册事务内调用，不 commit，由调用方提交）。

        以当前总注册数（含本用户）判断是否在赠送名额内；每人仅一次（source=coupon）。
        """
        try:
            if not settings.REGISTRATION_BONUS_ENABLED:
                return False
            if user.role == "admin":
                return False
            already = (
                await db.execute(
                    select(BillingTransaction.id).where(
                        BillingTransaction.user_id == user.id,
                        BillingTransaction.source == "coupon",
                    ).limit(1)
                )
            ).scalar_one_or_none()
            if already:
                return False
            cnt = (
                await db.execute(
                    select(func.count()).select_from(User).where(User.deleted_at.is_(None))
                )
            ).scalar_one()
            if cnt > settings.REGISTRATION_BONUS_FIRST_N:
                return False
            amount = Decimal(str(settings.REGISTRATION_BONUS_AMOUNT))
            await BillingService.credit(
                db,
                user_id=user.id,
                amount=amount,
                txn_type="grant",
                source="coupon",
                description="首批注册用户50元代金券",
                commit=False,
            )
            return True
        except Exception:
            logger.warning(
                f"[Billing] 注册赠送失败 | user={str(user.id)[:8]}", exc_info=True
            )
            return False

    @staticmethod
    async def backfill_registration_bonus(db: AsyncSession) -> int:
        """回填既有注册用户的前 N 名代金券（按注册时间升序，含功能上线前注册的用户）。

        幂等：仅给未领过 coupon 的用户发放，且累计满 FIRST_N 即停止。
        启动时调用（seed 阶段），失败仅告警不影响启动。
        """
        if not settings.REGISTRATION_BONUS_ENABLED:
            return 0
        # 已发放名额
        granted = (
            await db.execute(
                select(func.count()).select_from(BillingTransaction).where(
                    BillingTransaction.source == "coupon"
                )
            )
        ).scalar_one()
        if granted >= settings.REGISTRATION_BONUS_FIRST_N:
            return 0
        # 按注册时间取仍未领券的用户（admin 排除）
        subscribed_ids = select(BillingTransaction.user_id).where(
            BillingTransaction.source == "coupon"
        )
        rows = (
            await db.execute(
                select(User.id)
                .where(
                    User.deleted_at.is_(None),
                    User.role != "admin",
                    User.id.not_in(subscribed_ids),
                )
                .order_by(User.created_at.asc())
                .limit(settings.REGISTRATION_BONUS_FIRST_N - granted)
            )
        ).scalars().all()
        if not rows:
            return 0
        amount = Decimal(str(settings.REGISTRATION_BONUS_AMOUNT))
        for uid in rows:
            await BillingService.credit(
                db,
                user_id=uid,
                amount=amount,
                txn_type="grant",
                source="coupon",
                description="首批注册用户50元代金券",
                commit=False,
            )
        await db.commit()
        logger.info(
            "[Billing] 注册代金券回填完成: %s 人，当前名额 %s/%s",
            len(rows),
            granted + len(rows),
            settings.REGISTRATION_BONUS_FIRST_N,
        )
        return len(rows)

    # ================= 查询 =================

    @staticmethod
    async def list_transactions(
        db: AsyncSession, user_id, page: int = 1, size: int = 20
    ) -> tuple[list[BillingTransaction], int]:
        stmt = select(BillingTransaction).where(
            BillingTransaction.user_id == user_id
        ).order_by(BillingTransaction.created_at.desc())
        total = (
            await db.execute(
                select(func.count()).select_from(BillingTransaction).where(
                    BillingTransaction.user_id == user_id
                )
            )
        ).scalar_one()
        rows = (
            (await db.execute(stmt.offset((page - 1) * size).limit(size))).scalars().all()
        )
        return list(rows), int(total)

    @staticmethod
    async def list_active_packages(db: AsyncSession) -> list[BillingPackage]:
        rows = (
            await db.execute(
                select(BillingPackage)
                .where(BillingPackage.active.is_(True))
                .order_by(BillingPackage.price)
            )
        ).scalars().all()
        return list(rows)

    # ================= 充值申请（个人收款码 + 人工核销） =================

    @staticmethod
    async def create_recharge_application(
        db: AsyncSession,
        user_id,
        amount: Decimal,
        method: str,
        note: Optional[str] = None,
        auto_confirm: Optional[bool] = None,
    ) -> RechargeApplication:
        """提交充值申请（无支付网关的备用流程）。

        默认（RECHARGE_AUTO_CONFIRM=True）提交即入账：余额直接到账，
        转账备注为「用户 ID」（无管理员审核，事后按备注对账）；
        配置关闭时走管理员人工核销（status=pending，由 review_application 处理）。
        """
        if amount <= 0:
            raise BusinessException(ErrorCode.BAD_REQUEST, "充值金额必须大于 0")
        if amount > Decimal("10000"):
            raise BusinessException(ErrorCode.BAD_REQUEST, "单笔充值金额不能超过 10000 元")
        if auto_confirm is None:
            auto_confirm = bool(getattr(settings, "RECHARGE_AUTO_CONFIRM", True))
        app = RechargeApplication(
            user_id=user_id,
            app_no=_gen_app_no(),
            amount=_round(amount),
            method=method,
            note=note,
        )
        db.add(app)
        if auto_confirm:
            await BillingService.credit(
                db,
                user_id=user_id,
                amount=app.amount,
                txn_type="recharge",
                source="recharge",
                description=f"自动到账充值（{app.app_no}）",
                commit=False,
            )
            app.status = "confirmed"
            app.review_note = "自动到账"
        await db.commit()
        await db.refresh(app)
        return app

    @staticmethod
    async def create_recharge_order(
        db: AsyncSession,
        user_id,
        amount: Decimal,
        method: str,
        note: Optional[str] = None,
    ) -> tuple[RechargeApplication, str, str]:
        """充值下单（订单机制）。

        - 配置了虎皮椒网关：创建 pending 订单 → 虎皮椒下单 → 返回二维码地址。
          用户扫码付款后由回调（settle_order）自动入账，付款后才到账。
        - 未配置网关：回退 create_recharge_application（自动到账/人工核销），
          返回空二维码（前端据此走备用提示）。

        返回 (app, qr_code_url, pay_url)。
        """
        if amount <= 0:
            raise BusinessException(ErrorCode.BAD_REQUEST, "充值金额必须大于 0")
        if amount > Decimal("10000"):
            raise BusinessException(ErrorCode.BAD_REQUEST, "单笔充值金额不能超过 10000 元")
        amount = _round(amount)

        if not payment_gateway.configured:
            app = await BillingService.create_recharge_application(
                db, user_id, amount, method, note
            )
            return app, "", ""

        app_no = _gen_app_no()
        app = RechargeApplication(
            user_id=user_id,
            app_no=app_no,
            trade_order_id=app_no,
            amount=amount,
            method=method,
            note=note,
            status="pending",
        )
        db.add(app)
        await db.flush()
        try:
            data = await payment_gateway.create_order(
                trade_order_id=app_no,
                amount=str(amount),
                title="FitCream 充值",
                attach=str(user_id),
            )
        except Exception:
            await db.rollback()
            raise
        qr_url = str(data.get("url_qrcode", "") or "")
        pay_url = str(data.get("url", "") or "")
        await db.commit()
        await db.refresh(app)
        return app, qr_url, pay_url

    @staticmethod
    async def settle_order(
        db: AsyncSession,
        trade_order_id: str,
        transaction_id: Optional[str] = None,
    ) -> bool:
        """支付回调入账（幂等）：订单待支付 → 发放额度 + confirmed。

        虎皮椒回调按 trade_order_id 定位订单；已到账的订单重复回调直接返回 True。
        """
        if not trade_order_id:
            return False
        app = (
            await db.execute(
                select(RechargeApplication).where(
                    RechargeApplication.trade_order_id == trade_order_id
                )
            )
        ).scalar_one_or_none()
        if app is None:
            return False
        if app.status == "confirmed":
            return True  # 幂等：已入账
        if app.status != "pending":
            return False
        await BillingService.credit(
            db,
            user_id=app.user_id,
            amount=app.amount,
            txn_type="recharge",
            source="recharge",
            description=f"虎皮椒支付到账（{app.app_no}）",
            commit=False,
        )
        app.status = "confirmed"
        app.pay_transaction_id = transaction_id
        app.review_note = "支付回调"
        app.paid_at = func.now()
        await db.commit()
        return True

    @staticmethod
    async def list_my_applications(
        db: AsyncSession, user_id, limit: int = 20
    ) -> list[RechargeApplication]:
        rows = (
            await db.execute(
                select(RechargeApplication)
                .where(RechargeApplication.user_id == user_id)
                .order_by(RechargeApplication.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        return list(rows)

    @staticmethod
    async def list_applications(
        db: AsyncSession, status: Optional[str] = None, page: int = 1, size: int = 20
    ) -> tuple[list[RechargeApplication], int]:
        cond = []
        if status:
            cond.append(RechargeApplication.status == status)
        total = (
            await db.execute(
                select(func.count()).select_from(RechargeApplication).where(*cond)
            )
        ).scalar_one()
        stmt = (
            select(RechargeApplication)
            .where(*cond)
            .order_by(RechargeApplication.created_at.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), int(total)

    @staticmethod
    async def review_application(
        db: AsyncSession,
        app_id: UUID,
        admin: User,
        *,
        approve: bool,
        review_note: Optional[str] = None,
    ) -> RechargeApplication:
        """核销充值申请：approve 时给用户充值入账 + 记流水（含 commit）。"""
        app = (
            await db.execute(select(RechargeApplication).where(RechargeApplication.id == app_id))
        ).scalar_one_or_none()
        if app is None:
            raise BusinessException(ErrorCode.NOT_FOUND, "充值申请不存在")
        if app.status != "pending":
            raise BusinessException(ErrorCode.BAD_REQUEST, "该申请已处理")
        if approve:
            await BillingService.credit(
                db,
                user_id=app.user_id,
                amount=app.amount,
                txn_type="recharge",
                source="recharge",
                description=f"人工充值（{app.app_no}）",
                commit=False,
            )
            app.status = "confirmed"
        else:
            app.status = "rejected"
        app.review_note = review_note
        app.reviewed_by = admin.id
        app.reviewed_at = func.now()
        await db.commit()
        await db.refresh(app)
        return app
