"""
FitMe 业务数据模型包

核心 ORM 模型定义于各子模块（user / plan / checkin / exercise 等）。
模型注册与统一聚合导入由 app 层的 app.models 入口负责，
src 内不做"导入所有模型"的外层聚合。
"""
