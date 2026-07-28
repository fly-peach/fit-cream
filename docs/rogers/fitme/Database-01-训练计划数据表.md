# 训练计划数据库设计

FitCream 使用 PostgreSQL 数据库，通过 SQLAlchemy ORM 管理。本文件涵盖训练计划、动作库、打卡、用户、对话相关数据表。

## 用户体系

### users - 用户表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| phone | String(20) | UNIQUE, NOT NULL, 索引 | 登录手机号 |
| email | String(255) | UNIQUE, nullable | 可选邮箱 |
| password_hash | String(255) | NOT NULL | bcrypt 哈希 |
| name | String(100) | nullable | 显示名称 |
| height_cm | Numeric(5,2) | nullable | 身高(cm) |
| weight_kg | Numeric(5,2) | nullable | 体重(kg) |
| age | Integer | nullable | 年龄 |
| gender | String(10) | nullable | male / female / other |
| role | String(20) | NOT NULL, default="user" | user / admin |
| goal | String(50) | nullable | lose_fat / gain_muscle / maintain / improve_health |
| created_at | DateTime(tz) | server_default=now() | 创建时间 |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() | 更新时间 |

关系：一对多 -> plans, diet_plans, checkins, achievements, knowledge_bases, conversations, thread_metas, thread_usages

### achievements - 成就表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK->users.id CASCADE, 索引 | |
| type | String(50) | NOT NULL | 成就类型枚举 |
| name | String(100) | nullable | 显示名称 |
| description | String(255) | nullable | 描述 |
| icon | String(50) | nullable | 图标标识 |
| unlocked_at | DateTime(tz) | server_default=now() | 解锁时间 |

唯一约束：`(user_id, type)`

成就类型映射：

| type | name | 触发条件 |
|------|------|----------|
| streak_7 | 连续7天 | 连续打卡7天 |
| streak_30 | 连续30天 | 连续打卡30天 |
| streak_100 | 连续100天 | 连续打卡100天 |
| first_plan | 第一个计划 | 首次创建计划 |
| total_50_workouts | 累计50次训练 | 打卡总数达50 |
| total_100_workouts | 累计100次训练 | 打卡总数达100 |

## 训练计划体系

### plans - 训练计划表

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

### plan_days - 训练日表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| plan_id | UUID | FK->plans.id CASCADE, 索引 | 所属计划 |
| day_of_week | Integer | NOT NULL | 1=周一 ... 7=周日 |
| focus | String(100) | nullable | 训练重点，如"胸部 + 三头" |
| rest_seconds | Integer | default=60 | 组间休息(秒) |
| metadata_ | JSONB | default={} | 自定义扩展 |

关系：一对多 -> plan_day_exercises（CASCADE 删除）

### plan_day_exercises - 训练日动作表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| plan_day_id | UUID | FK->plan_days.id CASCADE, 索引 | |
| exercise_id | UUID | FK->exercises.id, 索引 | 引用动作库 |
| sets | Integer | NOT NULL | 组数 |
| reps | Integer | NOT NULL | 每组的次数 |
| weight_kg | Numeric(6,2) | nullable | 重量(kg) |
| sort_order | Integer | default=0 | 排序 |
| notes | Text | nullable | 执行提示 |
| metadata_ | JSONB | default={} | |

### exercises - 动作库

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | String(200) | NOT NULL, 索引 | 动作中文名 |
| name_en | String(200) | nullable | 英文名 |
| muscle_group | String(50) | 索引 | chest/back/legs/shoulders/arms/core/full_body |
| equipment | String(100) | nullable, 索引 | barbell/dumbbell/machine/bodyweight/cable/kettlebell |
| difficulty | String(20) | nullable, 索引 | beginner/intermediate/advanced |
| description | Text | nullable | 动作说明 |

## 打卡体系

### checkins - 打卡记录表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK->users.id CASCADE | 所属用户（由复合唯一索引覆盖） |
| plan_day_id | UUID | FK->plan_days.id SET NULL, nullable | 关联训练日 |
| date | Date | NOT NULL, 索引 | 训练日期 |
| duration_min | Integer | NOT NULL | 训练时长(分钟) |
| mood | Integer | nullable | 心情评分 1-5 |
| note | Text | nullable | 备注 |
| created_at | DateTime(tz) | server_default=now() | |

唯一约束：`(user_id, date)` - 每人每天仅可打卡一次（该复合唯一索引同时覆盖 user_id 前缀查询）

关系：一对多 -> checkin_exercises（CASCADE 删除）

### checkin_exercises - 打卡动作记录表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| checkin_id | UUID | FK->checkins.id CASCADE, 索引 | |
| exercise_id | UUID | FK->exercises.id, 索引 | |
| sets_done | Integer | nullable | 实际完成组数 |
| reps_done | Integer | nullable | 实际完成次数 |
| weight_kg | Numeric(6,2) | nullable | 使用重量 |

## 对话体系

### conversations - 对话消息表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK->users.id CASCADE, 索引 | |
| thread_id | String(100) | 索引, nullable | 对话线程标识 |
| role | String(20) | NOT NULL | user / assistant / tool |
| content | Text | nullable | 消息内容 |
| metadata_json | JSONB | nullable, GIN 索引 | 元数据（thinking、tool_calls、stopped、images） |
| created_at | DateTime(tz) | server_default=now(), 索引 | |

按 `user_id + thread_id` 组织对话线程。metadata_json 结构：
- 用户消息：`{"images": N}`
- 助手消息：`{"thinking": "思考内容", "tool_calls": [{id, name, input, output, status, thinking_offset}], "stopped": true}`

### thread_metas - 线程元信息表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 继承自 ThreadBase |
| user_id | UUID | FK->users.id CASCADE, 索引 | 继承自 ThreadBase |
| thread_id | String(100) | UNIQUE, 索引 | 继承自 ThreadBase |
| title | String(200) | nullable | 用户自定义标题 |
| created_at | DateTime(tz) | server_default=now() | |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() | 继承自 ThreadBase |

### thread_usages - 线程 Token 用量表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 继承自 ThreadBase |
| user_id | UUID | FK->users.id CASCADE, 索引 | 继承自 ThreadBase |
| thread_id | String(100) | UNIQUE, 索引 | 继承自 ThreadBase |
| total_tokens | Integer | default=0 | 累积总量 |
| input_tokens | Integer | default=0 | 输入量 |
| output_tokens | Integer | default=0 | 输出量 |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() | 继承自 ThreadBase |

ThreadBase 混入：thread_metas 与 thread_usages 共享 `id` / `user_id` / `thread_id` / `updated_at` 字段定义。

采用累加模式：每次对话结束时 upsert，各 token 字段叠加。

## 设计原则总结

1. **所有权校验链**：所有可变更操作逐级校验 `resource -> parent -> ... -> user_id`，已抽取为 `_verify_*_ownership` helper
2. **软删除策略**：训练计划和饮食计划均使用 archived 状态标记删除，对话使用物理 CASCADE 删除
3. **唯一约束**：`(user_id, date)` 确保每人每天仅一次打卡，`(user_id, type)` 确保成就不重复
4. **级联策略**：父记录删除时子记录自动 CASCADE 删除（SET NULL 仅用于 plan_day_id 的可选关联）
5. **时间戳**：各表统一使用带时区的 DateTime 字段，server_default 由数据库端生成
6. **索引策略**：equipment / difficulty 加独立索引支持多维度搜索；metadata_json 加 GIN 索引支持 JSON 路径查询；user_id 单列索引由复合唯一索引前缀覆盖，不再冗余创建
