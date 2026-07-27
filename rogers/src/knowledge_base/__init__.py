"""
知识库模块包

架构分层（参考 LLM Wiki 的纯逻辑/编排分离设计）：
- models.py:        ORM 模型（6 张表）
- schemas.py:       Pydantic 请求/响应模型
- chunker.py:       纯：文本分块（CJK token 估算 + 超长兜底，零 DB 依赖）
- references.py:    纯：引用解析（3 层查找映射 + 相对路径解析，零 DB 依赖）
- parsers.py:       纯：frontmatter 解析 + 标题提取（零 DB 依赖）
- schema_templates.py: 纯：实体类型模板（健身领域）
- lint.py:          纯：知识库健康检查规则
- indexer.py:       编排：分块 + 写 chunks + 重建引用（事务原子性）
- graph.py:         编排：全量重建图谱 + 图查询 + 过期传播
- service.py:       Service 编排层（DB 操作 + 调用纯逻辑模块）
"""
