"""
管理端 Schemas

定义管理员后台的用户管理、统计看板、知识库统计列表所需的请求/响应模型。
输出模型使用 from_attributes 从 ORM 实例转换。
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminUserListItem(BaseModel):
    """用户列表项（含运营汇总字段）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: Optional[str] = None
    name: Optional[str] = None
    gender: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    is_verified: bool = False
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    created_at: datetime
    plan_count: int = 0
    checkin_count: int = 0
    total_tokens: int = 0
    tokens_7d: int = 0


class AdminUserHealthMetric(BaseModel):
    """用户详情中的最新健康指标摘要"""

    measure_date: Optional[date] = None
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    bmi: Optional[float] = None


class AdminUserSettings(BaseModel):
    """用户详情中的设置摘要"""

    goal: Optional[str] = None
    weekly_training_goal: Optional[int] = None
    calorie_goal: Optional[int] = None
    target_weight_kg: Optional[float] = None


class AdminUserDetail(AdminUserListItem):
    """用户详情（列表项 + 扩展汇总）"""

    diet_plan_count: int = 0
    settings: Optional[AdminUserSettings] = None
    latest_health_metric: Optional[AdminUserHealthMetric] = None


class AdminUserUpdate(BaseModel):
    """管理端用户变更（禁用/启用、角色切换）"""

    is_active: Optional[bool] = None
    role: Optional[str] = Field(default=None, pattern="^(user|admin)$")


class AdminResetPasswordOut(BaseModel):
    """管理端重置密码返回（临时密码明文仅返回一次）"""

    new_password: str


class AdminCheckinOut(BaseModel):
    """管理端近期打卡摘要"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    date: date
    duration_min: Optional[int] = None
    actual_intensity: Optional[str] = None
    calories_burned: Optional[int] = None
    mood: Optional[int] = None
    note: Optional[str] = None
    created_at: datetime


class AdminKbListItem(BaseModel):
    """知识库管理列表项（含统计列）"""

    id: UUID
    name: str
    slug: str
    description: str = ""
    owner_name: Optional[str] = None
    document_count: int = 0
    chunk_count: int = 0
    pending_document_count: int = 0
    created_at: datetime
    updated_at: datetime


class AdminUsersStats(BaseModel):
    total: int = 0
    new_7d: int = 0
    active_7d: int = 0


class AdminTrainingStats(BaseModel):
    total_checkins: int = 0
    checkins_30d: int = 0
    total_plans: int = 0
    active_plans: int = 0


class AdminKbStats(BaseModel):
    total_kbs: int = 0
    total_documents: int = 0
    pending_documents: int = 0
    total_chunks: int = 0


class AdminConversationStats(BaseModel):
    total_threads: int = 0
    total_messages: int = 0
    threads_7d: int = 0


class AdminTokenStats(BaseModel):
    total_tokens: int = 0
    tokens_7d: int = 0


class AdminOverviewStats(BaseModel):
    """总览 KPI（四维度）"""

    users: AdminUsersStats = Field(default_factory=AdminUsersStats)
    training: AdminTrainingStats = Field(default_factory=AdminTrainingStats)
    kb: AdminKbStats = Field(default_factory=AdminKbStats)
    conversation: AdminConversationStats = Field(default_factory=AdminConversationStats)
    tokens: AdminTokenStats = Field(default_factory=AdminTokenStats)


class AdminTrends(BaseModel):
    """近 N 天每日趋势"""

    days: list[str] = Field(default_factory=list)
    registrations: list[int] = Field(default_factory=list)
    checkins: list[int] = Field(default_factory=list)
    conversations: list[int] = Field(default_factory=list)
    active_users: list[int] = Field(default_factory=list)
    tokens: list[int] = Field(default_factory=list)
