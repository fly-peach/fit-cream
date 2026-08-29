"""
目标闯关系统 Schemas

定义路线图/关卡/基线测试的请求与输出模型：
- MetricCriterion: 单一指标条件（{metric, op, value, unit}）
- StageDesign: 关卡设计（present_roadmap_tool / create_roadmap_tool 入参）
- GoalRoadmapCreate: 创建路线图（含关卡列表）
- GoalRoadmapOut / GoalMilestoneOut: 输出
- PerformanceTestCreate / Out: 力量基线/复测记录
"""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# 统一指标词表（全系统共用：原型用 ratio，关卡出口用绝对值）
METRIC_KEYS = (
    "body_fat_pct",
    "bench_ratio",
    "squat_ratio",
    "deadlift_ratio",
    "ohp_ratio",
    "waist_cm",
    "pull_ups",
    "bench_kg",
    "squat_kg",
    "deadlift_kg",
    "ohp_kg",
    "bodyweight_kg",
)

# 力量类指标（关卡跨关须单调不减）
STRENGTH_METRICS = ("bench_kg", "squat_kg", "deadlift_kg", "ohp_kg", "pull_ups")
# 反向类指标（须单调不增）
DESCENDING_METRICS = ("body_fat_pct", "waist_cm")


class MetricCriterion(BaseModel):
    """单一指标条件"""

    metric: str = Field(description="指标 key（统一词表内）")
    op: str = Field(pattern="^(>=|<=)$", description="比较操作符：>= / <=")
    value: float = Field(description="目标值")
    unit: Optional[str] = Field(default=None, description="单位，如 kg / % / cm / 次数")


class StageDesign(BaseModel):
    """关卡设计（present_roadmap_tool 展示与 create_roadmap_tool 落库共用）"""

    stage_index: int = Field(ge=1, description="关卡序号，从 1 连续递增")
    title: str = Field(min_length=1, max_length=200, description="关卡标题")
    description: Optional[str] = Field(default=None, description="关卡说明")
    exit_criteria: List[MetricCriterion] = Field(
        min_length=1, max_length=5, description="出口条件 1-5 条"
    )
    expected_weeks: int = Field(ge=2, le=16, description="预期周数 2-16")
    training_focus: Optional[str] = Field(
        default=None, max_length=200, description="训练重点（analyze 步约束当前关计划基调）"
    )


class GoalRoadmapCreate(BaseModel):
    """创建路线图入参（create_roadmap_tool）"""

    archetype_key: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    target_metrics: List[MetricCriterion] = Field(
        default_factory=list, description="最终目标（末关近似）"
    )
    horizon_months: Optional[int] = Field(default=None, ge=1, le=24)
    stages: List[StageDesign] = Field(
        min_length=2, max_length=8, description="关卡 2-8 个"
    )


class GoalMilestoneOut(BaseModel):
    """关卡输出"""

    id: UUID
    stage_index: int
    title: str
    description: Optional[str] = None
    exit_criteria: List[dict] = Field(default_factory=list)
    expected_weeks: Optional[int] = None
    training_focus: Optional[str] = None
    status: str
    achieved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class GoalRoadmapOut(BaseModel):
    """路线图输出"""

    id: UUID
    archetype_key: str
    title: str
    description: Optional[str] = None
    target_metrics: List[dict] = Field(default_factory=list)
    horizon_months: Optional[int] = None
    status: str
    milestones: List[GoalMilestoneOut] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class PerformanceTestCreate(BaseModel):
    """力量基线/复测记录入参"""

    lift: str = Field(pattern="^(bench|squat|deadlift|ohp|pull_up)$")
    value: float = Field(ge=0, description="kg（pull_up 为次数）")
    test_type: str = Field(default="1rm", pattern="^(1rm|est)$")
    tested_at: Optional[date] = None
    note: Optional[str] = None


class PerformanceTestOut(BaseModel):
    """力量基线/复测记录输出"""

    id: UUID
    lift: str
    test_type: str
    value: float
    bodyweight_kg: Optional[float] = None
    tested_at: date
    source: str
    note: Optional[str] = None

    model_config = {"from_attributes": True}
