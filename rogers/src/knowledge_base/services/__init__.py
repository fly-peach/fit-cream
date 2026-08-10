"""
知识库 Service 层

所有 Service 类均为纯静态方法，不持有状态。
Agent Tools 和 FastAPI Routers 共同调用此层，实现业务复用。

- KnowledgeBaseService: 知识库主体 CRUD + slug
- KBDocumentService:    文档 CRUD + 自动分块索引
- KBSearchService:      全文/向量混合检索 + 跨库搜索
- KBGraphService:       图谱 / 索引 / 引用
"""