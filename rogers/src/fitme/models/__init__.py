"""
SQLAlchemy ORM Models 包

导出所有 model 类，确保 Alembic 自动检测和 Base.metadata.create_all 能发现全部表。
新增 model 时需在此处添加 import 和 __all__ 条目。
"""
from src.fitme.models.achievement import Achievement
from src.fitme.models.checkin import Checkin, CheckinExercise
from src.fitme.models.conversation import Conversation
from src.fitme.models.diet_plan import DietPlan, DietPlanDay, DietPlanMeal
from src.fitme.models.exercise import Exercise
from src.fitme.models.plan import Plan, PlanDay, PlanDayExercise
from src.fitme.models.user import User
from src.fitme.models.thread_usage import ThreadUsage
from src.fitme.models.thread_meta import ThreadMeta

# 知识库模型
from src.knowledge_base.models import (
    KBApiToken,
    KBChunk,
    KBDocument,
    KBReference,
    KBSubscription,
    KnowledgeBase,
)

__all__ = [
    "User",
    "Plan",
    "PlanDay",
    "PlanDayExercise",
    "DietPlan",
    "DietPlanDay",
    "DietPlanMeal",
    "Checkin",
    "CheckinExercise",
    "Exercise",
    "Conversation",
    "Achievement",
    "ThreadUsage",
    "ThreadMeta",
    # 知识库
    "KnowledgeBase",
    "KBDocument",
    "KBChunk",
    "KBReference",
    "KBSubscription",
    "KBApiToken",
]
