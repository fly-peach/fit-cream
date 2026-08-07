"""
计划设计待办队列工具

配合 skills/plan-creation/SKILL.md 的闭环待办流程：
    收到设计意图 -> present_plan_queue_tool 创建「从信息收集到落库」的完整待办清单
    -> 逐项执行：update_plan_queue_item_tool(in_progress) -> 做该步 -> update(completed) 打勾
    -> 信息收集项用 present_form_tool 在对话内弹表单
    -> 大纲确认后用 present_plan_queue_tool 重组清单（插入逐日设计 todo）
    -> 逐日设计用 get_exercises_tool + present_day_design_tool 在对话内展示当日方案
    -> 装配 present_plan_tool -> create_plan_tool(传 days) 落库审批

待办面板只渲染 todo（标题 + 状态），不含表单/方案等内容；所有表单与当日方案
都在对话消息流内渲染（FormCard / DayDesignCard）。

三个工具均为纯展示/推进节点：不落库、不中断、无副作用。队列状态不进
agent state_schema，由消息历史中的工具调用承载，PlanQueueMiddleware 每轮
before_model 从历史重建快照注入给模型。
"""

from typing import List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# ===== 单日方案（present_day_design_tool 用，内联渲染，不进待办面板）=====


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
    """单日训练方案（内联展示，不进待办面板）"""

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


# ===== 待办队列（待办面板只渲染这些，不含别的内容）=====


class PlanQueueTodo(BaseModel):
    """待办清单中的一项（面板只显示标题 + 状态）"""

    id: str = Field(description="项ID，如 intake-body / design-day-1 / approve")
    title: str = Field(description="待办标题，如「收集基础身体数据」「设计周一 · 胸部+三头」")
    description: Optional[str] = Field(
        default=None, max_length=200, description="待办短说明（可选），如「设计周一训练日的动作与组次」"
    )
    status: str = Field(
        default="pending",
        pattern="^(pending|in_progress|completed|skipped)$",
        description="状态：pending(待办)/in_progress(进行中)/completed(完成)/skipped(跳过)",
    )


class PlanQueue(BaseModel):
    """计划设计待办队列整体（面板只渲染 title + todos）"""

    title: str = Field(description="队列标题，如「4周增肌计划设计」")
    todos: List[PlanQueueTodo] = Field(
        default_factory=list, description="从信息收集到落库的完整待办清单"
    )


# ===== 工具 =====


@tool
async def present_plan_queue_tool(
    title: str,
    todos: List[PlanQueueTodo],
) -> dict:
    """
    创建或更新「计划设计待办队列」：从信息收集到计划落库的完整闭环清单（纯展示，不落库不中断）。

    使用场景：
    - 收到计划设计意图后**第一步**就调用，建立覆盖全流程的待办清单（信息收集各项 +
      分析+大纲+逐日设计+装配+审批落库）
    - 大纲确认后再次调用以**重组清单**：把逐日设计 todo 插入大纲与装配之间

    待办面板只渲染标题与各 todo 的标题+状态，不含表单/方案内容；所有表单与当日方案
    都在对话消息流内渲染（present_form_tool / present_day_design_tool）。

    Args:
        title: 队列标题
        todos: 完整待办清单（每次传入当前最新全量，前端据此整体重渲染）

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
    更新待办队列中某一项的状态（pending->in_progress->completed/skipped），「做了就打勾」。

    使用场景：
    - 开始某步：status="in_progress"（面板该行变进行中）
    - 完成某步：status="completed"（面板该行打勾）-> 进入下一项

    重要：入参 queue 必须传**更新后的完整队列快照**（含全部 todo 的最新状态）。
    前端与 QueueMiddleware 都据此重建状态。建议从 QueueMiddleware 注入的当前快照
    复制后翻转对应 item 的 status。

    Args:
        item_id: 被更新的待办项ID
        status: 新状态 pending/in_progress/completed/skipped
        queue: 更新后的完整队列快照

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
    向用户展示单日训练方案提案（纯展示，不落库不中断），在对话内渲染当日方案卡。

    使用场景：
    - 逐日设计循环中，检索到候选动作、按难度+安全约束设计好组次重量后调用
    - 调用后前端在对话原位渲染当日方案卡（动作表格 + 设计依据 + 确认按钮）

    用户确认后会发结构化消息「[确认当日设计: <item_id>]」回到对话，
    你读取后调用 update_plan_queue_item_tool(item_id, status="completed", queue=全量快照)
    打勾该日 todo 并推进到下一日。

    Args:
        item_id: 对应待办项ID（如 design-day-1）
        day_design: 当日方案（含动作列表）
        rationale: 设计依据（经验层级/安全约束/器械/为何选这些动作）

    Returns:
        ``{"ok": True}``
    """
    return {"ok": True}
