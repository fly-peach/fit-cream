# 训练计划数据库设计

FitCream 使用 PostgreSQL 数据库，通过 SQLAlchemy ORM 管理。本文件涵盖训练计划、动作库、打卡、用户、对话相关数据表。

## 用户体系

### users — 用户表

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
| created_at | DateTime(tz) | server_default=now() | 创建时间 |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() | 更新时间 |

关系：一对一 -> settings；一对多 -> plans, diet_plans, checkins, knowledge_bases, conversations, thread_metas, thread_usages, health_metrics

### user_settings — 用户设置表

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
| created_at | DateTime(tz) | server_default=now() | 创建时间 |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() | 更新时间 |

关系：一对一 -> user

### health_metrics — 健康指标历史表

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
| created_at | DateTime(tz) | server_default=now() | 创建时间 |

关系：多对一 -> user

## 训练计划体系

### plans — 训练计划表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK->users.id CASCADE, 索引 | 所属用户 |
| name | String(200) | NOT NULL | 计划名称 |
| goal | String(50) | nullable | 目标类型 |
| difficulty | String(20) | nullable | beginner / intermediate / advanced |
| weeks | Integer | nullable | 计划周数 |
| status | String(20) | default="active" | active / archived / completed |
| created_at | DateTime(tz) | server_default=now() | |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() | |

关系：一对多 -> plan_days（CASCADE 删除）

### plan_days — 训练日表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| plan_id | UUID | FK->plans.id CASCADE, 索引 | 所属计划 |
| day_of_week | Integer | NOT NULL | 1=周一 ... 7=周日 |
| focus | String(100) | nullable | 训练重点，如"胸部 + 三头" |
| rest_seconds | Integer | default 60 | 组间休息(秒) |
| metadata_ | JSONB | default={} | 自定义扩展 |

关系：一对多 -> plan_day_exercises（CASCADE 删除）

### plan_day_exercises — 训练日动作表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| plan_day_id | UUID | FK->plan_days.id CASCADE, 索引 | |
| exercise_id | UUID | FK->exercises.id, 索引 | 引用动作库 |
| sets | Integer | NOT NULL | 组数 |
| reps | Integer | NOT NULL | 每组的次数 |
| weight_kg | Numeric(6,2) | nullable | 重量(kg) |
| sort_order | Integer | default 0 | 排序 |
| notes | Text | nullable | 执行提示 |
| metadata_ | JSONB | default={} | |

### exercises — 动作库

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | String(200) | NOT NULL, 索引 | 动作中文名 |
| name_en | String(200) | nullable | 英文名 |
| muscle_group | String(50) | 索引 | chest/back/legs/shoulders/arms/core/full_body |
| equipment | String(100) | nullable, 索引 | barbell/dumbbell/machine/bodyweight/cable/kettlebell |
| difficulty | String(20) | nullable, 索引 | beginner/intermediate/advanced |
| category | VARCHAR(50) | nullable, 索引 | compound / isolation / cardio / mobility |
| is_compound | Boolean | default=False | 是否复合动作 |
| muscle_subgroup | VARCHAR(50) | nullable | 细分肌群（upper_chest/middle_chest/lower_chest/lats/middle_back/lower_back 等） |
| muscle_subgroup_zh | VARCHAR(50) | nullable | 细分肌群（中文） |
| calories_per_min | NUMERIC(6,1) | nullable | 每分钟消耗热量估算(kcal) |
| instructions | Text | nullable | 执行步骤说明 |
| tips | Text | nullable | 注意事项/常见错误 |
| description | Text | nullable | 动作说明 |
| body_part | VARCHAR(50) | nullable, 索引 | dataset 原始身体部位（细分） |
| body_part_zh | VARCHAR(50) | nullable | 原始身体部位（中文） |
| target | VARCHAR(50) | nullable, 索引 | 目标肌群（英文） |
| target_zh | VARCHAR(50) | nullable | 目标肌群（中文） |
| secondary_muscles | JSONB | nullable | 次要肌群（英文） |
| secondary_muscles_zh | JSONB | nullable | 次要肌群（中文） |
| instruction_steps | JSONB | nullable | 编号步骤（中文） |
| instruction_steps_en | JSONB | nullable | 编号步骤（英文） |
| instructions_en | Text | nullable | 英文执行说明 |
| equipment_zh | VARCHAR(100) | nullable | 器械（中文） |
| media_id | VARCHAR(100) | nullable | 媒体库 ID（Gym Visual） |
| image | VARCHAR(255) | nullable | 静态缩略图 URL |
| gif_url | VARCHAR(255) | nullable | 动图演示 URL |
| attribution | VARCHAR(255) | nullable | 媒体署名 |

说明：动作库含 1324 条 dataset 导入动作，中英双语字段成对存储；`muscle_group` 为 7 值粗分类，由 dataset 的 `body_part` 经 `MUSCLE_GROUP_COARSENING` 映射归并而来，保持 Agent/Plan 消费方零改动。dataset 新增列均 nullable，由 `init_db` 自动 ALTER 补齐。

## 打卡体系

### checkins — 打卡记录表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK->users.id CASCADE | 所属用户（由复合唯一索引覆盖） |
| plan_day_id | UUID | FK->plan_days.id SET NULL, nullable | 关联训练日 |
| date | Date | NOT NULL, 索引 | 训练日期 |
| duration_min | Integer | NOT NULL | 训练时长(分钟) |
| actual_intensity | VARCHAR(20) | nullable | low / medium / high |
| calories_burned | Integer | nullable | 估算消耗热量(kcal) |
| mood | Integer | nullable | 心情评分 1-5 |
| note | Text | nullable | 备注 |
| created_at | DateTime(tz) | server_default=now() | |

唯一约束：`(user_id, date)` - 每人每天仅可打卡一次（该复合唯一索引同时覆盖 user_id 前缀查询，不再冗余创建单列索引）

关系：一对多 -> checkin_exercises（CASCADE 删除）

### checkin_exercises — 打卡动作记录表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| checkin_id | UUID | FK->checkins.id CASCADE, 索引 | |
| exercise_id | UUID | FK->exercises.id, 索引 | |
| sets_done | Integer | nullable | 实际完成组数 |
| reps_done | Integer | nullable | 实际完成次数 |
| weight_kg | Numeric(6,2) | nullable | 使用重量 |
| rpe | Integer | nullable | 自感用力等级 1-10 |
| notes | Text | nullable | 动作备注 |

## 对话体系

### conversations — 对话消息表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK->users.id CASCADE, 索引 | |
| thread_id | String(100) | 索引, nullable | 对话线程标识 |
| role | String(20) | NOT NULL | user / assistant / tool |
| content Text | nullable | 消息内容 |
| metadata_json | JSONB | nullable, GIN 索引 | 元数据（thinking、tool_calls、stopped、images） |
| created_at | DateTime(tz) | server_default=now(), 索引 | |

按 `user_id + thread_id` 组织对话线程。

### thread_metas — 线程元信息表

继承 ThreadBase 混入：id, user_id, thread_id, updated_at

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK->users.id CASCADE, 索引 | |
| thread_id | String(100) | UNIQUE, 索引 | |
| title | String(200) | nullable | 用户自定义标题 |
| created_at | DateTime(tz) | server_default=now() | |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() | |

### thread_usages — 线程 Token 用量表

继承 ThreadBase 混入：id, user_id, thread_id, updated_at

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK->users.id CASCADE, 索引 | |
| thread_id | String(100) | UNIQUE, 索引 | |
| total_tokens | Integer | default=0 | 累积总量 |
| input_tokens | Integer | default=0 | 输入量 |
| output_tokens | Integer | default=0 | 输出量 |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() | |

## 设计原则总结

1. 所有权校验链：所有可变更操作逐级校验 `resource -> parent -> ... -> user_id`
2. 软删除策略：训练计划和饮食计划使用 archived 状态标记删除，对话使用物理 CASCADE 删除
3. 唯一约束：`(user_id, date)` 确保每人每天仅一次打卡
4. 级联策略：父记录删除时子记录自动 CASCADE 删除（SET NULL 仅用于 plan_day_id 的可选关联）
5. 时间戳：各表统一使用带时区的 DateTime 字段，server_default 由数据库端生成
6. 索引策略：equipment/difficulty 加独立索引支持多维度搜索；metadata_json 加 GIN 索引支持 JSON 路径查询

## 饮食记录体系

### diet_meals — 每餐记录表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id CASCADE, NOT NULL, 索引 | 用户 ID |
| custom_food_item_id | UUID | FK->custom_food_items.id, nullable | 关联自定义食物 |
| meal_date | Date | NOT NULL, 索引 | 用餐日期 |
| meal_type | VARCHAR(20) | NOT NULL | breakfast / lunch / dinner / snack |
| food_name | VARCHAR(200) | NOT NULL | 食物名称 |
| portion | VARCHAR(100) | nullable | 份量描述 |
| calories | Integer | default=0 | 卡路里 |
| protein_g | NUMERIC(6,1) | nullable | 蛋白质(克) |
| carbs_g | NUMERIC(6,1) | nullable | 碳水(克) |
| fat_g | NUMERIC(6,1) | nullable | 脂肪(克) |
| note | Text | nullable | 备注 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |
| updated_at | TIMESTAMPTZ | server_default=now(), onupdate=now() | 更新时间 |

### daily_diet_summaries — 每日营养汇总表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id CASCADE, NOT NULL, 索引 | 用户 ID |
| summary_date | Date | NOT NULL, 索引, UNIQUE(user_id+summary_date) | 汇总日期 |
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

说明：每次创建/更新/删除 DietMeal 时自动重新计算。唯一约束确保每个用户每天只有一条汇总。

### custom_food_items — 自定义食物表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| user_id | UUID | FK->users.id CASCADE, NOT NULL, 索引 | 用户 ID |
| name | VARCHAR(200) | NOT NULL, 索引 | 食物名称 |
| category | VARCHAR(50) | nullable, 索引 | 分类 |
| portion | VARCHAR(100) | NOT NULL | 份量描述 |
| calories_per_portion | Integer | NOT NULL | 每份卡路里 |
| protein_g_per_portion | NUMERIC(6,1) | nullable | 每份蛋白质(克) |
| carbs_g_per_portion | NUMERIC(6,1) | nullable | 每份碳水(克) |
| fat_g_per_portion | NUMERIC(6,1) | nullable | 每份脂肪(克) |
| note | Text | nullable | 备注 |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |
| updated_at | TIMESTAMPTZ | server_default=now(), onupdate=now() | 更新时间 |
