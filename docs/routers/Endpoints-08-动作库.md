# 动作库接口

prefix: `/exercises`

动作库存储 1324 条健身动作（dataset 导入），含中英双语字段、动图演示与执行要点。查询类端点需 JWT 普通用户权限，管理类端点需 admin 权限。

## 动作列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/exercises` |
| 认证 | JWT (get_current_user) |

**查询参数：**

| 参数 | 类型 | 默认 | 约束 | 说明 |
|------|------|------|------|------|
| muscle_group | str | - | 可选 | 粗分类肌群（chest/back/legs/shoulders/arms/core/full_body） |
| equipment | str | - | 可选 | 器械 |
| difficulty | str | - | 可选 | beginner/intermediate/advanced |
| category | str | - | 可选 | compound/isolation/cardio/mobility |
| body_part | str | - | 可选 | dataset 原始身体部位（细分） |
| target | str | - | 可选 | 目标肌群 |
| keyword | str | - | 可选 | 模糊匹配 name/description/instructions |
| limit | int | 20 | 1-100 | 每页数量 |
| offset | int | 0 | >= 0 | 分页偏移 |

**响应：`ResponseModel[list[ExerciseOut]]`**

message 携带符合过滤条件的动作总数（与 limit/offset 无关）。

ExerciseOut：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | str | 动作中文名 |
| name_en | Optional[str] | 英文名 |
| muscle_group | Optional[str] | 粗分类肌群（7 值，由 dataset body_part 归并而来） |
| muscle_subgroup | Optional[str] | 细分肌群（英文） |
| muscle_subgroup_zh | Optional[str] | 细分肌群（中文） |
| category | Optional[str] | compound/isolation/cardio/mobility |
| is_compound | bool | 是否复合动作 |
| equipment | Optional[str] | 器械（英文） |
| equipment_zh | Optional[str] | 器械（中文） |
| difficulty | Optional[str] | 难度 |
| calories_per_min | Optional[float] | 每分钟消耗热量(kcal) |
| description | Optional[str] | 动作说明 |
| instructions | Optional[str] | 执行步骤说明 |
| tips | Optional[str] | 注意事项/常见错误 |
| body_part | Optional[str] | 原始身体部位（英文） |
| body_part_zh | Optional[str] | 原始身体部位（中文） |
| target | Optional[str] | 目标肌群（英文） |
| target_zh | Optional[str] | 目标肌群（中文） |
| secondary_muscles | Optional[list[str]] | 次要肌群（英文） |
| secondary_muscles_zh | Optional[list[str]] | 次要肌群（中文） |
| instruction_steps | Optional[list[str]] | 编号步骤（中文） |
| instruction_steps_en | Optional[list[str]] | 编号步骤（英文） |
| instructions_en | Optional[str] | 英文执行说明 |
| media_id | Optional[str] | 媒体库 ID（Gym Visual） |
| image | Optional[str] | 静态缩略图 URL |
| gif_url | Optional[str] | 动图演示 URL |
| attribution | Optional[str] | 媒体署名 |

## 分类统计

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/exercises/categories` |
| 认证 | JWT (get_current_user) |

**响应：`ResponseModel[list[CategoryStats]]`**

| 字段 | 类型 | 说明 |
|------|------|------|
| name | str | 分类名 |
| count | int | 该分类下动作数 |

逻辑：按 category 分组聚合计数，仅统计非空分类。

## 肌群统计

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/exercises/muscle-groups` |
| 认证 | JWT (get_current_user) |

**响应：`ResponseModel[list[MuscleGroupStats]]`**

| 字段 | 类型 | 说明 |
|------|------|------|
| name | str | 肌群名 |
| count | int | 该肌群下动作数 |

逻辑：按 muscle_group 分组聚合计数，仅统计非空肌群。

## 器械统计

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/exercises/equipments` |
| 认证 | JWT (get_current_user) |

**响应：`ResponseModel[list[EquipmentStats]]`**

| 字段 | 类型 | 说明 |
|------|------|------|
| name | str | 器械名 |
| count | int | 该器械下动作数 |

逻辑：按 equipment 分组聚合计数，dataset 含约 28 种器械值，前端筛选取动态值。

## 动作详情

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/exercises/{exercise_id}` |
| 认证 | JWT (get_current_user) |

**路径参数：** exercise_id (UUID)

错误：动作不存在 -> 40400

**响应：`ResponseModel[ExerciseOut]`**

## 创建动作

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/exercises` |
| 认证 | admin (get_admin_user) |

**请求体：ExerciseCreate**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| name | str | 1-200 字符 | 动作中文名 |
| name_en | Optional[str] | 最多 200 字符 | 英文名 |
| muscle_group | Optional[str] | 最多 50 字符 | 粗分类肌群 |
| muscle_subgroup | Optional[str] | 最多 50 字符 | 细分肌群 |
| muscle_subgroup_zh | Optional[str] | 最多 50 字符 | 细分肌群（中文） |
| category | Optional[str] | 最多 50 字符 | 分类 |
| is_compound | bool | 默认 false | 是否复合动作 |
| equipment | Optional[str] | 最多 100 字符 | 器械 |
| equipment_zh | Optional[str] | 最多 100 字符 | 器械（中文） |
| difficulty | Optional[str] | 最多 20 字符 | 难度 |
| calories_per_min | Optional[float] | >= 0 | 每分钟消耗热量 |
| description | Optional[str] | - | 动作说明 |
| instructions | Optional[str] | - | 执行步骤 |
| tips | Optional[str] | - | 注意事项 |
| body_part | Optional[str] | 最多 50 字符 | 原始身体部位 |
| body_part_zh | Optional[str] | 最多 50 字符 | 原始身体部位（中文） |
| target | Optional[str] | 最多 50 字符 | 目标肌群 |
| target_zh | Optional[str] | 最多 50 字符 | 目标肌群（中文） |
| secondary_muscles | Optional[list[str]] | - | 次要肌群 |
| secondary_muscles_zh | Optional[list[str]] | - | 次要肌群（中文） |
| instruction_steps | Optional[list[str]] | - | 编号步骤 |
| instruction_steps_en | Optional[list[str]] | - | 编号步骤（英文） |
| instructions_en | Optional[str] | - | 英文执行说明 |
| media_id | Optional[str] | 最多 100 字符 | 媒体库 ID |
| image | Optional[str] | 最多 255 字符 | 缩略图 URL |
| gif_url | Optional[str] | 最多 255 字符 | 动图 URL |
| attribution | Optional[str] | 最多 255 字符 | 媒体署名 |

**响应：`ResponseModel[ExerciseOut]`**

## 更新动作

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/exercises/{exercise_id}` |
| 认证 | admin (get_admin_user) |

**路径参数：** exercise_id (UUID)

**请求体：ExerciseUpdate**

所有字段可选，使用 `model_dump(exclude_unset=True)` 实现部分更新。字段集合与 ExerciseCreate 一致。

错误：动作不存在 -> 40400

**响应：`ResponseModel[ExerciseOut]`**

## 删除动作

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/exercises/{exercise_id}` |
| 认证 | admin (get_admin_user) |

**路径参数：** exercise_id (UUID)

逻辑：删除前校验 PlanDayExercise 和 CheckinExercise 中是否存在引用，有引用则拒绝删除（返回 40000）。

错误：动作不存在 -> 40400；已被引用 -> 40000

**响应：`ResponseModel[None]`**
