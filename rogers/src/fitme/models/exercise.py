"""
动作库模型

存储健身动作的基础数据（名称、肌群、器械、难度、描述），
供训练计划编排和 Agent 动作推荐查询使用。
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from pgvector.sqlalchemy import Vector

from app.config import settings
from app.database import Base


# dataset body_part -> 我们稳定的 7 值 muscle_group（粗分类，零改动 agent/plan 消费方）
MUSCLE_GROUP_COARSENING = {
    "chest": "chest",
    "back": "back",
    "shoulders": "shoulders",
    "neck": "shoulders",
    "upper arms": "arms",
    "lower arms": "arms",
    "upper legs": "legs",
    "lower legs": "legs",
    "waist": "core",
    "cardio": "full_body",
}

# dataset 28 种 equipment -> 8 种稳定值（与 agent 工具描述一致）
# map 只列非 other 映射；未命中的 key（medicine ball/stability ball/roller/tire/ergometer 等）默认 other
EQUIPMENT_COARSENING = {
    "body weight": "bodyweight",
    "barbell": "barbell",
    "ez barbell": "barbell",
    "olympic barbell": "barbell",
    "trap bar": "barbell",
    "dumbbell": "dumbbell",
    "cable": "cable",
    "rope": "cable",
    "leverage machine": "machine",
    "sled machine": "machine",
    "smith machine": "machine",
    "assisted": "machine",
    "kettlebell": "kettlebell",
    "band": "band",
    "resistance band": "band",
}


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    name_en: Mapped[Optional[str]] = mapped_column(String(200))
    muscle_group: Mapped[Optional[str]] = mapped_column(
        String(50), index=True
    )
    muscle_subgroup: Mapped[Optional[str]] = mapped_column(String(50))
    category: Mapped[Optional[str]] = mapped_column(
        String(50), index=True
    )
    is_compound: Mapped[bool] = mapped_column(Boolean, default=False)
    equipment: Mapped[Optional[str]] = mapped_column(
        String(100), index=True
    )
    difficulty: Mapped[Optional[str]] = mapped_column(
        String(20), index=True
    )
    calories_per_min: Mapped[Optional[float]] = mapped_column(Numeric(6, 1))
    description: Mapped[Optional[str]] = mapped_column(Text)
    instructions: Mapped[Optional[str]] = mapped_column(Text)
    tips: Mapped[Optional[str]] = mapped_column(Text)

    # ---- 以下为导入 exercises-dataset 新增列（均 nullable，由 init_db 自动 ALTER）----
    body_part: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    body_part_zh: Mapped[Optional[str]] = mapped_column(String(50))
    target: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    target_zh: Mapped[Optional[str]] = mapped_column(String(50))
    secondary_muscles: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    secondary_muscles_zh: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    instruction_steps: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    instruction_steps_en: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    instructions_en: Mapped[Optional[str]] = mapped_column(Text)
    equipment_zh: Mapped[Optional[str]] = mapped_column(String(100))
    muscle_subgroup_zh: Mapped[Optional[str]] = mapped_column(String(50))
    media_id: Mapped[Optional[str]] = mapped_column(String(100))
    image: Mapped[Optional[str]] = mapped_column(String(255))
    gif_url: Mapped[Optional[str]] = mapped_column(String(255))
    attribution: Mapped[Optional[str]] = mapped_column(String(255))

    # ---- 语义向量列（text-embedding-v3，供 Agent 语义检索动作）----
    # 向量文本由 ExerciseService.build_embedding_text 生成（名称中英 + 肌群 + 器械 + 描述），
    # 存量数据由 scripts/backfill_exercise_embeddings.py 回填；新列由 init_db 自动 ALTER。
    # deferred=True：默认 SELECT 不加载本列。pgvector 扩展缺失时列不会被创建，
    # 常规查询因不引用本列而不受影响；语义检索探测到列缺失则整体关闭（不做降级）。
    embedding = mapped_column(Vector(settings.EMBEDDING_DIMENSION), nullable=True, deferred=True)

    @hybrid_property
    def description_en(self) -> Optional[str]:
        steps = self.instruction_steps_en
        return steps[0] if steps else None


class UserExerciseFavorite(Base):
    __tablename__ = "user_exercise_favorites"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "exercise_id", name="uq_user_exercise_fav"),)