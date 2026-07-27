"""
FitCream 分层认知记忆架构

基于 LlamaIndex + 阿里 DashScope Embedding 实现的记忆系统。

架构层次：
- 工作记忆 (Working Memory): LangGraph State + Checkpointer
- 情景记忆 (Episodic Memory): 向量化存储对话事件
- 语义记忆 (Semantic Memory): 结构化事实/偏好/规则
- 程序性记忆 (Procedural Memory): 可复用工作流/技能

用法：
    from src.agents.harness.memory import (
        MemoryStore,
        MemoryExtractor,
        MemoryPipeline,
        create_memory_tools,
        get_embedding_model,
    )

    # 初始化
    store = MemoryStore()
    extractor = MemoryExtractor()
    pipeline = MemoryPipeline(store=store, extractor=extractor)

    # 会话结束后提取记忆
    await pipeline.process_conversation(user_id, messages)

    # 检索记忆
    memories = await store.search_episodic(user_id, query="健身计划")
"""

from src.agents.harness.memory.embeddings import (
    create_embedding_model,
    get_embedding_model,
    get_embedding_dimension,
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
)
from src.agents.harness.memory.store import MemoryStore, get_memory_store
from src.agents.harness.memory.extractor import MemoryExtractor, ExtractionResult
from src.agents.harness.memory.pipeline import MemoryPipeline
from src.agents.harness.memory.tools import create_memory_tools

__all__ = [
    # Embeddings
    "create_embedding_model",
    "get_embedding_model",
    "get_embedding_dimension",
    "DEFAULT_EMBEDDING_MODEL",
    "EMBEDDING_DIMENSION",
    # Store
    "MemoryStore",
    "get_memory_store",
    # Extractor
    "MemoryExtractor",
    "ExtractionResult",
    # Pipeline
    "MemoryPipeline",
    # Tools
    "create_memory_tools",
]