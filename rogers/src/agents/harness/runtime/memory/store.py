"""
记忆存储与检索服务

提供统一的记忆存储和检索接口，支持：
- 情景记忆：向量语义检索 + 时间范围过滤
- 语义记忆：结构化查询 + 版本管理
- 程序性记忆：向量语义检索

使用 LlamaIndex 进行向量化和检索。

用法：
    from src.agents.harness.runtime.memory.store import MemoryStore, get_memory_store
    
    store = get_memory_store()
    
    # 存储情景记忆
    memory_id = await store.store_episodic(
        user_id="user-123",
        content="今天完成了 5 公里跑步",
        memory_type="event",
    )
    
    # 检索情景记忆
    results = await store.retrieve_episodic(
        user_id="user-123",
        query="跑步记录",
        top_k=5,
    )
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, text, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from llama_index.vector_stores.postgres import PGVectorStore

from src.agents.harness.runtime.memory.embeddings import get_embedding_model, get_embedding_dimension
from src.agents.models.memory import (
    MemoryBase,
    EpisodicMemory,
    SemanticMemory,
    ProceduralMemory,
    MemoryConsolidationLog,
)


def _get_setting(key: str, default: str = "") -> str:
    """获取配置值，优先从 app.config.settings 读取，回退到环境变量"""
    try:
        from app.config import settings
        return str(getattr(settings, key, default))
    except Exception:
        return os.getenv(key, default)


class MemoryStore:
    """
    统一记忆存储服务
    
    提供三层记忆的存储和检索功能：
    - 情景记忆：支持语义检索 + 时间过滤
    - 语义记忆：支持结构化查询 + 版本管理
    - 程序性记忆：支持语义检索
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        embed_model=None,
    ):
        """
        初始化记忆存储
        
        Args:
            database_url: PostgreSQL 连接字符串
            embed_model: Embedding 模型实例
        """
        if database_url is None:
            database_url = _get_setting(
                "DATABASE_URL",
                "postgresql+asyncpg://fitcream:fitcream@localhost:5432/fitcream"
            )
        
        self.database_url = database_url
        self.embed_model = embed_model or get_embedding_model()

        # 每用户记忆容量上限（0 表示不限制）
        self.episodic_max = int(_get_setting("MEMORY_EPISODIC_MAX", "200"))
        self.procedural_max = int(_get_setting("MEMORY_PROCEDURAL_MAX", "50"))
        # 语义记忆每分类上限，超出按 低置信度→最旧 裁剪
        self.semantic_cap_each = int(_get_setting("MEMORY_SEMANTIC_MAX", "15"))
        # 受上限约束的语义分类（全部分类统一裁剪）
        self.semantic_capped_categories = ("preference", "fact", "rule", "status")
        
        # 创建异步引擎（使用与主应用相同的连接池配置）
        pool_size = int(_get_setting("DB_POOL_SIZE", "10"))
        max_overflow = int(_get_setting("DB_MAX_OVERFLOW", "20"))
        pool_timeout = int(_get_setting("DB_POOL_TIMEOUT", "30"))
        self.engine = create_async_engine(
            database_url, echo=False,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # LlamaIndex 向量存储（延迟初始化）
        self._vector_store = None
    
    async def init_db(self):
        """初始化数据库表"""
        async with self.engine.begin() as conn:
            # 创建 pgvector 扩展
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            # 创建表
            await conn.run_sync(MemoryBase.metadata.create_all)
    
    def _get_vector_store(self) -> PGVectorStore:
        """获取 LlamaIndex 向量存储（延迟初始化）"""
        if self._vector_store is None:
            # 转换为 psycopg 格式（去掉 +asyncpg 后缀）
            psycopg_url = self.database_url.replace("+asyncpg", "")

            # 从连接串解析各参数（格式: postgresql://user:pass@host:port/db）
            # user: // 后到第一个 : 之间
            # password: 最后一个 : 到 @ 之间
            # host: @ 后到第一个 : 之间
            # port: host 后到 / 之间
            # database: 最后一个 / 之后
            self._vector_store = PGVectorStore.from_params(
                database=psycopg_url.split("/")[-1],
                host=psycopg_url.split("@")[-1].split(":")[0],
                port=psycopg_url.split(":")[-1].split("/")[0],
                user=psycopg_url.split("//")[-1].split(":")[0],
                password=psycopg_url.split(":")[-1].split("@")[0],
                table_name="memory_vectors",
                embed_dim=get_embedding_dimension(),
            )
        return self._vector_store
    
    # ============================================================
    # 情景记忆 (Episodic Memory)
    # ============================================================

    async def _trim_memories(
        self,
        user_id: str,
        model,
        max_count: int,
        order_by,
        clear_episodic_refs: bool = False,
    ) -> int:
        """
        裁剪记忆到上限条数，删除多余记录。

        Args:
            user_id: 用户 ID
            model: 记忆模型（EpisodicMemory / ProceduralMemory）
            max_count: 上限条数（0 表示不限制）
            order_by: 删除优先级排序（排在最前的先删，即最旧的/最低重要性的）
            clear_episodic_refs: 删除情景记忆前清空 semantic 的 source_episodic_id 引用

        Returns:
            删除条数
        """
        if max_count <= 0:
            return 0
        async with self.async_session() as session:
            total = await session.scalar(
                select(func.count()).select_from(model).where(model.user_id == user_id)
            )
            excess = int(total or 0) - max_count
            if excess <= 0:
                return 0
            ids = (
                await session.scalars(
                    select(model.id)
                    .where(model.user_id == user_id)
                    .order_by(*order_by)
                    .limit(excess)
                )
            ).all()
            if not ids:
                return 0
            if clear_episodic_refs:
                await session.execute(
                    update(SemanticMemory)
                    .where(SemanticMemory.source_episodic_id.in_(ids))
                    .values(source_episodic_id=None)
                )
            await session.execute(delete(model).where(model.id.in_(ids)))
            await session.commit()
            return len(ids)

    async def _trim_semantic_by_category(
        self,
        user_id: str,
        category: str,
        max_count: int,
    ) -> int:
        """
        裁剪某分类的语义记忆到上限，删除多余的 active 记录。

        删除优先级：低置信度 → 更新时间最旧 → 创建时间最旧。

        Args:
            user_id: 用户 ID
            category: 语义分类（preference/fact/rule）
            max_count: 上限条数（0 表示不限制）

        Returns:
            删除条数
        """
        if max_count <= 0:
            return 0
        async with self.async_session() as session:
            total = await session.scalar(
                select(func.count())
                .select_from(SemanticMemory)
                .where(
                    SemanticMemory.user_id == user_id,
                    SemanticMemory.category == category,
                    SemanticMemory.status == "active",
                )
            )
            excess = int(total or 0) - max_count
            if excess <= 0:
                return 0
            ids = (
                await session.scalars(
                    select(SemanticMemory.id)
                    .where(
                        SemanticMemory.user_id == user_id,
                        SemanticMemory.category == category,
                        SemanticMemory.status == "active",
                    )
                    .order_by(
                        SemanticMemory.confidence.asc(),
                        SemanticMemory.updated_at.asc(),
                        SemanticMemory.created_at.asc(),
                    )
                    .limit(excess)
                )
            ).all()
            if not ids:
                return 0
            await session.execute(
                delete(SemanticMemory).where(SemanticMemory.id.in_(ids))
            )
            await session.commit()
            return len(ids)

    async def store_episodic(
        self,
        user_id: str,
        content: str,
        memory_type: str = "conversation",
        summary: Optional[str] = None,
        importance_score: float = 0.5,
        emotional_valence: str = "neutral",
        timestamp: Optional[datetime] = None,
        source_thread_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> uuid.UUID:
        """
        存储情景记忆
        
        Args:
            user_id: 用户 ID
            content: 记忆内容
            memory_type: 记忆类型 (conversation/event/observation)
            summary: 摘要（可选，不提供则使用 content）
            importance_score: 重要性评分 (0-1)
            emotional_valence: 情感倾向 (positive/negative/neutral)
            timestamp: 事件时间
            source_thread_id: 来源对话线程 ID
            metadata: 额外元数据
            
        Returns:
            记忆 ID
        """
        # 生成 embedding
        embedding = await self.embed_model.aget_text_embedding(content)
        
        memory = EpisodicMemory(
            id=uuid.uuid4(),
            user_id=user_id,
            content=content,
            summary=summary or content[:200],
            embedding=embedding,
            memory_type=memory_type,
            importance_score=importance_score,
            emotional_valence=emotional_valence,
            timestamp=timestamp or datetime.utcnow(),
            source_thread_id=source_thread_id,
            **(metadata or {}),
        )
        
        async with self.async_session() as session:
            session.add(memory)
            await session.commit()
        
        # 裁剪：超出上限时按 重要性升序 → 时间升序 删除（低重要性且最旧的先删）
        await self._trim_memories(
            user_id,
            EpisodicMemory,
            self.episodic_max,
            [
                EpisodicMemory.importance_score.asc(),
                EpisodicMemory.timestamp.asc(),
                EpisodicMemory.created_at.asc(),
            ],
            clear_episodic_refs=True,
        )
        
        return memory.id
    
    async def update_episodic(
        self,
        user_id: str,
        memory_id: uuid.UUID,
        content: Optional[str] = None,
        summary: Optional[str] = None,
        importance_score: Optional[float] = None,
    ) -> bool:
        """
        更新一条情景记忆（按 id）。

        若更新 content 且未提供 summary，则顺带更新 summary；embedding 由
        调用方决定是否重算（此处保留原向量，避免额外嵌入调用）。

        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID
            content: 新内容
            summary: 新摘要
            importance_score: 新重要性

        Returns:
            是否更新成功
        """
        async with self.async_session() as session:
            row = await session.get(EpisodicMemory, memory_id)
            if row is None or str(row.user_id) != str(user_id):
                return False
            if content is not None:
                row.content = content
                row.embedding = await self.embed_model.aget_text_embedding(content)
            if summary is not None:
                row.summary = summary
            elif content is not None and row.summary:
                row.summary = content[:200]
            if importance_score is not None:
                row.importance_score = importance_score
            row.updated_at = datetime.utcnow()
            await session.commit()
            return True

    async def delete_episodic(
        self,
        user_id: str,
        memory_id: uuid.UUID,
    ) -> bool:
        """
        删除一条情景记忆（按 id，硬删）。

        同时清空由它派生的语义记忆的 source_episodic_id 引用。

        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID

        Returns:
            是否删除成功
        """
        async with self.async_session() as session:
            row = await session.get(EpisodicMemory, memory_id)
            if row is None or str(row.user_id) != str(user_id):
                return False
            await session.execute(
                update(SemanticMemory)
                .where(SemanticMemory.source_episodic_id == memory_id)
                .values(source_episodic_id=None)
            )
            await session.delete(row)
            await session.commit()
            return True
    
    async def retrieve_episodic(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        time_range: Optional[tuple[datetime, datetime]] = None,
        memory_types: Optional[list[str]] = None,
        min_importance: float = 0.0,
    ) -> list[EpisodicMemory]:
        """
        检索情景记忆（语义 + 时间 + 重要性）
        
        Args:
            user_id: 用户 ID
            query: 查询内容
            top_k: 返回数量
            time_range: 时间范围 (start, end)
            memory_types: 记忆类型过滤
            min_importance: 最小重要性
            
        Returns:
            匹配的记忆列表
        """
        # 生成查询向量
        query_embedding = await self.embed_model.aget_text_embedding(query)
        
        async with self.async_session() as session:
            # 构建查询
            stmt = select(EpisodicMemory).where(
                EpisodicMemory.user_id == user_id,
                EpisodicMemory.importance_score >= min_importance,
            )
            
            # 时间范围过滤
            if time_range:
                stmt = stmt.where(
                    EpisodicMemory.timestamp >= time_range[0],
                    EpisodicMemory.timestamp <= time_range[1],
                )
            
            # 类型过滤
            if memory_types:
                stmt = stmt.where(EpisodicMemory.memory_type.in_(memory_types))
            
            # 获取所有候选记忆，在内存中计算余弦相似度（pgvector 原生排序需 SQL 函数支持）
            result = await session.execute(stmt)
            candidates = result.scalars().all()

            # 计算查询向量与每条候选记忆的相似度
            scored_memories = []
            for memory in candidates:
                if memory.embedding:
                    similarity = self._cosine_similarity(query_embedding, memory.embedding)
                    scored_memories.append((memory, similarity))

            # 按相似度降序排序
            scored_memories.sort(key=lambda x: x[1], reverse=True)
            
            # 更新访问计数（用于遗忘曲线计算）
            top_memories = [m for m, _ in scored_memories[:top_k]]
            for memory in top_memories:
                memory.access_count += 1
                memory.last_accessed = datetime.utcnow()
            
            await session.commit()
            
            return top_memories
    
    async def get_recent_episodic(
        self,
        user_id: str,
        limit: int = 10,
        days: int = 7,
    ) -> list[EpisodicMemory]:
        """
        获取最近的情景记忆
        
        Args:
            user_id: 用户 ID
            limit: 返回数量
            days: 最近天数
            
        Returns:
            记忆列表
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        async with self.async_session() as session:
            stmt = (
                select(EpisodicMemory)
                .where(
                    EpisodicMemory.user_id == user_id,
                    EpisodicMemory.timestamp >= cutoff,
                )
                .order_by(EpisodicMemory.timestamp.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()
    
    # ============================================================
    # 语义记忆 (Semantic Memory)
    # ============================================================
    
    async def store_semantic(
        self,
        user_id: str,
        subject: str,
        predicate: str,
        object: str,
        category: str = "fact",
        confidence: float = 1.0,
        source_episodic_id: Optional[uuid.UUID] = None,
    ) -> uuid.UUID:
        """
        存储语义记忆（事实三元组）
        
        支持版本管理：如果已存在相同的 (subject, predicate)，
        旧版本会被标记为 superseded。
        
        Args:
            user_id: 用户 ID
            subject: 主体（如 "用户"）
            predicate: 关系（如 "偏好"）
            object: 对象（如 "Python"）
            category: 分类 (preference/fact/rule/status)
            confidence: 置信度
            source_episodic_id: 来源情景记忆 ID
            
        Returns:
            记忆 ID
        """
        async with self.async_session() as session:
            # 事务级咨询锁：串行化同 (user, subject, predicate) 的写入，
            # 避免并发 read-modify-write 产生重复 active 三元组。
            # 锁随事务提交/回滚自动释放（无需迁移/唯一索引，适配 MemoryBase 不走 Alembic 的现状）。
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:u), hashtext(:sp))"),
                {"u": user_id, "sp": f"{subject}:{predicate}"},
            )

            # 查找已存在的相同事实（同 subject + predicate），用于版本管理
            existing_stmt = select(SemanticMemory).where(
                SemanticMemory.user_id == user_id,
                SemanticMemory.subject == subject,
                SemanticMemory.predicate == predicate,
                SemanticMemory.status == "active",
            )
            result = await session.execute(existing_stmt)
            existing = result.scalar_one_or_none()

            # 版本号递增：新记忆为旧版本号 + 1，首次创建为 1
            new_version = (existing.version + 1) if existing else 1

            memory = SemanticMemory(
                id=uuid.uuid4(),
                user_id=user_id,
                subject=subject,
                predicate=predicate,
                object=object,
                category=category,
                confidence=confidence,
                source_episodic_id=source_episodic_id,
                version=new_version,
                status="active",
            )

            # 标记旧版本为 superseded，建立版本链
            if existing:
                existing.status = "superseded"
                existing.superseded_by = memory.id
                existing.updated_at = datetime.utcnow()

            session.add(memory)
            await session.commit()

            memory_id = memory.id

        # 裁剪：超出分类上限（preference/fact/rule）时删除多余 active 记录
        if category in self.semantic_capped_categories:
            await self._trim_semantic_by_category(
                user_id, category, self.semantic_cap_each
            )

        return memory_id

    async def update_semantic(
        self,
        user_id: str,
        memory_id: uuid.UUID,
        object: Optional[str] = None,
        category: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> bool:
        """
        更新一条语义记忆（按 id）。

        仅更新 object / category / confidence，predicate 保持不变，
        避免破坏 (subject, predicate) 版本化分组的版本链。

        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID
            object: 新对象值
            category: 新分类
            confidence: 新置信度

        Returns:
            是否更新成功（记忆不存在或不属于该用户返回 False）
        """
        async with self.async_session() as session:
            row = await session.get(SemanticMemory, memory_id)
            if (
                row is None
                or str(row.user_id) != str(user_id)
                or row.status != "active"
            ):
                return False
            if object is not None:
                row.object = object
            if category is not None:
                row.category = category
            if confidence is not None:
                row.confidence = confidence
            row.updated_at = datetime.utcnow()
            await session.commit()
            return True

    async def delete_semantic(
        self,
        user_id: str,
        memory_id: uuid.UUID,
    ) -> bool:
        """
        删除一条语义记忆（按 id，硬删）。

        同时清空其他记忆指向该 id 的 superseded_by 引用，避免悬挂外键。

        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID

        Returns:
            是否删除成功
        """
        async with self.async_session() as session:
            row = await session.get(SemanticMemory, memory_id)
            if row is None or str(row.user_id) != str(user_id):
                return False
            await session.execute(
                update(SemanticMemory)
                .where(SemanticMemory.superseded_by == memory_id)
                .values(superseded_by=None)
            )
            await session.delete(row)
            await session.commit()
            return True

    async def retrieve_semantic(
        self,
        user_id: str,
        category: Optional[str] = None,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        limit: int = 50,
    ) -> list[SemanticMemory]:
        """
        检索语义记忆
        
        Args:
            user_id: 用户 ID
            category: 分类过滤
            subject: 主体过滤
            predicate: 关系过滤
            limit: 返回数量
            
        Returns:
            记忆列表
        """
        async with self.async_session() as session:
            stmt = select(SemanticMemory).where(
                SemanticMemory.user_id == user_id,
                SemanticMemory.status == "active",
            )
            
            if category:
                stmt = stmt.where(SemanticMemory.category == category)
            if subject:
                stmt = stmt.where(SemanticMemory.subject == subject)
            if predicate:
                stmt = stmt.where(SemanticMemory.predicate == predicate)
            
            stmt = stmt.order_by(SemanticMemory.updated_at.desc()).limit(limit)
            
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def search_semantic(
        self,
        user_id: str,
        query: str,
        top_k: int = 10,
    ) -> list[SemanticMemory]:
        """
        语义搜索语义记忆
        
        Args:
            user_id: 用户 ID
            query: 查询内容
            top_k: 返回数量
            
        Returns:
            匹配的记忆列表
        """
        # 获取所有活跃记忆
        all_memories = await self.retrieve_semantic(user_id, limit=100)
        
        # 生成查询向量
        query_embedding = await self.embed_model.aget_text_embedding(query)
        
        # 计算每个记忆的相似度
        scored = []
        for memory in all_memories:
            text = memory.to_triple_string()
            mem_embedding = await self.embed_model.aget_text_embedding(text)
            similarity = self._cosine_similarity(query_embedding, mem_embedding)
            scored.append((memory, similarity))
        
        # 排序并返回 top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        return [m for m, _ in scored[:top_k]]
    
    # ============================================================
    # 程序性记忆 (Procedural Memory)
    # ============================================================
    
    async def store_procedural(
        self,
        user_id: str,
        name: str,
        steps: list[dict],
        description: Optional[str] = None,
        trigger_conditions: Optional[dict] = None,
    ) -> uuid.UUID:
        """
        存储程序性记忆（工作流/技能）
        
        Args:
            user_id: 用户 ID
            name: 技能名称
            steps: 步骤列表 [{"step": 1, "action": "...", "params": {...}}]
            description: 技能描述
            trigger_conditions: 触发条件 {"keywords": [...], "context": "..."}
            
        Returns:
            记忆 ID
        """
        # 生成 embedding（基于名称 + 描述）
        content = f"{name}: {description or ''}"
        embedding = await self.embed_model.aget_text_embedding(content)
        
        memory = ProceduralMemory(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            description=description,
            steps=steps,
            embedding=embedding,
            trigger_conditions=trigger_conditions,
        )
        
        async with self.async_session() as session:
            session.add(memory)
            await session.commit()
        
        # 裁剪：超出上限时按 最久未使用 → 创建时间升序 删除
        await self._trim_memories(
            user_id,
            ProceduralMemory,
            self.procedural_max,
            [
                ProceduralMemory.last_used.asc().nullsfirst(),
                ProceduralMemory.created_at.asc(),
            ],
        )
        
        return memory.id
    
    async def retrieve_procedural(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
    ) -> list[ProceduralMemory]:
        """
        检索程序性记忆
        
        Args:
            user_id: 用户 ID
            query: 查询内容
            top_k: 返回数量
            
        Returns:
            匹配的记忆列表
        """
        query_embedding = await self.embed_model.aget_text_embedding(query)
        
        async with self.async_session() as session:
            stmt = select(ProceduralMemory).where(
                ProceduralMemory.user_id == user_id,
            )
            result = await session.execute(stmt)
            candidates = result.scalars().all()
            
            # 计算相似度
            scored = []
            for memory in candidates:
                if memory.embedding:
                    similarity = self._cosine_similarity(query_embedding, memory.embedding)
                    scored.append((memory, similarity))
            
            scored.sort(key=lambda x: x[1], reverse=True)
            
            # 更新使用统计
            top_memories = [m for m, _ in scored[:top_k]]
            for memory in top_memories:
                memory.last_used = datetime.utcnow()
            
            await session.commit()
            
            return top_memories
    
    async def record_procedural_usage(
        self,
        memory_id: uuid.UUID,
        success: bool,
    ):
        """
        记录程序性记忆使用情况
        
        Args:
            memory_id: 记忆 ID
            success: 是否成功
        """
        async with self.async_session() as session:
            stmt = select(ProceduralMemory).where(ProceduralMemory.id == memory_id)
            result = await session.execute(stmt)
            memory = result.scalar_one_or_none()
            
            if memory:
                if success:
                    memory.success_count += 1
                else:
                    memory.failure_count += 1
                memory.last_used = datetime.utcnow()
                await session.commit()
    
    # ============================================================
    # 遗忘曲线 (Forgetting Curve)
    # ============================================================
    
    async def apply_forgetting_curve(
        self,
        user_id: str,
        decay_rate: float = 0.1,
        min_decay: float = 0.1,
    ):
        """
        应用遗忘曲线，降低长期未访问记忆的权重
        
        基于艾宾浩斯遗忘曲线：
        - 每次访问重置衰减
        - 未访问的记忆逐渐衰减
        
        Args:
            user_id: 用户 ID
            decay_rate: 衰减率
            min_decay: 最小衰减因子
        """
        async with self.async_session() as session:
            stmt = select(EpisodicMemory).where(
                EpisodicMemory.user_id == user_id,
            )
            result = await session.execute(stmt)
            memories = result.scalars().all()
            
            now = datetime.utcnow()
            for memory in memories:
                # 计算未访问天数
                last_access = memory.last_accessed or memory.created_at
                days_since_access = (now - last_access).days
                
                # 应用衰减
                if days_since_access > 1:
                    new_decay = max(
                        min_decay,
                        memory.decay_factor * (1 - decay_rate * days_since_access / 30)
                    )
                    memory.decay_factor = new_decay
            
            await session.commit()
    
    # ============================================================
    # 工具方法
    # ============================================================

    async def delete_all_user(self, user_id: str) -> dict:
        """删除用户全部记忆（情景/语义/程序性 + 整合日志），用于账户注销。

        user_id 为 str（对应用户 UUID 字符串）。先删语义（其 source_episodic_id
        外键引用情景）再删情景，避免外键约束冲突。
        """
        stats = {"episodic": 0, "semantic": 0, "procedural": 0, "consolidation_logs": 0}
        async with self.async_session() as session:
            r = await session.execute(
                delete(SemanticMemory).where(SemanticMemory.user_id == user_id)
            )
            stats["semantic"] = r.rowcount
            r = await session.execute(
                delete(EpisodicMemory).where(EpisodicMemory.user_id == user_id)
            )
            stats["episodic"] = r.rowcount
            r = await session.execute(
                delete(ProceduralMemory).where(ProceduralMemory.user_id == user_id)
            )
            stats["procedural"] = r.rowcount
            r = await session.execute(
                delete(MemoryConsolidationLog).where(
                    MemoryConsolidationLog.user_id == user_id
                )
            )
            stats["consolidation_logs"] = r.rowcount
            await session.commit()
        return stats
    
    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def close(self):
        """关闭数据库连接"""
        await self.engine.dispose()


# ============================================================
# 全局单例
# ============================================================

_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """
    获取全局记忆存储实例
    
    Returns:
        MemoryStore 实例
    """
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store


async def init_memory_store(database_url: Optional[str] = None) -> MemoryStore:
    """
    初始化全局记忆存储（在 FastAPI lifespan 中调用）
    
    Args:
        database_url: 数据库连接字符串
        
    Returns:
        MemoryStore 实例
    """
    global _memory_store
    _memory_store = MemoryStore(database_url=database_url)
    await _memory_store.init_db()
    return _memory_store


async def shutdown_memory_store():
    """关闭全局记忆存储（在 FastAPI lifespan 中调用）"""
    global _memory_store
    if _memory_store:
        await _memory_store.close()
        _memory_store = None