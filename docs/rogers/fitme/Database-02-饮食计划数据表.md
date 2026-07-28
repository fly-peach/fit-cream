# 饮食计划数据库设计

FitCream 使用 PostgreSQL 数据库，通过 SQLAlchemy ORM 管理。本文件涵盖饮食计划相关数据表。

## 饮食计划体系

### diet_plans - 饮食计划表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK->users.id CASCADE, 索引 | 所属用户 |
| name | String(200) | NOT NULL | 计划名称 |
| target_calories | Integer | nullable | 目标热量(kcal) |
| goal | String(50) | nullable | 目标类型 |
| status | String(20) | default="active" | active / archived |
| created_at | DateTime(tz) | server_default=now() | |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() | |

关系：一对多 -> diet_plan_days（CASCADE 删除）

### diet_plan_days - 饮食日表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| diet_plan_id | UUID | FK->diet_plans.id CASCADE, 索引 | 所属饮食计划 |
| day_of_week | Integer | NOT NULL | 1=周一 ... 7=周日 |
| focus | String(100) | nullable | 饮食重点 |
| metadata_ | JSONB | default={} | 自定义扩展 |

关系：一对多 -> diet_plan_meals（CASCADE 删除）

### diet_plan_meals - 饮食日餐食表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| diet_plan_day_id | UUID | FK->diet_plan_days.id CASCADE, 索引 | 所属饮食日 |
| meal_type | String(20) | NOT NULL | breakfast/lunch/dinner/snack |
| food_name | String(200) | NOT NULL | 食物名称 |
| calories | Integer | nullable | 热量(kcal) |
| protein_g | Numeric(6,1) | nullable | 蛋白质(g) |
| carbs_g | Numeric(6,1) | nullable | 碳水(g) |
| fat_g | Numeric(6,1) | nullable | 脂肪(g) |
| portion | String(100) | nullable | 份量描述 |
| sort_order | Integer | default=0 | 排序 |
| metadata_ | JSONB | default={} | |

## 饮食生成逻辑

1. 目标映射为宏量营养素比例：
   - 减脂：P40% / C30% / F30%
   - 增肌：P35% / C45% / F20%
   - 维持：P30% / C40% / F30%
2. 每日热量分配到 4 餐：早餐 30%、午餐 35%、晚餐 25%、加餐 10%
3. 按 `days_per_week` 参数生成天数（默认 7 天），按模板轮换食物组合

## 设计原则

- **软删除**：饮食计划使用 archived 状态标记删除，保留历史数据
- **所有权校验**：所有操作逐级校验 `diet_plan_day -> diet_plan -> user_id`，已抽取为 `_verify_diet_day_ownership` / `_verify_meal_ownership` helper
- **级联策略**：父记录删除时子记录自动 CASCADE 删除
- 通用设计原则详见 Database-01-训练计划数据表.md

## 实际饮食记录 vs 饮食计划

本文件描述的是饮食计划层（DietPlan → DietPlanDay → DietPlanMeal），
与实际的每餐记录（DietMeal）和每日营养汇总（DailyDietSummary）为不同层次：

- **饮食计划（DietPlan）**：预设的计划模板，包含目标卡路里和计划餐食
- **实际记录（DietMeal）**：用户实际每日每餐的摄入记录
- **每日汇总（DailyDietSummary）**：按日期自动聚合的营养统计
- **自定义食物（CustomFoodItem）**：用户自定义的常用食物，可在 DietMeal 中引用

详见 Database-01 中 diet_meals / daily_diet_summaries / custom_food_items 表定义。
