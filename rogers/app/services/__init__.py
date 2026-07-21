"""
业务逻辑层

所有 Service 类均为纯静态方法，不持有状态。
Agent Tools 和 FastAPI Routers 共同调用此层，实现业务复用。

- AuthService: 注册/登录/刷新 Token
- UserService: 用户 CRUD
- PlanService: 训练计划 CRUD + 智能生成
- CheckinService: 打卡记录 + 连续天数计算
- ExerciseService: 动作库查询
- StatsService: 周/月/累计统计
"""