"""
DashScope Embedding 模型配置

使用阿里云 DashScope 的 text-embedding-v3 模型进行文本向量化。
支持同步和异步调用，用于记忆系统的向量化存储和检索。

模型选择：
- text-embedding-v3: 1024 维，性价比高（推荐）
- text-embedding-v2: 1536 维，精度更高
- text-embedding-v1: 1536 维，旧版本

用法：
    from src.agents.harness.runtime.memory.embeddings import create_embedding_model, get_embedding_model
    
    # 创建新实例
    embed_model = create_embedding_model()
    
    # 获取全局单例
    embed_model = get_embedding_model()
    
    # 生成 embedding
    embedding = await embed_model.aget_text_embedding("你好世界")
"""

import os
from typing import Optional
from functools import lru_cache

from llama_index.embeddings.dashscope import (
    DashScopeEmbedding,
    DashScopeTextEmbeddingModels,
)


def _get_setting(key: str, default: str = "") -> str:
    """获取配置值，优先从 app.config.settings 读取"""
    try:
        from app.config import settings
        return str(getattr(settings, key, default))
    except Exception:
        return os.getenv(key, default)


# 默认 embedding 模型
DEFAULT_EMBEDDING_MODEL = _get_setting(
    "DASHSCOPE_EMBEDDING_MODEL", 
    "text-embedding-v3"
)

# Embedding 维度（text-embedding-v3 默认 1024）
EMBEDDING_DIMENSION = int(_get_setting("EMBEDDING_DIMENSION", "1024"))


def create_embedding_model(
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> DashScopeEmbedding:
    """
    创建 DashScope Embedding 模型实例。
    
    Args:
        model_name: 模型名称，默认使用 text-embedding-v3
        api_key: DashScope API Key，默认从配置读取
        
    Returns:
        DashScopeEmbedding 实例
        
    Example:
        embed_model = create_embedding_model()
        embedding = await embed_model.aget_text_embedding("健身计划")
    """
    if model_name is None:
        model_name = DEFAULT_EMBEDDING_MODEL
    
    if api_key is None:
        api_key = _get_setting("DASHSCOPE_API_KEY")
    
    # 映射模型名称到枚举（如果支持）
    model_enum = _get_model_enum(model_name)
    
    return DashScopeEmbedding(
        model_name=model_enum or model_name,
        api_key=api_key,
    )


def _get_model_enum(model_name: str):
    """将模型名称映射到 DashScopeTextEmbeddingModels 枚举"""
    model_map = {
        "text-embedding-v1": DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V1,
        "text-embedding-v2": DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V2,
        "text-embedding-v3": DashScopeTextEmbeddingModels.TEXT_EMBEDDING_V3,
    }
    return model_map.get(model_name)


@lru_cache(maxsize=1)
def get_embedding_model() -> DashScopeEmbedding:
    """
    获取全局 Embedding 模型单例。
    
    使用 lru_cache 确保只创建一个实例，避免重复初始化。
    
    Returns:
        DashScopeEmbedding 实例
    """
    return create_embedding_model()


def get_embedding_dimension() -> int:
    """获取当前 embedding 模型的向量维度"""
    return EMBEDDING_DIMENSION


# ============================================================
# 通用 rerank（DashScope gte-rerank-v2）
# ============================================================

# rerank 后处理器（进程级缓存，懒加载；未启用/加载失败为 None）
_reranker = None


def _rerank_enabled() -> bool:
    try:
        from app.config import get_settings

        return bool(getattr(get_settings(), "RERANK_ENABLED", True))
    except Exception:
        return _get_setting("RERANK_ENABLED", "true").lower() in (
            "1",
            "true",
            "yes",
        )


def _rerank_model() -> str:
    try:
        from app.config import get_settings

        return str(getattr(get_settings(), "RERANK_MODEL", "gte-rerank-v2"))
    except Exception:
        return _get_setting("RERANK_MODEL", "gte-rerank-v2")


def _load_reranker():
    """懒加载 DashScopeRerank 后处理器；未启用/缺失依赖时返回 None（进程内只加载一次）。"""
    global _reranker
    if _reranker is not None:
        return _reranker
    if not _rerank_enabled():
        return None
    try:
        from llama_index.postprocessor.dashscope_rerank import DashScopeRerank

        _reranker = DashScopeRerank(
            model=_rerank_model(),
            top_n=int(_get_setting("RERANK_TOP_N", "20")),
        )
        return _reranker
    except Exception as e:
        logger = __import__("logging").getLogger("fitcream")
        logger.warning("rerank 后处理器加载失败（回退原序）: %s", e)
        return None


async def rerank_texts(
    query: str, texts: list[str], top_n: int | None = None
) -> list[int]:
    """对候选文本按 query 相关度重排，返回重排后的索引列表。

    - 未启用 / 依赖缺失 / 执行异常：回退原序 ``list(range(len(texts)))``。
    - ``top_n`` 缺省时返回全量重排结果。
    """
    if not texts:
        return []
    postprocessor = _load_reranker()
    if postprocessor is None:
        return list(range(len(texts)))

    from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

    try:
        query_bundle = QueryBundle(query_str=query)
        nodes = [
            NodeWithScore(
                node=TextNode(text=t, metadata={"index": i}), score=0.0
            )
            for i, t in enumerate(texts)
        ]
        reranked = postprocessor.postprocess_nodes(nodes, query_bundle)

        ordered: list[int] = []
        for n in reranked:
            node = getattr(n, "node", n)
            metadata = getattr(node, "metadata", {}) or {}
            idx = metadata.get("index", None)
            if not isinstance(idx, int) or not (0 <= idx < len(texts)):
                return list(range(len(texts)))
            ordered.append(idx)
        chosen = set(ordered)
        ordered.extend(i for i in range(len(texts)) if i not in chosen)
        return ordered[:top_n] if top_n is not None else ordered
    except Exception:
        return list(range(len(texts)))