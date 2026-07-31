# Service 层

## 设计原则

所有 Service 为无状态静态方法类，以 AsyncSession 作为公共第一参数，被 API Router 和 Agent Tool 共同调用，避免路由层与 Agent 之间的代码重复。

## 服务列表

### UserService

| 方法 | 功能 | 输入 | 输出 |
|------|------|------|------|
| get_by_id | 按 ID 获取用户 | user_id | User（未找到抛 NotFoundException） |
| get_by_email | 按邮箱获取用户 | email | User / None |
| update_profile | 部分更新用户资料 | user_id + UserUpdate | User |
| get_user_settings | 获取用户设置（不存在则创建） | user_id | UserSettings |
| update_user_settings | 更新用户设置 | user_id + UserSettingsUpdate | UserSettings |
| list_health_metrics | 分页获取健康指标历史 | user_id + page + size | (list[HealthMetric], int) |
| get_health_metric | 获取单条健康指标 | user_id + metric_id | HealthMetric |
| get_latest_health_metric | 获取最新健康指标 | user_id | HealthMetric / None |
| create_health_metric | 创建健康指标记录 | user_id + HealthMetricCreate | HealthMetric |
| update_health_metric | 更新健康指标记录 | user_id + metric_id + HealthMetricUpdate | HealthMetric |
| delete_health_metric | 删除健康指标记录 | user_id + metric_id | None |

update_health_metric 方法使用 exclude_unset=True 实现部分更新，仅更新提供的字段。创建和更新健康指标时会自动计算 BMI。

### UserSettingsService（含于 UserService）

| 方法 | 功能 | 输入 | 输出 |
|------|------|------|------|
| get_user_settings | 获取用户设置（不存在则创建） | user_id | UserSettings |
| update_user_settings | 更新用户设置（部分更新） | user_id + UserSettingsUpdate | UserSettings |

HealthMetricService（含于 UserService）

| 方法 | 功能 | 输入 | 输出 |
|------|------|------|------|
| list_health_metrics | 获取健康指标历史记录 | user_id + page + size | (list[HealthMetric], int) |
| get_health_metric | 获取单条健康指标记录 | user_id + metric_id | HealthMetric |
| get_latest_health_metric | 获取最新健康指标 | user_id | HealthMetric / None |
| create_health_metric | 创建健康指标记录 | user_id + data | HealthMetric |
| update_health_metric | 更新健康指标记录 | user_id + metric_id + data | HealthMetric |
| delete_health_metric | 删除健康指标记录 | user_id + metric_id | None |

### CheckinService

| 方法 | 功能 | 权限 |
|------|------|------|
| create_checkin | 创建打卡记录（同日唯一） | user |
| update_checkin | 更新打卡记录 | user |
| get_by_id | ID 查询 + 权限检查 | user |
| list_checkins | 分页列表（日期范围） | user |
| get_streak | 连续打卡天数（SQL 窗口函数） | user |
| _estimate_calories | 根据时长估算消耗热量 | (内部) |

说明：
- Checkin 新增 actual_intensity（低/中/高）和 calories_burned（估算热量）字段
- CheckinExercise 新增 rpe（1-10）和 notes（动作备注）字段
- create_checkin 时自动传入实际强度、RPE 和备注
- _estimate_calories 按 duration_min * 7 kcal/min 粗略估算

### PlanService

| 方法 | 功能 | 逻辑说明 |
|------|------|------|
| create_plan | 创建计划 | 批量创建 Plan → PlanDay → PlanDayExercise |
| list_plans | 分页列表查询 | 支持按状态过滤 |
| get_plan_detail | 获取计划详情 | 含 training days + exercises（selectinload） |
| get_active_plan | 获取当前活跃计划 | 最近的一个 active 状态计划 |
| update_plan | 更新计划 | 部分更新，支持 status 切换 |
| delete_plan | 删除计划 | 软删除（archived） |
| add_plan_day | 添加训练日 | 新增 day 关联 plan |
| update_plan_day | 更新训练日 | - |
| delete_plan_day | 删除训练日 | 返回 (plan_day, plan) |
| add_exercise_to_day | 添加动作到训练日 | 返回 (plan_exercise, plan) |
| update_exercise | 更新动作 | 返回 (plan_exercise, plan) |
| delete_exercise | 删除动作 | 返回 (plan_exercise, plan) |
| generate_plan_from_goal | AI 生成计划 | 根据目标、难度自动创建完整计划 |
| adjust_plan | AI 调整计划 | 支持：移除日、改难度、改动作 |

归属验证优化：`_verify_plan_day_ownership` 和 `_verify_exercise_ownership` 使用单条 JOIN 查询（PlanDayExercise → PlanDay → Plan）替代原有的 2-3 次串行查询。

mutation 方法（delete_plan_day、delete_exercise、add_exercise_to_day、update_exercise）返回 plan 对象，供 Router 层获取 plan.id 后调用 get_plan_detail 返回完整 PlanOut。

generate_plan_from_goal 流程：
1. 目标映射为计划名称和训练重点
2. 难度决定组数/次数/休息时间配置
3. 每周天数决定训练日在周几分布
4. 自动创建 Plan + PlanDay + PlanDayExercise

### DietPlanService

与 PlanService 平行的饮食计划服务，结构一致但使用软删除（archived 状态）。归属验证同样使用单条 JOIN 查询（DietPlanMeal → DietPlanDay → DietPlan）。mutation 方法（add_meal、update_meal、delete_meal）返回 (meal, diet_plan) 元组。

特有的方法：

| 方法 | 功能 | 逻辑说明 |
|------|------|------|
| generate_diet_plan_from_goal | AI 生成饮食计划 | 目标映射为营养比例，自动分配各餐热量 |

饮食生成逻辑：
1. 目标映射为宏量营养素比例（减脂：P40%/C30%/F30%，增肌：P35%/C40%/F25%）
2. 每日热量分配到 4 餐：早餐 30%、午餐 35%、晚餐 25%、加餐 10%
3. 创建 7 天的饮食计划，按模板轮换食物组合

### ExerciseService

| 方法 | 功能 | 权限 |
|------|------|------|
| search | 多条件搜索动作（肌群/器械/难度/分类/关键词） | user |
| get_by_id | ID 查询 | user |
| get_all | 获取全部动作 | user |
| search_by_name | 模糊名称匹配（Agent 打卡解析用） | user |
| create_exercise | 创建动作 | admin |
| update_exercise | 部分更新动作 | admin |
| delete_exercise | 删除动作（校验计划/打卡引用） | admin |
| count | 动作总数（带过滤条件） | user |
| list_categories | 返回所有分类及数量 | user |
| list_muscle_groups | 返回所有肌群及数量 | user |
| list_equipments | 返回所有器械及数量（dataset 约 28 种） | user |

说明：
- 动作库含 1324 条 dataset 导入动作，中英双语字段成对存储（name/name_en、equipment/equipment_zh、body_part/body_part_zh、target/target_zh、secondary_muscles/secondary_muscles_zh、instruction_steps/instruction_steps_en 等）
- `muscle_group` 为 7 值粗分类，由 dataset body_part 经 MUSCLE_GROUP_COARSENING 映射归并而来
- 新增字段：category（分类）、is_compound（复合）、muscle_subgroup（细分肌群）、calories_per_min（热量）、instructions（执行步骤）、tips（注意事项）、动图 gif_url 等
- delete_exercise 删除前检查 PlanDayExercise 和 CheckinExercise 中的引用，有引用则拒绝删除
- search 支持肌群/器械/难度/分类/身体部位/目标/关键词多条件过滤 + offset 分页；keyword 对 name/description/instructions 做 OR 模糊匹配（中文查询可命中英文动作）
- 启动时自动种子动作库（exercise_seed.py，支持 dataset 与 40 个常见动作）

## DietMealService

饮食记录服务，位于 `src/fitme/services/diet_meal_service.py`。

| 方法 | 功能 | 权限 |
|------|------|------|
| create_meal | 创建餐食记录（自动重算当日汇总） | user |
| update_meal | 更新餐食记录 | user |
| delete_meal | 删除餐食记录 | user |
| get_by_id | ID 查询 + 权限检查 | user |
| list_meals | 分页列表（日期范围/餐次筛选） | user |
| get_summary | 获取某日营养汇总（不存在则重算） | user |
| list_summaries | 日期范围内营养汇总列表 | user |
| _recalc_summary | 按日期聚合 DietMeal 统计 → 更新/创建 DailyDietSummary | (内部) |

## CustomFoodItemService

用户自定义食物管理，位于 `src/fitme/services/diet_meal_service.py`。

| 方法 | 功能 | 权限 |
|------|------|------|
| create | 创建自定义食物 | user |
| update | 更新自定义食物 | user |
| delete | 删除自定义食物 | user |
| get_by_id | ID 查询 + 权限检查 | user |
| list_by_user | 按分类/关键词搜索用户的全部食物 | user |

### StatsService

| 方法 | 功能 | 返回内容 |
|------|------|------|
| get_weekly_stats | 周统计 | 训练次数/总时长/总组数 + 每日分解 |
| get_monthly_trend | 月统计 | 月度总计 + 周度分组 + 平均心情 |
| get_body_trend | 身体数据趋势 | 最近的体重/身高/目标 |
| get_all_stats | 全部统计概览 | 累计数据 + 连续打卡（内部调用 CheckinService.get_streak） |

### AuthService

| 方法 | 功能 | 逻辑说明 |
|------|------|------|
| register | 用户注册 | 检查手机号唯一性 → bcrypt 哈希密码 → 创建用户 → 创建默认设置 → 生成 JWT 对 |
| login | 用户登录 | 校验凭据 → 生成 JWT 对 |
| sms_login | 短信验证码登录 | 校验验证码 → 未注册自动注册 → 生成 JWT 对 |
| refresh_token | 刷新令牌 | 验证 refresh_token → 校验用户存在 → 生成新 JWT 对 |

> 完整方法列表（含 change_password/logout/验证码/密码重置/_create_user/_finalize_login 等）见 `auth/Services-01-用户服务.md`。

JWT 配置：
- Access Token：7 天有效期，HS256 签名
- Refresh Token：30 天有效期

## 服务集成关系

StatsService → 调用 → CheckinService.get_streak()
PlanService → 依赖 → UserService（获取身体数据）
DietPlanService → 依赖 → UserService（获取体重/目标）
CheckinService → 依赖 → ExerciseService.search_by_name()
Agent Tools → 调用 → Service（同进程）
API Router → 调用 → Service（同进程）
