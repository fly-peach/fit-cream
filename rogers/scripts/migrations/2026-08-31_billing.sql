-- ============================================================
-- 计费系统迁移脚本（钱包 / 流水 / 单价 / 套餐 / 充值申请）
-- 日期：2026-08-31
-- 说明：新增 5 张表，全部为新表（无存量数据迁移）。
--       金额以「元」为单位的 NUMERIC(12,4)。
-- 生产环境（DEBUG=false）部署重启之前手动执行本 SQL；
-- 本地开发（DEBUG=true）由 init_db 的 create_all 自动建表。
-- 执行方式（服务器）：
--   docker exec -i fitcream-postgres psql -U <user> -d <db> < 2026-08-31_billing.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS billing_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    balance NUMERIC(12,4) NOT NULL DEFAULT 0,
    total_recharged NUMERIC(12,4) NOT NULL DEFAULT 0,
    total_granted NUMERIC(12,4) NOT NULL DEFAULT 0,
    total_consumed NUMERIC(12,4) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'normal',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_billing_accounts_user_id ON billing_accounts(user_id);

CREATE TABLE IF NOT EXISTS billing_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL,
    amount NUMERIC(12,4) NOT NULL,
    balance_after NUMERIC(12,4) NOT NULL,
    source VARCHAR(30) NOT NULL,
    model_provider VARCHAR(20) NOT NULL DEFAULT 'qwen',
    billed BOOLEAN NOT NULL DEFAULT TRUE,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    reasoning_tokens INTEGER NOT NULL DEFAULT 0,
    estimated BOOLEAN NOT NULL DEFAULT FALSE,
    description VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_billing_transactions_user_created
    ON billing_transactions(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS billing_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model VARCHAR(50) NOT NULL DEFAULT 'qwen3.8-flash',
    input_price NUMERIC(12,6) NOT NULL,
    output_price NUMERIC(12,6) NOT NULL,
    cache_read_price NUMERIC(12,6) NOT NULL DEFAULT 0,
    cache_write_price NUMERIC(12,6) NOT NULL DEFAULT 0,
    cost_input_price NUMERIC(12,6) NOT NULL DEFAULT 0.8,
    cost_output_price NUMERIC(12,6) NOT NULL DEFAULT 2.7,
    cost_cache_read_price NUMERIC(12,6) NOT NULL DEFAULT 0.1,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS billing_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    bonus NUMERIC(12,2) NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recharge_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app_no VARCHAR(32) NOT NULL UNIQUE,
    trade_order_id VARCHAR(32),
    pay_transaction_id VARCHAR(64),
    amount NUMERIC(12,2) NOT NULL,
    method VARCHAR(20) NOT NULL DEFAULT 'wechat',
    note VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    review_note VARCHAR(255),
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_recharge_applications_user_id ON recharge_applications(user_id);
CREATE INDEX IF NOT EXISTS ix_recharge_applications_status ON recharge_applications(status);
CREATE INDEX IF NOT EXISTS ix_recharge_applications_trade_order_id
    ON recharge_applications(trade_order_id);

-- 幂等补列（已在存量库上执行过旧版建表语句时补齐订单字段）
ALTER TABLE recharge_applications
    ADD COLUMN IF NOT EXISTS trade_order_id VARCHAR(32),
    ADD COLUMN IF NOT EXISTS pay_transaction_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_recharge_applications_trade_order_id
    ON recharge_applications(trade_order_id);
