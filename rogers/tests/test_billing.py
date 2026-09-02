"""
计费系统测试：注册赠送 / 扣费公式 / 余额门控 / 充值申请核销 / 管理员加量 / BYOK 不计费
"""
from decimal import Decimal

import pytest
from sqlalchemy import select

from src.agents.models.billing import BillingAccount, BillingTransaction, RechargeApplication
from src.fitme.services.billing_service import BillingService
from src.fitme.services.payment_gateway import sign_params
from tests.util import biz_code, unwrap
from utils.exceptions import BusinessException, ErrorCode


async def _balance(db, user) -> Decimal:
    return (await BillingService.get_balance(db, user.id)).balance or Decimal("0")


# ================= 计费公式 =================


def test_compute_charge_formula():
    p = {
        "input_price": Decimal("3"),
        "output_price": Decimal("10"),
        "cache_read_price": Decimal("0.3"),
    }
    # 100K 输入（90% 缓存）+ 10K 输出
    assert BillingService.compute_charge(p, 100_000, 10_000, 90_000, 0) == Decimal("0.157")
    # 零用量
    assert BillingService.compute_charge(p, 0, 0, 0, 0) == Decimal("0")
    # 纯输入无缓存
    assert BillingService.compute_charge(p, 10_000, 100, 0, 0) == Decimal("0.031")


# ================= 扣费 / BYOK =================


async def test_consume_deduction_and_transaction(db_session, user):
    await BillingService.credit(db_session, user_id=user.id, amount=Decimal("10"))
    charge = await BillingService.consume(
        db_session,
        user_id=user.id,
        source="chat",
        input_tokens=100_000,
        output_tokens=10_000,
        cache_read_tokens=90_000,
        reasoning_tokens=500,
    )
    assert charge == Decimal("0.157")
    assert await _balance(db_session, user) == Decimal("9.843")

    rows = (
        await db_session.execute(
            select(BillingTransaction).where(BillingTransaction.type == "consume")
        )
    ).scalars().all()
    assert len(rows) == 1
    tx = rows[0]
    assert tx.amount == Decimal("-0.157")
    assert tx.balance_after == Decimal("9.843")
    assert tx.source == "chat"
    assert tx.billed is True
    assert tx.input_tokens == 100_000
    assert tx.reasoning_tokens == 500


async def test_consume_byok_no_charge(db_session, user):
    """BYOK（用户自备 key）：只记流水，不动余额。"""
    await BillingService.credit(db_session, user_id=user.id, amount=Decimal("10"))
    charge = await BillingService.consume(
        db_session,
        user_id=user.id,
        source="chat",
        input_tokens=100_000,
        output_tokens=10_000,
        billed=False,
    )
    assert charge == Decimal("0")
    assert await _balance(db_session, user) == Decimal("10")
    rows = (
        await db_session.execute(select(BillingTransaction))
    ).scalars().all()
    consume_rows = [t for t in rows if t.type == "consume"]
    assert len(consume_rows) == 1
    assert consume_rows[0].billed is False
    assert consume_rows[0].amount == Decimal("0")


# ================= 余额门控 =================


async def test_check_can_chat_gate(db_session, user, admin):
    # 0 余额 → 拒绝
    with pytest.raises(BusinessException) as e:
        await BillingService.check_can_chat(db_session, user)
    assert e.value.code == ErrorCode.INSUFFICIENT_BALANCE

    # admin 豁免
    await BillingService.check_can_chat(db_session, admin)

    # 充值后放行
    await BillingService.credit(db_session, user_id=user.id, amount=Decimal("10"))
    await BillingService.check_can_chat(db_session, user)

    # frozen → 拒绝
    acc = (
        await db_session.execute(
            select(BillingAccount).where(BillingAccount.user_id == user.id)
        )
    ).scalar_one()
    acc.status = "frozen"
    await db_session.commit()
    with pytest.raises(BusinessException) as e2:
        await BillingService.check_can_chat(db_session, user)
    assert e2.value.code == ErrorCode.ACCOUNT_FROZEN


async def test_chat_endpoint_gate_insufficient_balance(user_client, db_session, user):
    """余额不足时 /api/chat/message 在 agent 初始化前被拦截。"""
    resp = await user_client.post("/api/chat/message", json={"message": "hi"})
    assert biz_code(resp) == ErrorCode.INSUFFICIENT_BALANCE


# ================= 充值下单（自动到账备用流程） =================


async def test_recharge_application_auto_confirm(user_client, admin_client, db_session, user):
    """未配置支付网关回退自动到账：用户提交申请即入账，无需管理员核销。"""
    data = unwrap(
        await user_client.post(
            "/api/billing/recharge-applications",
            json={"amount": 50, "method": "wechat", "note": "测试充值"},
        )
    )
    app = data["app"]
    assert data["qr_code_url"] == ""
    assert app["status"] == "confirmed"
    assert await _balance(db_session, user) == Decimal("50")
    recharges = (
        await db_session.execute(
            select(BillingTransaction).where(
                BillingTransaction.type == "recharge",
                BillingTransaction.source == "recharge",
            )
        )
    ).scalars().all()
    assert len(recharges) == 1
    assert recharges[0].amount == Decimal("50")
    assert "自动到账" in (recharges[0].description or "")


async def test_recharge_application_manual_review(
    user_client, admin_client, db_session, user, monkeypatch
):
    """审核模式（RECHARGE_AUTO_CONFIRM=False）：提交后待核销，管理员确认才到账。"""
    from app.config import settings

    monkeypatch.setattr(settings, "RECHARGE_AUTO_CONFIRM", False)

    data = unwrap(
        await user_client.post(
            "/api/billing/recharge-applications",
            json={"amount": 50, "method": "wechat", "note": "测试充值"},
        )
    )
    app = data["app"]
    assert app["status"] == "pending"
    assert await _balance(db_session, user) == Decimal("0")

    # 管理员确认 → 入账
    out = unwrap(
        await admin_client.post(
            f"/api/admin/billing/applications/{app['id']}/review",
            json={"approve": True},
        )
    )
    assert out["status"] == "confirmed"
    assert await _balance(db_session, user) == Decimal("50")

    # 拒绝另一个 → 余额不变
    data2 = unwrap(
        await user_client.post(
            "/api/billing/recharge-applications",
            json={"amount": 30, "method": "alipay"},
        )
    )
    app2 = data2["app"]
    out2 = unwrap(
        await admin_client.post(
            f"/api/admin/billing/applications/{app2['id']}/review",
            json={"approve": False, "review_note": "未收到款项"},
        )
    )
    assert out2["status"] == "rejected"
    assert await _balance(db_session, user) == Decimal("50")

    # 重复核销已处理的申请 → 拒绝
    resp = await admin_client.post(
        f"/api/admin/billing/applications/{app['id']}/review", json={"approve": True}
    )
    assert biz_code(resp) != 0


# ================= 管理员加量 =================


async def test_admin_grant_and_my_billing(user_client, admin_client, db_session, user):
    out = unwrap(
        await admin_client.post(
            f"/api/admin/users/{user.id}/billing/grant",
            json={"amount": 30, "reason": "体验补偿"},
        )
    )
    assert float(out["balance"]) == 30.0
    assert await _balance(db_session, user) == Decimal("30")

    # 用户端余额查询（含单价）
    me = unwrap(await user_client.get("/api/billing/me"))
    assert float(me["balance"]) == 30.0
    assert float(me["pricing"]["input_price"]) == 3.0
    assert float(me["pricing"]["output_price"]) == 10.0
    assert float(me["pricing"]["cache_read_price"]) == 0.3

    # 流水列表
    tx = unwrap(await user_client.get("/api/billing/transactions?page=1&size=20"))
    assert tx["total"] >= 1
    assert tx["items"][0]["type"] == "grant"


# ================= 注册赠送（首批 150 名） =================


async def test_registration_bonus(client, db_session):
    # conftest 已建 1 个用户（fixture），新注册在 150 名内 → 自动送 50 元
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13700009999", "password": "pass123456", "name": "新用户"},
    )
    data = unwrap(resp)
    assert data and data.get("id")

    coupons = (
        await db_session.execute(
            select(BillingTransaction).where(BillingTransaction.source == "coupon")
        )
    ).scalars().all()
    assert len(coupons) == 1
    assert coupons[0].amount == Decimal("50")
    assert "首批" in (coupons[0].description or "")


async def test_registration_no_bonus_when_disabled(client, db_session, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "REGISTRATION_BONUS_ENABLED", False)
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13700009999", "password": "pass123456"},
    )
    unwrap(resp)
    coupons = (
        await db_session.execute(
            select(BillingTransaction).where(BillingTransaction.source == "coupon")
        )
    ).scalars().all()
    assert coupons == []


async def test_backfill_registration_bonus_existing_users(db_session, user):
    """既有注册用户（含功能上线前注册的）回填前 N 名代金券，幂等。"""
    assert await _balance(db_session, user) == Decimal("0")
    granted = await BillingService.backfill_registration_bonus(db_session)
    assert granted == 1
    assert await _balance(db_session, user) == Decimal("50")

    # 幂等：已发放过不再发
    granted2 = await BillingService.backfill_registration_bonus(db_session)
    assert granted2 == 0
    assert await _balance(db_session, user) == Decimal("50")


# ================= 检索类模型成本（embedding / rerank） =================


async def test_consume_search_cost(db_session, user):
    """检索成本计费：embedding 用 0.5、rerank 用 0.6 元/百万输入 token。"""
    await BillingService.credit(db_session, user_id=user.id, amount=Decimal("10"))
    charge = await BillingService.consume_search_cost(
        db_session,
        user_id=user.id,
        source="kb_search",
        embedding_tokens=1000,
        rerank_tokens=200000,
    )
    # 1000×0.5/1e6 + 200000×0.6/1e6 = 0.0005 + 0.12 = 0.1205
    assert charge == Decimal("0.1205")
    assert await _balance(db_session, user) == Decimal("9.8795")

    rows = (
        await db_session.execute(
            select(BillingTransaction).where(BillingTransaction.source == "kb_search")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].amount == Decimal("-0.1205")
    assert rows[0].input_tokens == 201000

    # 零 token 不记账
    charge2 = await BillingService.consume_search_cost(
        db_session, user_id=user.id, source="exercise_search"
    )
    assert charge2 == Decimal("0")


async def test_pricing_includes_embedding_rerank(user_client, db_session):
    """/billing/me 单价含 embedding/rerank。"""
    me = unwrap(await user_client.get("/api/billing/me"))
    assert float(me["pricing"]["embedding_price"]) == 0.5
    assert float(me["pricing"]["rerank_price"]) == 0.6


# ================= 虎皮椒订单机制 =================


def test_xunhupay_sign():
    """签名算法：非空参数按键排序以 & 拼接 + appsecret，md5 小写。"""
    import hashlib

    params = {"appid": "app-1", "trade_order_id": "RC1", "time": "12345", "attach": ""}
    sig = sign_params(params, "secret")
    raw = "appid=app-1&time=12345&trade_order_id=RC1secret"
    assert sig == hashlib.md5(raw.encode("utf-8")).hexdigest()


async def test_settle_order_idempotent(db_session, user):
    """回调入账幂等：重复回调不重复发放额度。"""
    order = RechargeApplication(
        user_id=user.id,
        app_no="RCIDEMPOTENT1",
        trade_order_id="RCIDEMPOTENT1",
        amount=Decimal("30"),
        status="pending",
    )
    db_session.add(order)
    await db_session.commit()

    ok = await BillingService.settle_order(db_session, "RCIDEMPOTENT1", "txn-1")
    assert ok
    assert await _balance(db_session, user) == Decimal("30")

    # 幂等：重复回调仍返回 True，但不重复入账
    ok2 = await BillingService.settle_order(db_session, "RCIDEMPOTENT1", "txn-1")
    assert ok2
    assert await _balance(db_session, user) == Decimal("30")
    recharges = (
        await db_session.execute(
            select(BillingTransaction).where(BillingTransaction.type == "recharge")
        )
    ).scalars().all()
    assert len(recharges) == 1


async def test_pay_notify_endpoint(client, db_session, user, monkeypatch):
    """虎皮椒回调端点：验签通过后自动到账；验签失败不发放；重复回调幂等。"""
    from app.config import settings

    monkeypatch.setattr(settings, "XUNHUPAY_APPID", "test-appid")
    monkeypatch.setattr(settings, "XUNHUPAY_APP_SECRET", "test-secret")
    monkeypatch.setattr(settings, "XUNHUPAY_NOTIFY_URL", "http://test/notify")

    order = RechargeApplication(
        user_id=user.id,
        app_no="RCNOTIFY1",
        trade_order_id="RCNOTIFY1",
        amount=Decimal("20"),
        status="pending",
    )
    db_session.add(order)
    await db_session.commit()

    # 验签失败 → error，不入账
    resp = await client.post(
        "/api/billing/pay/notify",
        data={"trade_order_id": "RCNOTIFY1", "status": "OD", "total_fee": "20", "hash": "bad"},
    )
    assert resp.text == "error"
    assert await _balance(db_session, user) == Decimal("0")

    # 合法回调 → success + 入账
    params = {
        "trade_order_id": "RCNOTIFY1",
        "status": "OD",
        "total_fee": "20",
        "transaction_id": "TXN-1",
        "time": "123",
    }
    params["hash"] = sign_params(params, "test-secret")
    resp = await client.post("/api/billing/pay/notify", data=params)
    assert resp.text == "success"
    assert await _balance(db_session, user) == Decimal("20")

    # 重复回调 → 幂等不重复入账
    resp = await client.post("/api/billing/pay/notify", data=params)
    assert resp.text == "success"
    assert await _balance(db_session, user) == Decimal("20")
