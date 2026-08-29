-- ============================================================
-- 目标闯关系统增量迁移（修复对齐）
-- 日期：2026-08-29
-- 说明：为已上线的 goal_archetypes / goal_milestones 补列，与模型对齐。
--       - goal_archetypes.female_only：女性专属原型过滤（种子已有该字段，此前未建模）
--       - goal_milestones.training_focus：关卡训练重点（此前 SKILL 已依赖，落库时被丢弃）
-- 本地开发 DEBUG=true 时 init_db 的补列逻辑自动处理，无需执行本脚本。
-- 执行方式（服务器）：
--   docker exec -i fitcream-postgres psql -U <user> -d <db> < 2026-08-29_goal_roadmap_fix.sql
-- ============================================================

-- 1. 原型库补 female_only（默认 FALSE，存量原型不视为女性专属）
ALTER TABLE goal_archetypes
    ADD COLUMN IF NOT EXISTS female_only BOOLEAN NOT NULL DEFAULT FALSE;

-- 1.1 回填已知女性专属原型（种子 JSON 为唯一真源；启动期 seed loader 也会幂等同步）
UPDATE goal_archetypes
    SET female_only = TRUE
    WHERE key = 'toned_curves' AND NOT female_only;

-- 2. 关卡补 training_focus（可空，存量关卡无训练重点，由后续路线图设计回填）
ALTER TABLE goal_milestones
    ADD COLUMN IF NOT EXISTS training_focus VARCHAR(200);
