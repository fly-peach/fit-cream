"""
应用层数据模型与服务聚合入口

集中导入 src 内所有 ORM 模型（注册到 app.database.Base.metadata，
供 init_db 的 create_all 建表）与所有 Service 类，
作为应用统一的加载/暴露入口。

src 各子系统只保留核心数据模型、schemas 与 service 定义，
不在 src 内做"导入所有模型/服务"的外层聚合——该职责由本模块承担。
"""
# ---- ORM 模型（注册到 Base.metadata）----
from src.fitme.models.auth_models import (
    LoginAttempt,
    RefreshTokenBlacklist,
    UserApiKey,
    UserAuditLog,
    VerificationCode,
)
from src.fitme.models.checkin import Checkin, CheckinExercise
from src.fitme.models.diet_meal import CustomFoodItem, DailyDietSummary, DietMeal
from src.fitme.models.diet_plan import DietPlan, DietPlanDay, DietPlanMeal
from src.fitme.models.exercise import Exercise, UserExerciseFavorite
from src.fitme.models.health_metric import HealthMetric
from src.fitme.models.plan import Plan, PlanDay, PlanDayExercise
from src.agents.models.thread_meta import ThreadMeta
from src.agents.models.thread_usage import ThreadUsage
from src.fitme.models.user import User
from src.fitme.models.user_goals import UserGoals
from src.fitme.models.user_settings import UserSettings

from src.agents.models.conversation import Conversation

from src.knowledge_base.models.chunk import KBChunk
from src.knowledge_base.models.document import KBDocument
from src.knowledge_base.models.knowledge_base import KnowledgeBase
from src.knowledge_base.models.reference import KBReference
from src.knowledge_base.models.subscription import KBSubscription

# ---- Agent 记忆模型（独立 MemoryBase，不进 app Base.metadata；建表走 MemoryStore.init_db）----
from src.agents.models.memory import (
    EpisodicMemory,
    MemoryConsolidationLog,
    ProceduralMemory,
    SemanticMemory,
)

# ---- Service 层 ----
from src.agents.harness.runtime.conversation_service import ConversationService
from src.auth.api_key_service import UserApiKeyService
from src.auth.auth_service import AuthService
from src.fitme.services.checkin_service import CheckinService
from src.fitme.services.diet_meal_service import CustomFoodItemService, DietMealService
from src.fitme.services.diet_plan_service import DietPlanService
from src.fitme.services.exercise_service import ExerciseService
from src.fitme.services.plan_service import PlanService
from src.fitme.services.sms_service import SmsService
from src.fitme.services.stats_service import StatsService
from src.fitme.services.user_service import UserService
from src.knowledge_base.services.document_service import KBDocumentService
from src.knowledge_base.services.graph_service import KBGraphService
from src.knowledge_base.services.knowledge_base_service import KnowledgeBaseService
from src.knowledge_base.services.search_service import KBSearchService

__all__ = [
    # 业务模型
    "User",
    "UserGoals",
    "UserSettings",
    "HealthMetric",
    "Plan",
    "PlanDay",
    "PlanDayExercise",
    "DietPlan",
    "DietPlanDay",
    "DietPlanMeal",
    "DietMeal",
    "DailyDietSummary",
    "CustomFoodItem",
    "Checkin",
    "CheckinExercise",
    "Exercise",
    "UserExerciseFavorite",
    "ThreadUsage",
    "ThreadMeta",
    # Agent 模型
    "Conversation",
    # 认证模型
    "RefreshTokenBlacklist",
    "LoginAttempt",
    "UserApiKey",
    "UserAuditLog",
    "VerificationCode",
    # 知识库模型
    "KnowledgeBase",
    "KBDocument",
    "KBChunk",
    "KBReference",
    "KBSubscription",
    # Agent 记忆模型（独立 MemoryBase）
    "EpisodicMemory",
    "SemanticMemory",
    "ProceduralMemory",
    "MemoryConsolidationLog",
    # 服务
    "UserApiKeyService",
    "AuthService",
    "UserService",
    "PlanService",
    "CheckinService",
    "ExerciseService",
    "StatsService",
    "DietPlanService",
    "DietMealService",
    "CustomFoodItemService",
    "SmsService",
    "KnowledgeBaseService",
    "KBDocumentService",
    "KBSearchService",
    "KBGraphService",
    "ConversationService",
]
