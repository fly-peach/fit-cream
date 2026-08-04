"""
记忆处理流水线 (Memory Pipeline)

自动化的记忆管理流程：
1. 提取 (Extract): 从对话中提取记忆
2. 整合 (Consolidate): 融合新旧记忆，处理冲突
3. 存储 (Store): 存入对应记忆库
4. 遗忘 (Forget): 应用遗忘曲线
5. 反思 (Reflect): 定期总结，知识升华

用法：
    from src.agents.harness.runtime.memory.pipeline import MemoryPipeline
    
    pipeline = MemoryPipeline(store, extractor)
    
    # 处理对话
    await pipeline.process_conversation(user_id, messages)
    
    # 定期整合
    await pipeline.consolidate_memories(user_id)
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional
import logging

from langchain_core.messages import BaseMessage
from langchain_core.language_models import BaseChatModel
from sqlalchemy import update

from src.agents.harness.runtime.memory.store import MemoryStore, get_memory_store
from src.agents.harness.runtime.memory.extractor import MemoryExtractor, ExtractionResult
from src.agents.models.memory import SemanticMemory, MemoryConsolidationLog

logger = logging.getLogger("fitcream.memory")


CONSOLIDATE_PROMPT = """\
你是一个记忆整合专家。以下是对用户的语义记忆（事实三元组）。请从中提炼出更高层次的洞察或规律，作为新的语义记忆。

已有记忆：
{memories}

要求：
- 只提炼有充分依据的洞察，不要臆测
- 每条洞察为三元组 (subject, predicate, object)
- subject 通常为 "用户"
- predicate 描述模式/规律（如 "运动偏好"、"饮食倾向"）
- object 具体内容
- 最多 5 条
- 若无值得提炼的洞察，返回空数组

输出 JSON（不要包含 markdown 代码块标记）：
{{
  "insights": [
    {{"subject": "用户", "predicate": "...", "object": "...", "category": "insight", "confidence": 0.7}}
  ]
}}
"""


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
        self.llm = llm
        
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
                logger.error(f"Failed to store episodic memory: {e}")
        
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
                logger.error(f"Failed to store semantic memory: {e}")
        
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
                logger.error(f"Failed to store procedural memory: {e}")
        
        return stats
    
    async def consolidate_memories(
        self,
        user_id: str,
    ) -> dict:
        """
        整合记忆

        1. 合并重复：同 (subject, predicate) 的多条 active，保留 version 最大，
           其余标记 superseded（建立版本链）。
        2. LLM 升华：从已有语义记忆提炼更高层次洞察，去重后存为新记忆。
        3. 记录整合日志到 memory_consolidation_logs。

        Args:
            user_id: 用户 ID

        Returns:
            整合结果统计 {"merged", "conflicts_resolved", "insights"}
        """
        stats = {"merged": 0, "conflicts_resolved": 0, "insights": 0}

        semantics = await self.store.retrieve_semantic(user_id, limit=100)
        if not semantics:
            return stats

        # 1. 合并重复 active：同 (subject, predicate) 保留 version 最大
        groups: dict[str, list] = {}
        for mem in semantics:
            groups.setdefault(f"{mem.subject}:{mem.predicate}", []).append(mem)
        merged_pairs: list[tuple] = []
        for mems in groups.values():
            if len(mems) <= 1:
                continue
            mems.sort(key=lambda m: (m.version or 0), reverse=True)
            keeper = mems[0]
            for m in mems[1:]:
                merged_pairs.append((m.id, keeper.id))
                stats["merged"] += 1
        if merged_pairs:
            async with self.store.async_session() as session:
                for mid, keeper_id in merged_pairs:
                    await session.execute(
                        update(SemanticMemory)
                        .where(SemanticMemory.id == mid)
                        .values(
                            status="superseded",
                            superseded_by=keeper_id,
                            updated_at=datetime.utcnow(),
                        )
                    )
                await session.commit()

        # 2. LLM 升华：提炼更高层洞察
        llm = self.llm or (self.extractor.llm if self.extractor else None)
        result_ids: list = []
        if llm is not None:
            try:
                triples = "\n".join(
                    f"- {m.to_triple_string()} [{m.category}]" for m in semantics
                )
                resp = await llm.ainvoke(
                    [("human", CONSOLIDATE_PROMPT.format(memories=triples))]
                )
                insights = self._parse_insights(resp.content)
            except Exception as e:
                logger.warning(f"consolidate LLM insight failed: {e}")
                insights = []

            for ins in insights:
                # 去重：同 (subject, predicate) 已有 active 则跳过
                existing = await self.store.retrieve_semantic(
                    user_id,
                    subject=ins.get("subject"),
                    predicate=ins.get("predicate"),
                    limit=1,
                )
                if existing:
                    continue
                try:
                    rid = await self.store.store_semantic(
                        user_id=user_id,
                        subject=ins.get("subject", "用户"),
                        predicate=ins.get("predicate", ""),
                        object=ins.get("object", ""),
                        category=ins.get("category", "insight"),
                        confidence=float(ins.get("confidence", 0.7)),
                    )
                    result_ids.append(rid)
                    stats["insights"] += 1
                except Exception as e:
                    logger.error(f"consolidate store insight failed: {e}")

        # 3. 记录整合日志
        try:
            async with self.store.async_session() as session:
                log = MemoryConsolidationLog(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    consolidation_type="reflect",
                    source_memory_ids=[m.id for m in semantics[:20]],
                    result_memory_id=result_ids[0] if result_ids else None,
                    details=stats,
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"consolidate log failed: {e}")

        return stats

    def _parse_insights(self, content: str) -> list[dict]:
        """解析 LLM 升华响应，容错 markdown 代码块"""
        import json
        import re

        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", content)
            if not m:
                return []
            try:
                data = json.loads(m.group())
            except json.JSONDecodeError:
                return []
        if not isinstance(data, dict):
            return []
        return data.get("insights", []) or []
    
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