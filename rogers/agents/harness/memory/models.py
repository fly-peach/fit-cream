"""
记忆系统数据库模型

定义三层长期记忆的 SQLAlchemy 模型：
- EpisodicMemory: 情景记忆（事件、对话片段）
- SemanticMemory: 语义记忆（事实、偏好、规则）
- ProceduralMemory: 程序性记忆（工作流、技能）

使用 pgvector 扩展存储向量，支持语义检索。

用法：
    from agents.harness.memory.models import EpisodicMemory, SemanticMemory, ProceduralMemory
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    Float,
    Index,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # 如果 pgvector 未安装，使用 JSON 作为 fallback
    Vector = None

from agents.harness.memory.embeddings import get_embedding_dimension


class MemoryBase(DeclarativeBase):
    """记忆模型基类"""
    pass


class EpisodicMemory(MemoryBase):
    """
    情景记忆 (Episodic Memory)
    
    记录具体发生的事件和交互，类似"个人日记"。
    存储对话片段、关键事件、观察等。
    
    Attributes:
        content: 原始内容
        summary: AI 生成的摘要
        embedding: 内容向量（用于语义检索）
        memory_type: 记忆类型 (conversation/event/observation)
        importance_score: 重要性评分 (0-1)
        emotional_valence: 情感倾向 (positive/negative/neutral)
        access_count: 访问次数（用于遗忘曲线）
        decay_factor: 衰减因子（用于遗忘曲线）
    """
    __tablename__ = "episodic_memories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=False, index=True)
    
    # 内容
    content = Column(Text, nullable=False)
    summary = Column(Text)
    embedding = Column(Vector(get_embedding_dimension())) if Vector else Column(JSONB)
    
    # 元数据
    memory_type = Column(String(50), default="conversation")  # conversation/event/observation
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    location = Column(String(200))  # 可选：地点
    participants = Column(ARRAY(String))  # 可选：参与者
    
    # 情感与重要性
    emotional_valence = Column(String(20), default="neutral")  # positive/negative/neutral
    importance_score = Column(Float, default=0.5)  # 0-1
    
    # 遗忘曲线参数
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime)
    decay_factor = Column(Float, default=1.0)
    
    # 来源
    source_thread_id = Column(String(100))  # 来源对话线程
    source_message_ids = Column(ARRAY(String))  # 来源消息 ID
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_episodic_user_time", "user_id", "timestamp"),
        Index("idx_episodic_user_type", "user_id", "memory_type"),
        Index("idx_episodic_importance", "importance_score"),
    )
    
    def __repr__(self):
        return f"<EpisodicMemory(id={self.id}, user={self.user_id}, type={self.memory_type})>"


class SemanticMemory(MemoryBase):
    """
    语义记忆 (Semantic Memory)
    
    存储从经历中提炼出的事实、偏好和规则。
    使用三元组结构 (subject, predicate, object) 表示知识。
    
    支持版本管理：当信息更新时，旧版本标记为 superseded。
    
    Attributes:
        subject: 主体（如 "用户"）
        predicate: 关系（如 "偏好"）
        object: 对象（如 "Python"）
        category: 分类 (preference/fact/rule/status)
        confidence: 置信度 (0-1)
        version: 版本号
        status: 状态 (active/superseded)
    """
    __tablename__ = "semantic_memories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=False, index=True)
    
    # 三元组结构
    subject = Column(String(200), nullable=False)
    predicate = Column(String(200), nullable=False)
    object = Column(Text, nullable=False)
    
    # 元数据
    category = Column(String(50), default="fact")  # preference/fact/rule/status
    confidence = Column(Float, default=1.0)
    
    # 来源
    source_episodic_id = Column(UUID(as_uuid=True), ForeignKey("episodic_memories.id"))
    source_episodic = relationship("EpisodicMemory", backref="derived_semantics")
    
    # 版本管理
    version = Column(Integer, default=1)
    status = Column(String(20), default="active")  # active/superseded
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("semantic_memories.id"))
    superseded_by_memory = relationship("SemanticMemory", remote_side=[id])
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_semantic_user_category", "user_id", "category"),
        Index("idx_semantic_user_status", "user_id", "status"),
        Index("idx_semantic_triple", "user_id", "subject", "predicate"),
    )
    
    def __repr__(self):
        return f"<SemanticMemory({self.subject} {self.predicate} {self.object})>"
    
    def to_triple_string(self) -> str:
        """转换为三元组字符串表示"""
        return f"{self.subject} {self.predicate} {self.object}"


class ProceduralMemory(MemoryBase):
    """
    程序性记忆 (Procedural Memory)
    
    存储如何完成特定任务的流程和技能，类似"肌肉记忆"。
    将成功的工作流保存为可复用的"技能"。
    
    Attributes:
        name: 技能名称（如 "撰写周报"）
        description: 技能描述
        steps: 步骤列表（JSON）
        trigger_conditions: 触发条件（JSON）
        success_count: 成功执行次数
        failure_count: 失败执行次数
    """
    __tablename__ = "procedural_memories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=False, index=True)
    
    # 技能内容
    name = Column(String(200), nullable=False)
    description = Column(Text)
    steps = Column(JSONB, nullable=False)  # [{"step": 1, "action": "...", "params": {...}}]
    embedding = Column(Vector(get_embedding_dimension())) if Vector else Column(JSONB)
    
    # 使用统计
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_used = Column(DateTime)
    
    # 适用条件
    trigger_conditions = Column(JSONB)  # {"keywords": [...], "context": "..."}
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_procedural_user_name", "user_id", "name"),
    )
    
    def __repr__(self):
        return f"<ProceduralMemory(name={self.name}, user={self.user_id})>"
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


class MemoryConsolidationLog(MemoryBase):
    """
    记忆整合日志
    
    记录记忆整合（consolidation）过程的日志，用于追踪记忆演化。
    """
    __tablename__ = "memory_consolidation_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=False, index=True)
    
    # 整合信息
    consolidation_type = Column(String(50))  # merge/update/forget/reflect
    source_memory_ids = Column(ARRAY(UUID(as_uuid=True)))
    result_memory_id = Column(UUID(as_uuid=True))
    
    # 详情
    details = Column(JSONB)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_consolidation_user_time", "user_id", "created_at"),
    )