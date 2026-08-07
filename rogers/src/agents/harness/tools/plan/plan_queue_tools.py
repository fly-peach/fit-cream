"""
计划设计待办队列工具

配合 skills/plan-creation/SKILL.md 的队列流程：
    intake 分析 -> present_plan_queue_tool 渲染大纲+逐日待办
    -> 逐日循环：update_plan_queue_item_tool(in_progress)
       -> get_exercises_tool 检索候选
       -> present_day_design_tool 展示当日方案 -> 用户确认
       -> update_plan_queue_item_tool(completed, queue全量)
    -> 全部完成 -> present_plan_tool + create_plan_tool(传入 days) 落库

三个工具均为纯展示/推进节点：不落库、不中断、无副作用，
仅作为 ReAct 步骤流中的标记节点。前端按工具名特判渲染对应卡片，
读取工具入参（而非返回值）。

队列状态不进 agent state_schema：由消息历史中的工具调用承载，
PlanQueueMiddleware 每轮 before_model 从历史重建快照注入给模型。
"""

from typing import List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# ===== 数据模型（前端 types/chat.ts 的等价 Pydantic 镜像）=====


class DayExerciseDesign(BaseModel):
    """单日设计中的一个动作"""

    exercise_id: Optional[str] = Field(
        default=None, description="动作库动作ID（命中库时用）；与 custom_name 二选一"
    )
    custom_name: Optional[str] = Field(
        default=None, max_length=200, description="自定义动作名（库无匹配或用户指定时用）"
    )
    exercise_type: str = Field(
        default="strength",
        pattern="^(strength|cardio)$",
        description="动作类型：strength(力量) / cardio(有氧)",
    )
    name: str = Field(description="展示用动作名")
    sets: Optional[int] = Field(default=None, ge=1, le=20, description="力量动作组数")
    reps: Optional[int] = Field(default=None, ge=1, le=100, description="力量动作次数")
    weight_kg: Optional[float] = Field(default=None, ge=0, description="建议重量(kg)")
    duration_min: Optional[int] = Field(default=None, ge=1, description="有氧时长(分钟)")
    distance_km: Optional[float] = Field(default=None, ge=0, description="有氧距离(km)")
    rest_seconds: Optional[int] = Field(
        default=None, ge=0, description="组间休息(秒)，不填则用训练日默认"
    )
    notes: Optional[str] = Field(
        default=None, max_length=500, description="选它/强度设定的依据或安全提示"
    )


class DayDesign(BaseModel):
    """单日训练方案"""

    day_of_week: int = Field(ge=1, le=7, description="1=周一 ... 7=周日")
    focus: str = Field(description="训练重点，如「胸部 + 三头」")
    day_type: str = Field(
        pattern="^(strength|cardio|mixed|rest)$",
        description="当日类型：strength/cardio/mixed/rest",
    )
    exercises: List[DayExerciseDesign] = Field(
        default_factory=list, description="动作设计列表"
    )
    rationale: Optional[str] = Field(
        default=None, description="当日设计依据（经验层级/安全约束/器械）"
    )


class PlanQueueTodo(BaseModel):
    """队列中的一个待办项（一个训练日）"""

    id: str = Field(description="项ID，如 day-1 / phaseA-day-1")
    title: str = Field(description="展示标题，如「周一 · 胸部 + 三头」")
    description: Optional[str] = Field(default=None, description="副标题，如「力量日 · 复合动作为主」")
    status: str = Field(
        default="pending",
        pattern="^(pending|in_progress|completed|skipped)$",
        description="状态：pending(待设计)/in_progress(进行中)/completed(已完成)/skipped(跳过)",
    )
    day_type: str = Field(
        pattern="^(strength|cardio|mixed|rest)$", description="当日类型"
    )
    day_design: Optional[DayDesign] = Field(
        default=None, description="completed 后填充的当日最终方案"
    )


class PlanQueuePhase(BaseModel):
    """计划阶段（v1 仅单阶段；recomp 多阶段为 v2，QueueSection 天然支持分区）"""

    phase_id: str = Field(description="阶段ID，如 phaseA")
    phase_title: str = Field(description="阶段标题，如「4 周增肌入门」")
    weeks: Optional[int] = Field(default=None, ge=1, le=52, description="阶段周数")
    todos: List[PlanQueueTodo] = Field(default_factory=list, description="该阶段的逐日待办")


class PlanQueue(BaseModel):
    """计划设计待办队列整体"""

    goal: str = Field(description="健身目标 lose_fat/gain_muscle/maintain/improve_health")
    training_type: str = Field(
        description=(
            "主要训练类型：fat_loss(减脂)/muscle_gain(增肌)/"
            "recomp(先减脂再增肌，v1 暂按单阶段)/cardio_only(纯有氧)/maintain(维持)"
        )
    )
    weekly_frequency: int = Field(ge=1, le=7, description="每周训练天数")
    difficulty: str = Field(
        default="beginner",
        pattern="^(beginner|intermediate|advanced)$",
        description="难度层级",
    )
    phases: List[PlanQueuePhase] = Field(
        default_factory=list, description="阶段列表（v1 通常一个）"
    )


class PresentPlanQueueInput(BaseModel):
    """present_plan_queue_tool 入参（与 PlanQueue 字段同构，phases 可选以匹配函数签名）"""

    goal: str = Field(description="健身目标 lose_fat/gain_muscle/maintain/improve_health")
    training_type: str = Field(
        description=(
            "主要训练类型：fat_loss(减脂)/muscle_gain(增肌)/"
            "recomp(先减脂再增肌，v1 暂按单阶段)/cardio_only(纯有氧)/maintain(维持)"
        )
    )
    weekly_frequency: int = Field(ge=1, le=7, description="每周训练天数")
    difficulty: str = Field(
        default="beginner",
        pattern="^(beginner|intermediate|advanced)$",
        description="难度层级",
    )
    phases: Optional[List[PlanQueuePhase]] = Field(
        default=None, description="阶段列表（v1 通常一个），含逐日 todos"
    )


# ===== 工具 =====


@tool(args_schema=PresentPlanQueueInput)
async def present_plan_queue_tool(
    goal: str,
    training_type: str,
    weekly_frequency: int,
    difficulty: str = "beginner",
    phases: Optional[List[PlanQueuePhase]] = None,
) -> dict:
    """
    向用户展示「计划设计待办队列」：大纲 + 逐日待办清单（纯展示，不落库不中断）。

    使用场景：
    - intake 信息收集完成、分析出训练类型与分化策略后，用本工具渲染整个计划的设计进度面板
    - 调用后前端顶部常驻渲染 Queue 待办面板，引导逐日协同设计

    随后进入逐日循环：对每个 pending 日依次调用
    update_plan_queue_item_tool(status="in_progress") -> get_exercises_tool 检索 ->
    present_day_design_tool 展示方案 -> 用户确认 ->
    update_plan_queue_item_tool(status="completed", queue=全量更新后的队列)。

    Args:
        goal: 健身目标
        training_type: 主要训练类型
        weekly_frequency: 每周训练天数
        difficulty: 难度层级
        phases: 阶段列表（含逐日 todos）

    Returns:
        ``{"ok": True}``
    """
    return {"ok": True}


@tool
async def present_day_design_tool(
    item_id: str,
    day_design: DayDesign,
    rationale: str = "",
) -> dict:
    """
    向用户展示单日训练方案提案（纯展示，不落库不中断），等待用户确认或调整。

    使用场景：
    - 逐日循环中，检索到候选动作、按难度+安全约束设计好组次重量后调用
    - 调用后前端内联渲染当日方案卡（动作表格 + 设计依据 + 确认/调整按钮）

    用户确认后会发结构化消息「[确认当日设计: <item_id>]」回到对话，
    你读取后调用 update_plan_queue_item_tool(status="completed", queue=全量快照)
    标记完成并推进到下一日。

    Args:
        item_id: 对应队列项ID（如 day-1）
        day_design: 当日方案（含动作列表）
        rationale: 设计依据（经验层级/安全约束/器械/为何选这些动作）

    Returns:
        ``{"ok": True}``
    """
    return {"ok": True}


@tool
async def update_plan_queue_item_tool(
    item_id: str,
    status: str,
    queue: PlanQueue,
) -> dict:
    """
    更新计划设计队列中某一项的状态（pending->in_progress->completed/skipped）。

    使用场景：
    - 开始设计某日：status="in_progress"（前端该行变 active）
    - 用户确认当日方案后：status="completed"，并把该日的 day_design 填入对应 todo
    - 用户跳过某日：status="skipped"

    重要：入参 queue 必须传**更新后的完整队列快照**（包含所有 phase 所有 todo 的最新
    状态与 day_design）。前端据此重渲染整张待办面板（不依赖增量合并）。
    QueueMiddleware 也会从历史中读取本调用的 queue 入参重建快照注入给后续对话。

    Args:
        item_id: 被更新的队列项ID
        status: 新状态 pending/in_progress/completed/skipped
        queue: 更新后的完整队列快照

    Returns:
        ``{"ok": True}``
    """
    return {"ok": True}
