-- ============================================================
-- 目标闯关系统（Goal Roadmap）迁移脚本
-- 日期：2026-08-28
-- 说明：生产环境 DEBUG=false，init_db() 直接 return，需在部署重启之前
--       手动执行本 SQL（lifespan 的 seed loader 启动时灌入知识层数据）。
--       本地开发 DEBUG=true 时 init_db 自动建表，无需执行本脚本。
-- 执行方式（服务器）：
--   docker exec -i fitcream-postgres psql -U <user> -d <db> < 2026-08-28_goal_roadmap.sql
-- ============================================================

-- 1. 知识层：身材原型库
CREATE TABLE goal_archetypes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    tagline VARCHAR(200),
    description TEXT,
    target_metrics JSONB NOT NULL,
    training_bias VARCHAR(50),
    diet_bias VARCHAR(50),
    stage_hint JSONB,
    stage_narrative_hint JSONB,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- 2. 知识层：力量标准表
CREATE TABLE strength_standards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gender VARCHAR(10) NOT NULL,
    lift VARCHAR(20) NOT NULL,
    level VARCHAR(20) NOT NULL,
    bw_multiplier NUMERIC(4,2) NOT NULL,
    UNIQUE (gender, lift, level)
);

-- 3. 知识层：进度速率表
CREATE TABLE progress_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experience_level VARCHAR(20) NOT NULL,
    metric VARCHAR(30) NOT NULL,
    monthly_min NUMERIC(6,2) NOT NULL,
    monthly_max NUMERIC(6,2) NOT NULL,
    unit VARCHAR(10) NOT NULL,
    note VARCHAR(200)
);

-- 4. 知识层：安全限值表
CREATE TABLE goal_safety_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric VARCHAR(30) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    floor_value NUMERIC(6,2),
    ceiling_value NUMERIC(6,2),
    note VARCHAR(200),
    UNIQUE (metric, gender)
);

-- 5. 业务层：闯关路线图
CREATE TABLE goal_roadmaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    archetype_key VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    target_metrics JSONB NOT NULL DEFAULT '[]',
    horizon_months INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_goal_roadmaps_user ON goal_roadmaps(user_id);

-- 6. 业务层：关卡
CREATE TABLE goal_milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    roadmap_id UUID NOT NULL REFERENCES goal_roadmaps(id) ON DELETE CASCADE,
    stage_index INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    exit_criteria JSONB NOT NULL DEFAULT '[]',
    expected_weeks INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'locked',
    achieved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_goal_milestones_roadmap ON goal_milestones(roadmap_id);

-- 7. 业务层：力量/围度基线记录
CREATE TABLE performance_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lift VARCHAR(20) NOT NULL,
    test_type VARCHAR(20) NOT NULL DEFAULT '1rm',
    value NUMERIC(6,2) NOT NULL,
    bodyweight_kg NUMERIC(5,2),
    tested_at DATE NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'chat',
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_performance_tests_user ON performance_tests(user_id, lift, tested_at DESC);

-- 8. 既有表：plans 增 milestone_id（可空，向后兼容）
ALTER TABLE plans ADD COLUMN milestone_id UUID REFERENCES goal_milestones(id) ON DELETE SET NULL;
CREATE INDEX ix_plans_milestone ON plans(milestone_id);
