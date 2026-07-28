# 打卡与统计接口

## 打卡 (prefix: `/checkins`)

所有端点认证方式均为 JWT（get_current_user），每人每天仅限一次打卡。

### 列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/checkins` |

查询参数：

| 参数 | 类型 | 默认 | 约束 |
|------|------|------|------|
| page | int | 1 | ge 1 |
| size | int | 20 | 1-100 |
| start | Optional[date] | — | 起始日期 YYYY-MM-DD |
| end | Optional[date] | — | 截止日期 YYYY-MM-DD |

响应：`ResponseModel[PaginatedResponse[CheckinOut]]`

CheckinOut：id, user_id, plan_day_id, date, duration_min, actual_intensity, calories_burned, mood, note, created_at, exercises[]
CheckinExerciseOut：exercise_id, exercise_name, sets_done, reps_done, weight_kg, rpe, notes

### 连续打卡天数

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/checkins/streak` |

响应：`ResponseModel[StreakOut]`

| 字段 | 类型 | 说明 |
|------|------|------|
| current_streak | int | 当前连续天数（从今天往前计算） |
| longest_streak | int | 最长连续记录 |
| last_checkin_date | Optional[date] | 最近打卡日期 |

### 详情

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/checkins/{checkin_id}` |
| 路径参数 | checkin_id: UUID |

响应：`ResponseModel[CheckinOut]`

### 创建

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/checkins` |

请求体：CheckinCreate

| 字段 | 类型 | 约束 |
|------|------|------|
| date | date | 必填，不可在未来 |
| plan_day_id | Optional[UUID] | 关联训练日 |
| duration_min | int | > 0 |
| actual_intensity | Optional[str] | low/medium/high |
| calories_burned | Optional[int] | >=0, 估算热量(kcal) |
| mood | Optional[int] | 1-5 |
| note | Optional[str] | 最多 1000 字符 |
| exercises | list[CheckinExerciseCreate] | 动作记录列表（含 exercise_id, sets_done, reps_done, weight_kg, rpe, notes） |

逻辑：校验 `(user_id, date)` 唯一性，校验日期合法性，批量创建 CheckinExercise 子记录。

响应：`ResponseModel[CheckinOut]`

错误：重复打卡 → 40002，日期无效 → 40003，心情超出范围 → 40004

### 更新

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/checkins/{checkin_id}` |

请求体：CheckinUpdate

duration_min、mood、note、exercises 均为 Optional

响应：`ResponseModel[CheckinOut]`

---

## 统计 (prefix: `/stats`)

所有端点认证方式均为 JWT（get_current_user）。

### 周统计

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/stats/weekly` |

查询参数：

| 参数 | 类型 | 默认 |
|------|------|------|
| week_start | Optional[date] | 本周一 |

响应：`ResponseModel[dict]` — 训练次数、总时长、每日分解

### 月统计

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/stats/monthly` |

查询参数：

| 参数 | 类型 | 约束 |
|------|------|------|
| year | Optional[int] | 2020-2100 |
| month | Optional[int] | 1-12 |

响应：`ResponseModel[dict]` — 月度趋势、周度分组、平均心情

### 身体数据

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/stats/body` |

响应：`ResponseModel[dict]` — 当前体重、身高、目标

### 总览

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/stats/overview` |

响应：`ResponseModel[dict]` — 累计数据（训练总次数/总时长/总组数）+ 连续打卡（内部调用 CheckinService.get_streak）

---

## 饮食统计 (prefix: `/stats`)

### 饮食营养趋势

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/stats/diet` |
| 认证 | JWT |

**查询参数：**

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| start | Optional[date] | 7 天前 | 开始日期 |
| end | Optional[date] | 今天 | 结束日期 |

**响应：`ResponseModel[list[DietTrendItem]]`**

| 字段 | 类型 | 说明 |
|------|------|------|
| summary_date | str | 日期 |
| total_calories | int | 总卡路里 |
| total_protein_g | float | 总蛋白质(克) |
| total_carbs_g | float | 总碳水(克) |
| total_fat_g | float | 总脂肪(克) |
| meal_count | int | 餐数 |
