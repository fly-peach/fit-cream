"""
Agent 数据模型包

集中存放 Agent 子系统相关的 ORM 模型：
- conversation: 对话消息记录（conversations 表，继承 app Base）
- thread_base/thread_usage/thread_meta: 对话线程维度（token 用量、标题等，继承 app Base）
- memory: 分层记忆模型（episodic/semantic/procedural_memories 等，独立 MemoryBase）

模型注册与统一聚合导入由 app 层的 app.models 入口负责。
"""
