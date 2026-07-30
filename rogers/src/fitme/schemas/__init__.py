"""
Pydantic v2 Schemas 包

定义所有 API 接口的请求/响应数据模型：
- auth: 注册/登录/刷新 Token
- user: 用户信息输出/更新
- plan: 训练计划 CRUD
- checkin: 打卡记录 CRUD
- common: 统一响应格式（ResponseModel / PaginatedResponse）

注：对话线程/消息相关 schemas 已迁至 src/agents/schemas/chat。
"""