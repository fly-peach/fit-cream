"""
知识库模块包

架构分层（参考 LLM Wiki 的纯逻辑/编排分离设计）：
- models/:          ORM 模型（knowledge_base / document / chunk / reference）
- schemas/:         Pydantic 请求/响应模型（knowledge_base / document / search / graph / index / lint）
- services/:        Service 编排层（knowledge_base / document / search / graph）
- chunker.py:       纯：文本分块（CJK token 估算 + 超长兜底，零 DB 依赖）
- frontmatter.py:   纯：YAML frontmatter 解析 + 标题/标签提取（零 DB 依赖）
- references.py:    纯：引用解析（3 层查找映射 + 相对路径解析，零 DB 依赖）
- schema_templates.py: 纯：实体类型模板（健身领域）
- lint.py:          纯：知识库健康检查规则
- indexer.py:       编排：分块 + 写 chunks（事务原子性）
- graph.py:         编排：全量重建图谱 + 图查询 + 过期传播

入库流程：MCP 写 wiki 文档（不自动索引）→ 管理员核验 →「重建 lint」统一重建搜索索引+引用图+lint。
"""
