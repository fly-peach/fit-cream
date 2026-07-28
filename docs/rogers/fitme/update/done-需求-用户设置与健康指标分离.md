# fitme 用户设置与健康指标分离

日期：2026-07-28
来源：代码审查 / 架构优化
详情：当前 User 表混合了账户信息（phone、password_hash）、业务设置（goal）、身体数据（height_cm、weight_kg），且身体数据缺少历史记录。拆分为 UserSettings 表（当前设置）和 HealthMetric 表（历史记录）。

## 待办

- [x] 创建 UserSettings 模型（user_id 唯一关联）
- [x] 创建 HealthMetric 模型（user_id + measure_date 复合索引）
- [x] 从 User 表迁移 height_cm、weight_kg、goal 到 UserSettings
- [x] 删除 User 表中的 height_cm、weight_kg、goal 字段
- [x] 更新 User 模型关系（新增 settings、health_metrics）
- [x] 更新 users router 的获取/更新资料接口
- [x] 更新 UserService 的相关方法
- [x] 更新 Agent 的 user context 构建逻辑
- [x] 更新 Database-01-训练计划数据表.md 文档
- [x] 更新 Services-01-Service层.md 文档
- [x] 更新 Endpoints-01-认证与用户.md 文档
