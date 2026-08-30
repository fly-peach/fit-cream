-- ============================================================
-- 身材原型库 v2（动作组产品功能）迁移脚本
-- 日期：2026-08-30
-- 说明：goal_archetypes 从「一行一原型 + 内嵌男女拆分」升级为
--       「一行 = 一个 (key, gender) + 扁平字段」，并新增
--       image / target_exercises / target_exercise_goal 三个展示字段（列名与 JSON 键一致）。
--       知识表由种子全量重灌（seed loader 启动时按 (key,gender) upsert），
--       故此处直接清空存量行；goal_roadmaps 仅冗余 archetype_key 字符串
--       与自持 target_metrics 快照，无外键依赖，不受影响。
-- 生产环境（DEBUG=false）在部署重启之前手动执行本 SQL；
-- 本地开发（DEBUG=true）由 init_db 的幂等 DDL 自动处理。
-- 执行方式（服务器）：
--   docker exec -i fitcream-postgres psql -U <user> -d <db> < 2026-08-30_goal_archetype_v2.sql
-- ============================================================

-- 1. 新增列（IF NOT EXISTS 幂等）
ALTER TABLE goal_archetypes
    ADD COLUMN IF NOT EXISTS gender VARCHAR(10) NOT NULL DEFAULT 'male',
    ADD COLUMN IF NOT EXISTS image VARCHAR(300),
    ADD COLUMN IF NOT EXISTS target_exercises JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS target_exercise_goal JSONB NOT NULL DEFAULT '[]'::jsonb;

-- 2. 清空存量行（种子重灌），并把男女拆分列的类型收敛为扁平类型
DELETE FROM goal_archetypes;

ALTER TABLE goal_archetypes
    ALTER COLUMN stage_hint TYPE VARCHAR(50) USING stage_hint::text,
    ALTER COLUMN stage_narrative_hint TYPE TEXT USING stage_narrative_hint::text;

-- 3. 旧列与旧约束下线
ALTER TABLE goal_archetypes DROP COLUMN IF EXISTS female_only;
ALTER TABLE goal_archetypes DROP CONSTRAINT IF EXISTS goal_archetypes_key_key;

-- 4. 新唯一约束 (key, gender)
ALTER TABLE goal_archetypes DROP CONSTRAINT IF EXISTS uq_goal_archetypes_key_gender;
ALTER TABLE goal_archetypes
    ADD CONSTRAINT uq_goal_archetypes_key_gender UNIQUE (key, gender);
