"""
SQLAlchemy ORM Models 包

导出所有 model 类，确保 Alembic 自动检测和 Base.metadata.create_all 能发现全部表。
新增 model 时需在此处添加 import 和 __all__ 条目。
"""
from app.models.achievement import Achievement
from app.models.checkin import Checkin, CheckinExercise
from app.models.conversation import Conversation
from app.models.exercise import Exercise
from app.models.plan import Plan, PlanDay, PlanDayExercise
from app.models.user import User

__all__ = [
    "User",
    "Plan",
    "PlanDay",
    "PlanDayExercise",
    "Checkin",
    "CheckinExercise",
    "Exercise",
    "Conversation",
    "Achievement",
]