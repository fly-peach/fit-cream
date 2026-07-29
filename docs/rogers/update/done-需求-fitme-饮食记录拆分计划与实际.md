# fitme 饮食记录拆分：计划 vs 实际记录

**日期**：2026-07-28
**来源**：功能完善 / 对比 fit-cream-last
**详情**：当前只有 DietPlan（计划层），缺少记录用户实际每餐摄入的表。新增 DietMeal（实际每餐记录）和 DailyDietSummary（每日汇总统计）。

## 待办

- [x] 创建 DietMeal 模型（user_id + meal_date + meal_type，支持自定义食物）
- [x] 创建 DailyDietSummary 模型（user_id + summary_date 唯一）
- [x] 创建 CustomFoodItem 模型（用户自定义食物库）
- [x] 更新 User 模型关系（新增 diet_meals、custom_food_items）
- [x] 创建 DietMealService（CRUD + 每日汇总）
- [x] 创建 CustomFoodItemService（用户自定义食物管理）
- [x] 创建 schemas/diet.py（DietMealIn/DietMealOut/DailyDietSummaryOut/CustomFoodItemIn/CustomFoodItemOut）
- [x] 创建 diet router（独立于 diet_plans）
- [ ] 更新 StatsService，集成饮食统计
- [ ] 更新 Agent 工具，支持记录饮食
- [x] 更新 Database-02-饮食计划数据表.md 文档
- [x] 更新 Services-01-Service层.md 文档
- [x] 更新 routers/Overview-01-路由总览.md 文档
- [x] 创建 Endpoints-07-饮食记录.md 文档
