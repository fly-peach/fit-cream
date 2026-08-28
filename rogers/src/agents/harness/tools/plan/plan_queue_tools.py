"""
计划设计待办队列工具

配合 skills/plan-creation/SKILL.md 的闭环待办流程：
    收到设计意图 -> present_plan_queue_tool 创建「从信息收集到落库」的完整待办清单
    -> 逐项执行：update_plan_queue_item_tool(in_progress) -> 做该步 -> update(completed) 打勾
    -> 信息收集项用 present_form_tool 在对话内弹表单
    -> 大纲阶段用 present_outline_tool 展示训练大纲（chip + 弹窗，不占正文）
    -> 大纲确认后用 present_plan_queue_tool 重组清单（插入逐日设计 todo）
    -> 逐日设计用 get_exercises_tool + present_day_design_tool 在对话内展示当日方案
    -> 装配 present_plan_tool -> create_plan_tool(传 days) 落库审批

待办面板只渲染 todo（标题 + 状态），不含表单/方案等内容；所有表单与当日方案
都在对话消息流内渲染（FormCard / DayDesignCard）。

本模块工具均为纯展示/推进节点：不落库、不中断、无副作用。队列状态不进
agent state_schema，由消息历史中的工具调用承载，PlanQueueMiddleware 每轮
wrap_model_call 从历史重建快照临时注入给模型（F1：不落 checkpoint）。

present_outline_tool 入参（分化策略 + 每日 focus/day_type）体量小且全程
（逐日设计需对照大纲）有用，故不纳入 ContextMessageGateMiddleware 的
QUEUE_TOOLS 裁剪范围，完整保留在模型视图中。
"""

from typing import List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# 携带完整队列快照入参的工具名（前端待办面板 / PlanQueueMiddleware / 模型视图
# 裁剪 ContextMessageGateMiddleware 共同依赖的锚点，定义在此作为契约来源）
QUEUE_TOOLS = ("present_plan_queue_tool", "update_plan_queue_item_tool")


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


# ===== 训练大纲（present_outline_tool 用，chip + 弹窗渲染，不占正文）=====


class OutlineDay(BaseModel):
    """大纲中的一个训练日（只有分化安排，不含具体动作）"""

    day_of_week: int = Field(ge=1, le=7, description="1=周一 ... 7=周日")
    focus: str = Field(description="训练重点，如「胸部 + 三头」；休息日写「休息」")
    day_type: str = Field(
        pattern="^(strength|cardio|mixed|rest)$",
        description="当日类型：strength/cardio/mixed/rest",
    )
    note: Optional[str] = Field(
        default=None,
        max_length=200,
        description="当日备注（可选），如强度安排/恢复说明",
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

    调用纪律：
    - **每次设计会话只调用一次**（初始建清单）。展示后立即用
      update_plan_queue_item_tool 推进，不得反复重 present 同一清单。
    - 仅在大纲确认后**重组清单**（插入逐日设计 todo）时才可再次调用。
    - 调用后本轮即止步等待用户/推进动作，不要在同一轮继续重复调用本工具。

    Args:
        title: 队列标题
        todos: 完整待办清单（每次传入当前最新全量，前端据此整体重渲染）

    Returns:
        ``{"ok": True, "next": ...}``
    """
    return {
        "ok": True,
        "next": (
            "队列已展示。立即调用 update_plan_queue_item_tool 将第一项标记为 "
            "in_progress 并执行该步（如发起信息收集表单）。本次设计会话禁止再次调用 "
            "本工具（大纲确认后重组清单除外）。"
        ),
    }


@tool
async def present_outline_tool(
    title: str,
    strategy: str,
    days: List[OutlineDay],
) -> dict:
    """
    向用户展示训练大纲提案（纯展示，不落库不中断）：分化策略 + 每日 focus + day_type。

    前端渲染为对话内一个「查看训练大纲」链接（chip），点击弹窗展示完整大纲，
    **不占用回复正文**；回复正文只需一两句话概括分化思路并引导用户点开确认。

    使用场景：
    - plan-creation 流程大纲项：按分层规则确定分化后调用，代替在正文里输出大纲表格
    - 用户确认后发结构化消息「[确认大纲]」回到对话，你读取后打勾 outline 项并重组待办清单

    注意：大纲不含具体动作/组次；具体动作在逐日设计（present_day_design_tool）中展开。

    Args:
        title: 大纲标题，如「4周增肌计划 · 训练大纲」
        strategy: 分化策略与设计依据（经验层级/频率/安全约束的简述）
        days: 每日安排（星期/focus/day_type/备注），休息日也要列出（day_type=rest）

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
        ``{"ok": True, "next": ...}``（打勾后引导推进下一项；全部完成则引导装配/审批）
    """
    remaining = [t for t in queue.todos if t.status in ("pending", "in_progress")]
    if status == "completed" and not remaining:
        return {
            "ok": True,
            "next": (
                "全部待办已完成。立即进入装配：调用 present_plan_tool 展示完整计划提案"
                "与变更清单，随后调用 create_plan_tool(传 days) 触发审批落库。"
            ),
        }
    if not remaining:
        return {
            "ok": True,
            "next": (
                "队列已全部完成。立即调用 present_plan_tool + create_plan_tool(传 days)"
                "装配提案并触发审批落库，不得开放式收尾。"
            ),
        }
    return {
        "ok": True,
        "next": (
            f"已更新「{item_id}」为 {status}。立即推进下一项：调用 "
            "update_plan_queue_item_tool 将下一个 pending 项标记为 in_progress "
            "并执行该步（信息收集项用 present_form_tool 弹表单、分析项定类型、"
            "大纲项用 present_outline_tool、逐日项用 get_exercises_tool + "
            "present_day_design_tool）。"
        ),
    }


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
