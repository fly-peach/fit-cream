"""
FitCream 后端应用包

FastAPI 业务应用，包含：
- main: 应用入口 & lifespan
- config: pydantic-settings 全局配置
- database: 异步数据库引擎 & Session 工厂
- dependencies: 公共依赖（JWT 鉴权）
- models/: SQLAlchemy ORM 模型
- routers/: API 路由
- schemas/: Pydantic 请求/响应模型
- services/: 业务逻辑层
- utils/: 工具函数
"""