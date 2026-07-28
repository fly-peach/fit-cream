# 用户表

## users — 用户表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| phone | String(20) | UNIQUE, NOT NULL, 索引 | 登录手机号 |
| email | String(255) | UNIQUE, nullable | 可选邮箱 |
| password_hash | String(255) | NOT NULL | bcrypt 哈希 |
| name | String(100) | nullable | 显示名称 |
| age | Integer | nullable | 年龄 |
| gender | String(10) | nullable | male / female / other |
| role | String(20) | NOT NULL, default="user" | user / admin |
| is_active | Boolean | NOT NULL, default=True | 账号是否启用 |
| is_verified | Boolean | NOT NULL, default=False | 是否已验证手机号 |
| last_login_at | TIMESTAMPTZ | nullable | 最后登录时间 |
| last_login_ip | VARCHAR(50) | nullable | 最后登录 IP |
| deleted_at | TIMESTAMPTZ | nullable | 软删除时间 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |
| updated_at | TIMESTAMPTZ | server_default=now(), onupdate=now() | 更新时间 |

关系：一对一 -> user_settings；一对多 -> plans, diet_plans, checkins, knowledge_bases, conversations, thread_metas, thread_usages, health_metrics, diet_meals, daily_diet_summaries, custom_food_items

说明：
- phone 是唯一的登录标识，注册和登录均使用手机号
- password_hash 使用 bcrypt 12 轮哈希，输入密码截断 72 字节
- height/weight/goal 等业务字段已迁移至 user_settings 和 health_metrics

## user_settings — 用户设置表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id CASCADE, UNIQUE, 索引 | 用户 ID |
| goal | String(50) | nullable | lose_fat / gain_muscle / maintain / improve_health |
| target_weight_kg | Numeric(5,2) | nullable | 目标体重(kg) |
| target_body_fat_pct | Numeric(4,2) | nullable | 目标体脂百分比 |
| weekly_training_goal | Integer | default 5 | 每周训练目标次数 |
| calorie_goal | Integer | default 2000 | 每日目标卡路里 |
| protein_goal_g | Integer | default 150 | 每日蛋白质目标(克) |
| carbs_goal_g | Integer | default 250 | 每日碳水目标(克) |
| fat_goal_g | Integer | default 65 | 每日脂肪目标(克) |
| notification_enabled | Boolean | default True | 是否启用通知 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |
| updated_at | TIMESTAMPTZ | server_default=now(), onupdate=now() | 更新时间 |

## health_metrics — 健康指标历史表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id CASCADE, 索引 | 用户 ID |
| measure_date | Date | NOT NULL, 索引 | 测量日期 |
| height_cm | Numeric(5,2) | nullable | 身高(cm) |
| weight_kg | Numeric(5,2) | nullable | 体重(kg) |
| body_fat_pct | Numeric(4,2) | nullable | 体脂百分比 |
| muscle_mass_kg | Numeric(5,2) | nullable | 肌肉量(kg) |
| bmi | Numeric(4,2) | nullable | BMI |
| bmi_status | String(20) | nullable | BMI 分类：偏瘦/正常/偏胖/肥胖 |
| chest_cm | Numeric(5,2) | nullable | 胸围(cm) |
| waist_cm | Numeric(5,2) | nullable | 腰围(cm) |
| hip_cm | Numeric(5,2) | nullable | 臀围(cm) |
| arm_cm | Numeric(5,2) | nullable | 臂围(cm) |
| thigh_cm | Numeric(5,2) | nullable | 腿围(cm) |
| note | String(500) | nullable | 备注 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |

## refresh_token_blacklist — 令牌黑名单表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| jti | VARCHAR(36) | UNIQUE, NOT NULL, 索引 | JWT ID |
| user_id | UUID | FK->users.id CASCADE, NOT NULL, 索引 | 所属用户 |
| expires_at | TIMESTAMPTZ | NOT NULL | 令牌过期时间 |
| revoked_at | TIMESTAMPTZ | server_default=now() | 撤销时间 |
| reason | VARCHAR(200) | nullable | 撤销原因 |

说明：logout 时将 refresh_token 的 jti 加入黑名单，refresh 前检查黑名单。

## login_attempts — 登录尝试表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id SET NULL, nullable, 索引 | 所属用户（未登录时为 NULL） |
| phone | VARCHAR(20) | NOT NULL, 索引 | 登录手机号 |
| ip | VARCHAR(50) | nullable | 登录 IP |
| success | Boolean | default=False | 是否成功 |
| attempted_at | TIMESTAMPTZ | server_default=now() | 尝试时间 |

说明：每次登录尝试（成功/失败）均记录。连续 5 次失败锁定 15 分钟（可配置）。

## user_audit_logs — 用户审计日志表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id CASCADE, NOT NULL, 索引 | 用户 ID |
| action | VARCHAR(50) | NOT NULL | 操作类型（register/login/change_password/logout） |
| ip | VARCHAR(50) | nullable | 客户端 IP |
| user_agent | VARCHAR(500) | nullable | User-Agent |
| detail | Text | nullable | 操作详情 |
| created_at | TIMESTAMPTZ | server_default=now() | 记录时间 |

## verification_codes — 验证码表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id SET NULL, nullable, 索引 | 用户 ID |
| phone | VARCHAR(20) | nullable, 索引 | 手机号 |
| email | VARCHAR(255) | nullable | 邮箱 |
| code | VARCHAR(10) | NOT NULL | 验证码 |
| code_type | VARCHAR(20) | NOT NULL | register / login / reset_password |
| expires_at | TIMESTAMPTZ | NOT NULL | 过期时间 |
| used_at | TIMESTAMPTZ | nullable | 使用时间 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |

说明：支持短信和邮箱验证码。发送前检查冷却期（60秒）和每小时上限（5次），验证后设置 used_at。

## diet_meals — 每餐记录表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id CASCADE, NOT NULL, 索引 | 用户 ID |
| meal_date | Date | NOT NULL, 索引 | 用餐日期 |
| meal_type | VARCHAR(20) | NOT NULL | breakfast / lunch / dinner / snack |
| food_name | VARCHAR(200) | NOT NULL | 食物名称 |
| portion | VARCHAR(100) | nullable | 份量描述 |
| custom_food_item_id | UUID | FK->custom_food_items.id, nullable | 关联自定义食物 |
| calories | Integer | default=0 | 卡路里 |
| protein_g | NUMERIC(6,1) | nullable | 蛋白质(克) |
| carbs_g | NUMERIC(6,1) | nullable | 碳水(克) |
| fat_g | NUMERIC(6,1) | nullable | 脂肪(克) |
| note | Text | nullable | 备注 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |
| updated_at | TIMESTAMPTZ | server_default=now(), onupdate=now() | 更新时间 |

## daily_diet_summaries — 每日营养汇总表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id CASCADE, NOT NULL, 索引 | 用户 ID |
| summary_date | Date | NOT NULL, 索引, UNIQUE(user_id, summary_date) | 汇总日期 |
| total_calories | Integer | default=0 | 总卡路里 |
| total_protein_g | NUMERIC(6,1) | default=0 | 总蛋白质(克) |
| total_carbs_g | NUMERIC(6,1) | default=0 | 总碳水(克) |
| total_fat_g | NUMERIC(6,1) | default=0 | 总脂肪(克) |
| protein_goal_met | Boolean | default=False | 蛋白质目标达成 |
| carbs_goal_met | Boolean | default=False | 碳水目标达成 |
| fat_goal_met | Boolean | default=False | 脂肪目标达成 |
| meal_count | Integer | default=0 | 当日餐数 |
| note | VARCHAR(500) | nullable | 备注 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |
| updated_at | TIMESTAMPTZ | server_default=now(), onupdate=now() | 更新时间 |

说明：按 (user_id, summary_date) 唯一，每次创建/更新/删除 DietMeal 时自动重新计算。

## custom_food_items — 自定义食物表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id CASCADE, NOT NULL, 索引 | 用户 ID |
| name | VARCHAR(200) | NOT NULL, 索引 | 食物名称 |
| category | VARCHAR(50) | nullable, 索引 | 分类 |
| portion | VARCHAR(100) | NOT NULL | 份量（如 "100g"） |
| calories_per_portion | Integer | NOT NULL | 每份卡路里 |
| protein_g_per_portion | NUMERIC(6,1) | nullable | 每份蛋白质(克) |
| carbs_g_per_portion | NUMERIC(6,1) | nullable | 每份碳水(克) |
| fat_g_per_portion | NUMERIC(6,1) | nullable | 每份脂肪(克) |
| note | Text | nullable | 备注 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |
| updated_at | TIMESTAMPTZ | server_default=now(), onupdate=now() | 更新时间 |
