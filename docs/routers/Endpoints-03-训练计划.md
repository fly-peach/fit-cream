# 训练计划接口

## 训练计划 (prefix: `/plans`)

所有端点认证方式均为 JWT（get_current_user），资源通过级联所有权校验隔离。

### 列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/plans` |

**查询参数：**

| 参数 | 类型 | 默认 | 约束 |
|------|------|------|------|
| page | int | 1 | ge 1 |
| size | int | 20 | 1-100 |
| status | Optional[str] | — | active / archived / completed |

**响应：`ResponseModel[PaginatedResponse[PlanListOut]]`**

PlanListOut：id, name, goal, difficulty, weeks, status, created_at（不含嵌套 days）

### 活跃计划

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/plans/active` |

**响应：`ResponseModel[Optional[PlanOut]]`** — 最近的一个 active 计划，无活跃计划时返回 null

### 详情

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/plans/{plan_id}` |
| 路径参数 | plan_id: UUID |

**响应：`ResponseModel[PlanOut]`** — 含 days + exercises 完整结构

### 创建

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/plans` |

**请求体：PlanCreate**

| 字段 | 类型 | 约束 |
|------|------|------|
| name | str | 1-200 字符 |
| goal | Optional[str] | lose_fat / gain_muscle / maintain / improve_health |
| difficulty | Optional[str] | 默认 beginner，可选 beginner / intermediate / advanced |
| weeks | Optional[int] | 1-52 |
| days | list[PlanDayCreate] | 训练日列表（含 day_of_week、focus、rest_seconds、metadata_、exercises[]） |

逻辑：批量创建 Plan → PlanDay → PlanDayExercise，一次性提交。

**响应：`ResponseModel[PlanOut]`**

### 更新

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/plans/{plan_id}` |
| 路径参数 | plan_id: UUID |

**请求体：PlanUpdate**

name、goal、difficulty、weeks、status 均为 Optional，支持部分更新。

**响应：`ResponseModel[PlanOut]`**

### 删除（物理删除）

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/plans/{plan_id}` |
| 路径参数 | plan_id: UUID |

逻辑：CASCADE 物理删除关联的 days 和 exercises。

**响应：`ResponseModel[None]`（message: "计划已删除"）**

---

### 添加训练日

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/plans/{plan_id}/days` |

**请求体：PlanDayCreate**

| 字段 | 类型 | 说明 |
|------|------|------|
| day_of_week | int | 1-7 |
| focus | Optional[str] | 训练重点 |
| rest_seconds | int | 默认 60 秒 |
| metadata_ | Optional[dict] | 自定义扩展 |
| exercises | list[PlanExerciseCreate] | 动作列表 |

**响应：`ResponseModel[PlanOut]`** — 返回刷新后的完整计划

### 更新训练日

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/plans/days/{day_id}` |
| 路径参数 | day_id: UUID |

**请求体：PlanDayUpdate**（focus, rest_seconds, metadata_ 均为 Optional）

**响应：`ResponseModel[PlanOut]`** — 返回父计划完整结构

### 删除训练日

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/plans/days/{day_id}` |

**响应：`ResponseModel[PlanOut]`** — 返回删除后的完整计划

---

### 添加动作

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/plans/days/{day_id}/exercises` |

**请求体：PlanExerciseCreate**

| 字段 | 类型 | 约束 |
|------|------|------|
| exercise_id | UUID | 引用动作库 |
| sets | int | 1-20 |
| reps | int | 1-100 |
| weight_kg | Optional[float] | ge 0 |
| sort_order | int | 默认 0 |
| notes | Optional[str] | 最多 500 字符 |
| metadata_ | Optional[dict] | |

**响应：`ResponseModel[PlanOut]`** — 返回刷新后的完整计划（含 ExerciseBrief 引用信息）

### 更新动作

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/plans/exercises/{exercise_id}` |

**请求体：PlanExerciseUpdate**

sets、reps、weight_kg、sort_order、notes、metadata_ 均为 Optional

**响应：`ResponseModel[PlanOut]`** — 返回刷新后的完整计划

### 删除动作

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/plans/exercises/{exercise_id}` |

**响应：`ResponseModel[PlanOut]`** — 返回删除后的完整计划

---

## 动作库 (prefix: `/exercises`)

### 动作列表（含筛选和分页）

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/exercises` |
| 认证 | JWT (get_current_user) |

**查询参数：**

| 字段 | 类型 | 说明 |
|------|------|------|
| muscle_group | Optional[str] | 肌群筛选 |
| equipment | Optional[str] | 器械筛选 |
| difficulty | Optional[str] | 难度筛选 |
| category | Optional[str] | 分类筛选：compound/isolation/cardio/mobility |
| keyword | Optional[str] | 关键词搜索 |
| limit | int | 1-100，默认 20 |
| offset | int | 分页偏移，默认 0 |

**响应：`ResponseModel[list[ExerciseOut]]`**

ExerciseOut：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | str | 中文名 |
| name_en | Optional[str] | 英文名 |
| muscle_group | Optional[str] | 肌群 |
| muscle_subgroup | Optional[str] | 细分肌群 |
| category | Optional[str] | compound/isolation/cardio/mobility |
| is_compound | bool | 是否复合动作 |
| equipment | Optional[str] | 器械 |
| difficulty | Optional[str] | 难度 |
| calories_per_min | Optional[float] | 每分钟热量 |
| description | Optional[str] | 描述 |
| instructions | Optional[str] | 执行步骤 |
| tips | Optional[str] | 注意事项 |

### 动作分类统计

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/exercises/categories` |
| 认证 | JWT |

**响应：`ResponseModel[list[CategoryStats]]`**

| 字段 | 类型 |
|------|------|
| name | str |
| count | int |

### 动作肌群统计

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/exercises/muscle-groups` |
| 认证 | JWT |

**响应：`ResponseModel[list[MuscleGroupStats]]`**

| 字段 | 类型 |
|------|------|
| name | str |
| count | int |

### 动作详情

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/exercises/{exercise_id}` |
| 认证 | JWT |

### 创建动作

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/exercises` |
| 认证 | JWT (get_admin_user) |

**请求体：ExerciseCreate**

| 字段 | 类型 | 约束 |
|------|------|------|
| name | str | 1-200 字符 |
| name_en | Optional[str] | 最多 200 字符 |
| muscle_group | Optional[str] | 最多 50 字符 |
| muscle_subgroup | Optional[str] | 最多 50 字符 |
| category | Optional[str] | 最多 50 字符 |
| is_compound | bool | 默认 False |
| equipment | Optional[str] | 最多 100 字符 |
| difficulty | Optional[str] | 最多 20 字符 |
| calories_per_min | Optional[float] | >=0 |
| description | Optional[str] | - |
| instructions | Optional[str] | - |
| tips | Optional[str] | - |

### 更新动作

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/exercises/{exercise_id}` |
| 认证 | JWT (get_admin_user) |

**请求体：ExerciseUpdate**（所有字段可选）

### 删除动作

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/exercises/{exercise_id}` |
| 认证 | JWT (get_admin_user) |

逻辑：删除前检查 PlanDayExercise 和 CheckinExercise 引用数量，有引用则拒绝删除并返回 40000。
