# 饮食计划接口

prefix: `/diet-plans`

所有端点认证方式均为 JWT（get_current_user），资源通过用户作用域隔离。饮食计划使用**软删除**（archive 状态）而非物理删除。

## 列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/diet-plans` |

**查询参数：**

| 参数 | 类型 | 默认 | 约束 |
|------|------|------|------|
| page | int | 1 | ge 1 |
| size | int | 20 | 1-100 |
| status | Optional[str] | — | active / archived |

**响应：`ResponseModel[PaginatedResponse[DietPlanListOut]]`**

## 活跃计划

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/diet-plans/active` |

**响应：`ResponseModel[Optional[DietPlanOut]]`**

## 详情

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/diet-plans/{diet_plan_id}` |
| 路径参数 | diet_plan_id: UUID |

**响应：`ResponseModel[DietPlanOut]`** — 含 days + meals 完整结构

## 创建

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/diet-plans` |

**请求体：DietPlanCreate**

| 字段 | 类型 | 约束 |
|------|------|------|
| name | str | 1-200 字符 |
| target_calories | Optional[int] | 目标热量(kcal) |
| goal | Optional[str] | lose_fat / gain_muscle / maintain / improve_health |
| days | list[DietDayCreate] | 饮食日列表（含 day_of_week、focus、metadata_、meals[]） |

**响应：`ResponseModel[DietPlanOut]`**

## 更新

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/diet-plans/{diet_plan_id}` |

**请求体：DietPlanUpdate**

name、target_calories、goal、status 均为 Optional

**响应：`ResponseModel[DietPlanOut]`**

## 删除（软删除）

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/diet-plans/{diet_plan_id}` |

逻辑：将 status 设为 archived，不物理删除。

**响应：`ResponseModel[None]`（message: "饮食计划已归档"）**

---

## 添加饮食日

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/diet-plans/{diet_plan_id}/days` |

**请求体：DietDayCreate**

| 字段 | 类型 | 说明 |
|------|------|------|
| day_of_week | int | 1-7 |
| focus | Optional[str] | 饮食重点 |
| metadata_ | Optional[dict] | |
| meals | list[DietMealCreate] | 餐食列表 |

**响应：`ResponseModel[DietPlanOut]`** — 返回刷新后的完整计划

## 更新饮食日

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/diet-plans/days/{day_id}` |

**请求体：DietDayUpdate**（focus, metadata_ 均为 Optional）

**响应：`ResponseModel[DietPlanOut]`** — 返回父计划完整结构

## 更新餐食

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/diet-plans/meals/{meal_id}` |

**请求体：DietMealUpdate**

| 字段 | 类型 | 约束 |
|------|------|------|
| meal_type | str | breakfast / lunch / dinner / snack |
| food_name | Optional[str] | 食物名称 |
| calories | Optional[int] | 热量 |
| protein_g | Optional[float] | 蛋白质 |
| carbs_g | Optional[float] | 碳水 |
| fat_g | Optional[float] | 脂肪 |
| portion | Optional[str] | 份量描述 |
| sort_order | Optional[int] | 排序 |
| metadata_ | Optional[dict] | |

**响应：`ResponseModel[DietMealOut]`**

## 删除餐食

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/diet-plans/meals/{meal_id}` |

**响应：`ResponseModel[None]`（message: "餐食已删除"）**
