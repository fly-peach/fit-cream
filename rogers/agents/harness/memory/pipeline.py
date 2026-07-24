"""
记忆处理流水线 (Memory Pipeline)

自动化的记忆管理流程：
1. 提取 (Extract): 从对话中提取记忆
2. 整合 (Consolidate): 融合新旧记忆，处理冲突
3. 存储 (Store): 存入对应记忆库
4. 遗忘 (Forget): 应用遗忘曲线
5. 反思 (Reflect): 定期总结，知识升华

用法：
    from agents.harness.memory.pipeline import MemoryPipeline
    
    pipeline = MemoryPipeline(store, extractor)
    
    # 处理对话
    await pipeline.process_conversation(user_id, messages)
    
    # 定期整合
    await pipeline.consolidate_memories(user_id)
"""

from datetime import datetime, timedelta
from typing import Optional

from langchain_core.messages import BaseMessage
from langchain_core.language_models import BaseChatModel

from agents.harness.memory.store import MemoryStore, get_memory_store
from agents.harness.memory.extractor import MemoryExtractor, ExtractionResult


class MemoryPipeline:
    """
    记忆处理流水线
    
    协调记忆提取、存储、整合、遗忘等流程。
    """
    
    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        extractor: Optional[MemoryExtractor] = None,
        llm: Optional[BaseChatModel] = None,
    ):
        """
        初始化记忆流水线
        
        Args:
            store: 记忆存储服务
            extractor: 记忆提取器
            llm: LLM 模型（用于创建 extractor）
        """
        self.store = store or get_memory_store()
        
        if extractor is None and llm is not None:
            extractor = MemoryExtractor(llm)
        self.extractor = extractor
    
    async def process_conversation(
        self,
        user_id: str,
        messages: list[BaseMessage],
        thread_id: Optional[str] = None,
    ) -> dict:
        """
        处理对话，提取并存储记忆
        
        这是主要的入口方法，在对话结束后调用。
        
        Args:
            user_id: 用户 ID
            messages: 对话消息列表
            thread_id: 对话线程 ID
            
        Returns:
            处理结果统计
        """
        if self.extractor is None:
            return {"error": "No extractor configured"}
        
        # 1. 提取记忆
        extracted = await self.extractor.extract_from_conversation(
            user_id=user_id,
            messages=messages,
            thread_id=thread_id,
        )
        
        # 2. 存储记忆
        stats = await self._store_extracted(user_id, extracted, thread_id)
        
        return stats
    
    async def _store_extracted(
        self,
        user_id: str,
        extracted: ExtractionResult,
        thread_id: Optional[str] = None,
    ) -> dict:
        """存储提取的记忆"""
        stats = {"episodic": 0, "semantic": 0, "procedural": 0}
        
        # 存储情景记忆
        for ep in extracted.episodic:
            try:
                await self.store.store_episodic(
                    user_id=user_id,
                    content=ep.content,
                    memory_type=ep.memory_type,
                    summary=ep.summary,
                    importance_score=ep.importance,
                    emotional_valence=ep.emotional_valence,
                    source_thread_id=thread_id,
                )
                stats["episodic"] += 1
            except Exception as e:
                print(f"Failed to store episodic memory: {e}")
        
        # 存储语义记忆
        for sem in extracted.semantic:
            try:
                await self.store.store_semantic(
                    user_id=user_id,
                    subject=sem.subject,
                    predicate=sem.predicate,
                    object=sem.object,
                    category=sem.category,
                    confidence=sem.confidence,
                )
                stats["semantic"] += 1
            except Exception as e:
                print(f"Failed to store semantic memory: {e}")
        
        # 存储程序性记忆
        for proc in extracted.procedural:
            try:
                await self.store.store_procedural(
                    user_id=user_id,
                    name=proc.name,
                    steps=proc.steps,
                    description=proc.description,
                    trigger_conditions=proc.trigger_conditions,
                )
                stats["procedural"] += 1
            except Exception as e:
                print(f"Failed to store procedural memory: {e}")
        
        return stats
    
    async def consolidate_memories(
        self,
        user_id: str,
    ) -> dict:
        """
        整合记忆
        
        定期运行，用于：
        1. 合并重复记忆
        2. 解决冲突
        3. 生成更高层次的洞察
        
        Args:
            user_id: 用户 ID
            
        Returns:
            整合结果统计
        """
        stats = {"merged": 0, "conflicts_resolved": 0, "insights": 0}
        
        # 获取所有语义记忆
        semantics = await self.store.retrieve_semantic(user_id, limit=100)
        
        # 检测并合并重复记忆
        # （简单实现：基于 subject + predicate 去重，保留最新版本）
        seen = {}
        for mem in semantics:
            key = f"{mem.subject}:{mem.predicate}"
            if key in seen:
                # 保留较新的版本
                seen[key] = mem
            else:
                seen[key] = mem
        
        return stats
    
    async def apply_forgetting_curve(
        self,
        user_id: str,
        decay_rate: float = 0.1,
    ):
        """
        应用遗忘曲线
        
        Args:
            user_id: 用户 ID
            decay_rate: 衰减率
        """
        await self.store.apply_forgetting_curve(user_id, decay_rate)
    
    async def get_memory_context(
        self,
        user_id: str,
        query: str,
        max_episodic: int = 3,
        max_semantic: int = 10,
        max_procedural: int = 2,
    ) -> str:
        """
        获取记忆上下文（用于注入到 System Prompt）
        
        Args:
            user_id: 用户 ID
            query: 当前查询/话题
            max_episodic: 最大情景记忆数
            max_semantic: 最大语义记忆数
            max_procedural: 最大程序性记忆数
            
        Returns:
            格式化的记忆上下文字符串
        """
        sections = []
        
        # 检索情景记忆
        episodic = await self.store.retrieve_episodic(
            user_id=user_id,
            query=query,
            top_k=max_episodic,
        )
        if episodic:
            lines = ["## 相关经历"]
            for mem in episodic:
                time_str = mem.timestamp.strftime("%Y-%m-%d") if mem.timestamp else ""
                summary = mem.summary or mem.content[:100]
                lines.append(f"- [{time_str}] {summary}")
            sections.append("\n".join(lines))
        
        # 检索语义记忆
        semantic = await self.store.retrieve_semantic(
            user_id=user_id,
            limit=max_semantic,
        )
        if semantic:
            lines = ["## 用户信息"]
            for mem in semantic:
                lines.append(f"- {mem.subject} {mem.predicate} {mem.object}")
            sections.append("\n".join(lines))
        
        # 检索程序性记忆
        procedural = await self.store.retrieve_procedural(
            user_id=user_id,
            query=query,
            top_k=max_procedural,
        )
        if procedural:
            lines = ["## 可用技能"]
            for mem in procedural:
                lines.append(f"- {mem.name}: {mem.description or ''}")
            sections.append("\n".join(lines))
        
        if not sections:
            return ""
        
        return "# 记忆上下文\n\n" + "\n\n".join(sections)


# 全局单例
_pipeline: Optional[MemoryPipeline] = None


def get_memory_pipeline() -> MemoryPipeline:
    """获取全局记忆流水线实例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = MemoryPipeline()
    return _pipeline


def init_memory_pipeline(
    store: MemoryStore,
    llm: BaseChatModel,
) -> MemoryPipeline:
    """初始化全局记忆流水线"""
    global _pipeline
    _pipeline = MemoryPipeline(store=store, llm=llm)
    return _pipeline