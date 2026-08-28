-- ============================================================
-- Intake 健身画像表（user_fitness_profiles）迁移脚本
-- 日期：2026-08-28
-- 说明：生产环境 DEBUG=false，init_db() 直接 return，需在部署重启之前
--       手动执行本 SQL。纯新增表，向后兼容（旧代码不读不写该表），
--       可先执行本 SQL 再部署代码。
--       本地开发 DEBUG=true 时 init_db 自动建表，无需执行本脚本。
-- 执行方式（服务器）：
--   docker exec -i fitcream-postgres psql -U <user> -d <db> < 2026-08-28_user_fitness_profiles.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS user_fitness_profiles (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    medical_history TEXT,
    injuries TEXT,
    allergies VARCHAR(500),
    pregnancy VARCHAR(200),
    medication VARCHAR(500),
    parq_result VARCHAR(20),
    doctor_advice VARCHAR(500),
    training_experience VARCHAR(20),
    cardio_level VARCHAR(20),
    strength_level VARCHAR(20),
    flexibility VARCHAR(20),
    body_fat_pct NUMERIC(4,1),
    weekly_frequency VARCHAR(10),
    session_duration VARCHAR(10),
    preferred_types VARCHAR(500),
    past_results TEXT,
    occupation_schedule VARCHAR(500),
    diet_habits TEXT,
    sleep_quality VARCHAR(10),
    stress_level VARCHAR(10),
    equipment VARCHAR(500),
    preferred_time VARCHAR(10),
    diet_preferences VARCHAR(500),
    food_allergies VARCHAR(500),
    cooking_condition VARCHAR(500),
    meals_per_day VARCHAR(10),
    eating_out_ratio VARCHAR(20),
    budget VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_fitness_profiles_user ON user_fitness_profiles(user_id);
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_parq_result
  CHECK (parq_result IS NULL OR parq_result IN ('low','uncertain','high'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_training_experience
  CHECK (training_experience IS NULL OR training_experience IN ('never','beginner','intermediate','advanced'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_cardio_level
  CHECK (cardio_level IS NULL OR cardio_level IN ('beginner','intermediate','advanced'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_strength_level
  CHECK (strength_level IS NULL OR strength_level IN ('beginner','intermediate','advanced'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_flexibility
  CHECK (flexibility IS NULL OR flexibility IN ('limited','normal','good'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_weekly_frequency
  CHECK (weekly_frequency IS NULL OR weekly_frequency IN ('0','1-2','3-4','5+'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_session_duration
  CHECK (session_duration IS NULL OR session_duration IN ('<30','30-60','>60'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_sleep_quality
  CHECK (sleep_quality IS NULL OR sleep_quality IN ('poor','normal','good'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_stress_level
  CHECK (stress_level IS NULL OR stress_level IN ('low','medium','high'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_preferred_time
  CHECK (preferred_time IS NULL OR preferred_time IN ('morning','noon','evening','flexible'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_meals_per_day
  CHECK (meals_per_day IS NULL OR meals_per_day IN ('2','3','4','5+'));
ALTER TABLE user_fitness_profiles ADD CONSTRAINT ck_user_fitness_profiles_eating_out_ratio
  CHECK (eating_out_ratio IS NULL OR eating_out_ratio IN ('mostly_out','half','mostly_home'));
