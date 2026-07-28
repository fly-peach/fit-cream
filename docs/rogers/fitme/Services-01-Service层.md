# Service 层

## 设计原则

所有 Service 为**无状态静态方法类**，以 `AsyncSession` 作为公共第一参数，被 API Router 和 Agent Tool 共同调用，避免路由层与 Agent 之间的代码重复。

## 服务列表

### UserService

| 方法 | 功能 | 输入 | 输出 |
|------|------|------|------|
| get_by_id | 按 ID 查用户 | user_id | User（未找到抛 NotFoundException） |
| get_by_email | 按邮箱查用户 | email | User / None |
| update_profile | 部分更新用户资料 | user_id + UserUpdate | User |

update_profile 使用 `model_dump(exclude_unset=True)` 实现部分更新，仅更新提供的字段。

### CheckinService

| 方法 | 功能 | 逻辑说明 |
|------|------|----------|
| create_checkin | 创建打卡记录 | 先校验 `(user_id, date)` 唯一性，校验日期是否在未来，然后批量创建 CheckinExercise 子记录 |
| get_by_date | 按日期查询打卡 | 指定日期的打卡记录 |
| get_by_id | 按 ID 查打卡 | 同时校验所有权归属 |
| list_checkins | 分页列表查询 | 支持日期范围过滤、分页 |
| update_checkin | 更新打卡信息 | 替换 exercise 子列表 |
| get_streak | 查询连续打卡天数 | 查询所有日期降序排列，从今天往前计算连续天数，同时返回最长连续记录 |

生成计划时的热量估算公式：
- 减脂：体重 × 22
- 增肌：体重 × 33
- 维持：体重 × 28

### PlanService

| 方法 | 功能 | 逻辑说明 |
|------|------|----------|
| create_plan | 创建计划 | 批量创建 Plan → PlanDay → PlanDayExercise |
| list_plans | 分页列表 | 支持按状态过滤 |
| get_plan_detail | 计划详情 | 含 training days + exercises |
| get_active_plan | 当前活跃计划 | 最近的一个 active 状态计划 |
| update_plan | 更新计划 | 部分更新，支持 status 切换 |
| delete_plan | 删除计划 | 物理 CASCADE 删除 |
| add_plan_day | 添加训练日 | 新增 day 并关联 plan |
| update_plan_day | 更新训练日 | |
| delete_plan_day | 删除训练日 | |
| add_exercise_to_day | 添加动作 | 关联 exercise_id |
| update_exercise | 更新动作 | |
| delete_exercise | 删除动作 | |
| generate_plan_from_goal | AI 生成计划 | 根据目标、难度自动创建完整计划 |
| adjust_plan | AI 调整计划 | 支持：移除日、改难度、改动作 |

`generate_plan_from_goal` 流程：
1. 目标映射为计划名称和训练重点
2. 难度决定组数/次数/休息时间配置
3. 每周天数决定训练日在周几分布
4. 自动创建 Plan + PlanDay + PlanDayExercise

`adjust_plan` 支持的操作：
- `remove_day`：移除指定日
- `change_difficulty`：调整难度（同步更新组数/次数/休息）
- `modify_exercise`：修改指定动作参数

### DietPlanService

与 PlanService 平行的饮食计划服务，结构一致但**使用软删除**（archived 状态）。特有的方法：

| 方法 | 功能 | 逻辑说明 |
|------|------|----------|
| generate_diet_plan_from_goal | AI 生成饮食计划 | 目标映射为营养比例，自动分配各餐热量 |

饮食生成逻辑：
1. 目标映射为宏量营养素比例（减脂：P40%/C30%/F30%，增肌：P35%/C40%/F25%）
2. 每日热量分配到 4 餐：早餐 30%、午餐 35%、晚餐 25%、加餐 10%
3. 创建 7 天的饮食计划，按模板轮换食物组合

### ExerciseService

| 方法 | 功能 | 逻辑说明 |
|------|------|----------|
| get_all | 全部动作 | |
| get_by_id | 按 ID 查询 | |
| list_by_muscle_group | 按肌群查询 | |
| list_by_equipment | 按器材查询 | |
| search | 多维度搜索 | 同时支持 muscle_group + equipment + difficulty + keyword（ILIKE 模糊匹配） |
| search_by_name | 名称模糊匹配 | Agent checkin 工具使用的动作匹配 |

### StatsService

| 方法 | 功能 | 返回内容 |
|------|------|----------|
| get_weekly_stats | 本周统计 | 训练次数/总时长/总组数 + 每日分解 |
| get_monthly_trend | 月度趋势 | 月度总计 + 周度分组 + 平均心情 |
| get_body_trend | 身体数据趋势 | 当前体重/身高/目标 |
| get_all_stats | 全部统计概览 | 累计数据 + 连续打卡（内部调用 CheckinService.get_streak） |

### AuthService

| 方法 | 功能 | 逻辑说明 |
|------|------|----------|
| register | 注册 | 检查手机号唯一 → bcrypt 哈希密码 → 创建用户 → 生成 JWT 对 |
| login | 登录 | 校验凭据 → 生成 JWT 对 |
| refresh_token | 刷新令牌 | 验证 refresh_token → 生成新 JWT 对 |

JWT 配置：
- Access Token：7 天有效期，HS256 签名
- Refresh Token：30 天有效期

## Service 集成关系

```
StatsService ──调用──→ CheckinService.get_streak()
PlanService  ──依赖──→ UserService（获取身体数据）
DietPlanService──依赖──→ UserService（获取体重/目标）
CheckinService──依赖──→ ExerciseService.search_by_name()

Agent Tools → Service（直接调用，同进程）
API Router  → Service（直接调用，同进程）
```
