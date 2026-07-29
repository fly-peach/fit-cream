# 饮食记录接口

prefix: `/diet-meals`

所有端点认证方式均为 JWT（get_current_user），资源通过用户作用域隔离。饮食记录为用户实际每餐摄入的记录，区别于饮食计划（`/diet-plans`）的预设模板。

## 餐食记录

### 列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/diet-meals` |
| 认证 | JWT (get_current_user) |

**查询参数：**

| 参数 | 类型 | 默认 | 约束 |
|------|------|------|------|
| page | int | 1 | ge 1 |
| size | int | 20 | 1-100 |
| start | Optional[date] | - | 起始日期 YYYY-MM-DD |
| end | Optional[date] | - | 截止日期 YYYY-MM-DD |
| meal_type | Optional[str] | - | breakfast / lunch / dinner / snack |

**响应：`ResponseModel[PaginatedResponse[DietMealOut]]`**

DietMealOut：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 用户 ID |
| meal_date | date | 用餐日期 |
| meal_type | str | breakfast / lunch / dinner / snack |
| food_name | str | 食物名称 |
| portion | Optional[str] | 份量描述 |
| calories | int | 卡路里 |
| protein_g | Optional[float] | 蛋白质(克) |
| carbs_g | Optional[float] | 碳水(克) |
| fat_g | Optional[float] | 脂肪(克) |
| note | Optional[str] | 备注 |
| custom_food_item_id | Optional[UUID] | 关联自定义食物 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 创建

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/diet-meals` |
| 认证 | JWT (get_current_user) |

**请求体：DietMealCreate**

| 字段 | 类型 | 约束 |
|------|------|------|
| meal_date | date | 必填 |
| meal_type | str | breakfast / lunch / dinner / snack |
| food_name | str | 1-200 字符 |
| portion | Optional[str] | 最多 100 字符 |
| calories | int | >= 0，默认 0 |
| protein_g | Optional[float] | >= 0 |
| carbs_g | Optional[float] | >= 0 |
| fat_g | Optional[float] | >= 0 |
| note | Optional[str] | 最多 500 字符 |
| custom_food_item_id | Optional[UUID] | 关联自定义食物 |

逻辑：创建后自动重算当日 `DailyDietSummary`。

**响应：`ResponseModel[DietMealOut]`**

### 详情

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/diet-meals/{meal_id}` |
| 路径参数 | meal_id: UUID |
| 认证 | JWT (get_current_user) |

**响应：`ResponseModel[DietMealOut]`**

### 更新

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/diet-meals/{meal_id}` |
| 路径参数 | meal_id: UUID |
| 认证 | JWT (get_current_user) |

**请求体：DietMealUpdate**

meal_type、food_name、portion、calories、protein_g、carbs_g、fat_g、note 均为 Optional。

使用 `model_dump(exclude_unset=True)` 实现部分更新。更新后自动重算当日汇总。

**响应：`ResponseModel[DietMealOut]`**

### 删除

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/diet-meals/{meal_id}` |
| 路径参数 | meal_id: UUID |
| 认证 | JWT (get_current_user) |

逻辑：删除后自动重算当日汇总。

**响应：`ResponseModel[None]`（message: "饮食记录已删除"）**

---

## 每日营养汇总

### 某日汇总

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/diet-meals/summary` |
| 认证 | JWT (get_current_user) |

**查询参数：**

| 参数 | 类型 | 约束 |
|------|------|------|
| date | date | 必填，查询日期 YYYY-MM-DD |

逻辑：查询当日 `DailyDietSummary`，不存在则按当日 `DietMeal` 记录重新计算后创建。

**响应：`ResponseModel[DailyDietSummaryOut]`**

DailyDietSummaryOut：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 用户 ID |
| summary_date | date | 汇总日期 |
| total_calories | int | 总卡路里 |
| total_protein_g | float | 总蛋白质(克) |
| total_carbs_g | float | 总碳水(克) |
| total_fat_g | float | 总脂肪(克) |
| protein_goal_met | bool | 蛋白质目标达成 |
| carbs_goal_met | bool | 碳水目标达成 |
| fat_goal_met | bool | 脂肪目标达成 |
| meal_count | int | 当日餐数 |
| note | Optional[str] | 备注 |

### 汇总列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/diet-meals/summaries` |
| 认证 | JWT (get_current_user) |

**查询参数：**

| 参数 | 类型 | 默认 | 约束 |
|------|------|------|------|
| start | Optional[date] | - | 起始日期 |
| end | Optional[date] | - | 截止日期 |

**响应：`ResponseModel[list[DailyDietSummaryOut]]`**

---

## 自定义食物 (prefix: `/diet-meals/foods`)

用户可创建常用食物库，创建餐食记录时通过 `custom_food_item_id` 引用。

### 列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/diet-meals/foods/list` |
| 认证 | JWT (get_current_user) |

**查询参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| category | Optional[str] | - | 分类筛选 |
| keyword | Optional[str] | - | 关键词搜索 |

**响应：`ResponseModel[list[CustomFoodItemOut]]`**

### 创建

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/diet-meals/foods` |
| 认证 | JWT (get_current_user) |

**请求体：CustomFoodItemCreate**

| 字段 | 类型 | 约束 |
|------|------|------|
| name | str | 1-200 字符 |
| category | Optional[str] | 最多 50 字符 |
| portion | str | 份量描述，默认 "100g"，最多 100 字符 |
| calories_per_portion | int | >= 0 |
| protein_g_per_portion | Optional[float] | >= 0 |
| carbs_g_per_portion | Optional[float] | >= 0 |
| fat_g_per_portion | Optional[float] | >= 0 |
| note | Optional[str] | 最多 500 字符 |

**响应：`ResponseModel[CustomFoodItemOut]`**

CustomFoodItemOut：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 用户 ID |
| name | str | 食物名称 |
| category | Optional[str] | 分类 |
| portion | str | 份量描述 |
| calories_per_portion | int | 每份卡路里 |
| protein_g_per_portion | Optional[float] | 每份蛋白质(克) |
| carbs_g_per_portion | Optional[float] | 每份碳水(克) |
| fat_g_per_portion | Optional[float] | 每份脂肪(克) |
| note | Optional[str] | 备注 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### 更新

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/diet-meals/foods/{food_id}` |
| 路径参数 | food_id: UUID |
| 认证 | JWT (get_current_user) |

**请求体：CustomFoodItemUpdate**

name、category、portion、calories_per_portion、protein_g_per_portion、carbs_g_per_portion、fat_g_per_portion、note 均为 Optional。

使用 `model_dump(exclude_unset=True)` 实现部分更新。

**响应：`ResponseModel[CustomFoodItemOut]`**

### 删除

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/diet-meals/foods/{food_id}` |
| 路径参数 | food_id: UUID |
| 认证 | JWT (get_current_user) |

**响应：`ResponseModel[None]`（message: "食物已删除"）**

---

## 路由顺序说明

`diet_meals` 路由中静态路径（`/summary`、`/summaries`、`/foods/list`、`/foods`、`/foods/{food_id}`）注册在动态路径（`/{meal_id}`）之前，以避免 FastAPI 路径匹配冲突。详见 `rogers/app/routers/diet_meals.py`。
