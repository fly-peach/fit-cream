"""
AI 信息校验中间件（对大纲与普通结构化信息的确定性兜底）

背景（生产实测暴露的两个失败模式）：
1. 大纲阶段模型未调用 present_outline_tool，反而把大纲以纯文本表格写进回复正文，
   前端只按「工具是否被调用」渲染 chip+弹窗，管不住正文重复输出。
2. 模型把用户手打的「[确认大纲]」当成合法确认，跳过大纲直接进入逐日设计
   （此前某一轮在复杂度上限被掐断，present_outline_tool 根本没发出）。

本中间件在 plan-design 队列流程（有队列快照）的每个用户轮次 wrap_model_call
临时合并针对性校验提示到 request.system_message（F1：不落 checkpoint），把
「必须走展示工具、禁止正文写结构化内容」从软规则升级为每轮可见的硬约束，
作为确定性兜底：

- 确认类兜底：用户确认大纲/当日设计，但对应展示工具从未被调用 -> 要求先补展示，
  不得直接接受该确认。
- 阶段类兜底：当前处于大纲/逐日设计/装配审批阶段且对应展示工具尚未调用 ->
  强调用展示工具渲染、禁止把表格写成正文。

架构与 PlanQueueMiddleware / RequestGateMiddleware 一致：
- 仅最新消息为 HumanMessage 时注入（跳过 tool 循环，避免重复注入）
- 无实例级可变状态，编译进共享 graph，并发运行互不影响
- F3：队列快照经 plan_queue_middleware.get_queue_snapshot 复用 PlanQueue 的
  单次扫描结果，不重复后向扫描
- 无队列快照（非 plan-design 流程）时零开销直接跳过
"""

import logging
from typing import Optional

from langchain.messages import HumanMessage

from src.agents.harness.runtime.middleware.plan_queue_middleware import (
    get_queue_snapshot,
)
from src.agents.harness.runtime.middleware.robust import msg_tool_calls
from src.agents.harness.runtime.middleware.transient_prompt import (
    TransientPromptMiddleware,
)

logger = logging.getLogger("fitcream.agent")

# 计划设计流程中承担「结构化展示」的展示工具（前端据此渲染专用卡片）
OUTLINE_TOOL = "present_outline_tool"
DAY_DESIGN_TOOL = "present_day_design_tool"
PLAN_PROPOSAL_TOOL = "present_plan_tool"
ROADMAP_TOOL = "present_roadmap_tool"

# 确认消息的识别锚点（与前端 FormCard/DayDesignCard/OutlineCard/RoadmapCard 提交的结构化文本一致）
_OUTLINE_CONFIRM_NEEDLES = ("确认大纲",)
_DAY_CONFIRM_NEEDLES = ("确认当日设计",)
_ROADMAP_CONFIRM_NEEDLES = ("确认路线图",)


def _has_called(messages: list, tool_name: str) -> bool:
    """历史中是否出现过某展示工具的调用。

    经 msg_tool_calls 统一安全提取：非 dict tc / 缺 name 的畸形条目被跳过，
    避免对畸形 tool_calls 下标访问抛异常阻断整条消息。
    """
    for msg in messages:
        for name, _, _ in msg_tool_calls(msg):
            if name == tool_name:
                return True
    return False


def _current_stage_id(queue: dict) -> Optional[str]:
    """取队列中第一个未完成待办的 id（即当前应推进的阶段）。"""
    for t in queue.get("todos") or []:
        if not isinstance(t, dict):
            continue
        if t.get("status") != "completed":
            return t.get("id")
    return None


def _is_outline_confirm(text: str) -> bool:
    return any(n in text for n in _OUTLINE_CONFIRM_NEEDLES)


def _is_day_confirm(text: str) -> bool:
    return any(n in text for n in _DAY_CONFIRM_NEEDLES)


def _is_roadmap_confirm(text: str) -> bool:
    return any(n in text for n in _ROADMAP_CONFIRM_NEEDLES)


def _build_guards(messages: list, queue: dict) -> list[str]:
    """按当前阶段与历史，生成需要注入的校验提示（空列表=不注入）。"""
    guards: list[str] = []

    last = messages[-1] if messages else None
    last_content = ""
    if isinstance(last, HumanMessage):
        last_content = str(last.content or "")

    has_outline = _has_called(messages, OUTLINE_TOOL)
    has_day_design = _has_called(messages, DAY_DESIGN_TOOL)
    has_proposal = _has_called(messages, PLAN_PROPOSAL_TOOL)
    has_roadmap = _has_called(messages, ROADMAP_TOOL)

    # ---- 确认类兜底：用户确认了某项，但对应展示工具从未被调用 ----
    if last_content and _is_outline_confirm(last_content) and not has_outline:
        guards.append(
            "校验：用户确认了「大纲」，但本会话尚未调用 present_outline_tool 展示过大纲。"
            "不得把该确认当作已展示来接受——请立即调用 present_outline_tool(title, strategy, days) "
            "先展示大纲（前端渲染 chip+弹窗），展示后再按确认推进；"
            "若此前确已展示过，请说明并继续，不要重新生成大纲内容。"
        )
    if last_content and _is_day_confirm(last_content) and not has_day_design:
        guards.append(
            "校验：用户确认了「当日设计」，但本会话尚未调用 present_day_design_tool 展示过任何当日方案。"
            "不得跳过展示直接落库或继续——请先用 get_exercises_tool 检索候选，再调用 "
            "present_day_design_tool 展示当日方案供用户确认。"
        )
    if last_content and _is_roadmap_confirm(last_content) and not has_roadmap:
        guards.append(
            "校验：用户确认了「路线图」，但本会话尚未调用 present_roadmap_tool 展示过路线图提案。"
            "不得把该确认当作已展示来接受——请先按 get_goal_knowledge_tool 返回的原型/档位/速率"
            "分解关卡，调用 present_roadmap_tool 展示路线图（前端渲染 RoadmapCard），"
            "展示后再按确认推进；若此前确已展示过，请说明并继续，不要重新生成。"
        )

    # ---- 阶段类兜底：当前阶段的展示工具尚未调用，禁止把结构化内容写成正文 ----
    current_id = _current_stage_id(queue)
    if current_id in ("analyze", "outline") and not has_outline:
        guards.append(
            "校验：当前处于大纲阶段。训练大纲必须通过 present_outline_tool 展示"
            "（title + strategy + days，前端渲染「查看训练大纲」chip+弹窗），"
            "禁止在回复正文里输出大纲表格；调用工具后正文只写一两句分化思路概述并引导点开查看。"
        )
    elif current_id and current_id.startswith("design-day"):
        guards.append(
            "校验：当前处于逐日设计阶段。当日方案必须先用 get_exercises_tool 检索候选，"
            "再调用 present_day_design_tool 展示（前端渲染当日方案卡），"
            "禁止在回复正文里输出动作表格；动作必须来自 get_exercises_tool 返回结果（带 id），不得编造。"
        )
    elif current_id == "roadmap" and not has_roadmap:
        guards.append(
            "校验：当前处于路线图阶段。闯关路线图必须通过 present_roadmap_tool 展示"
            "（title + description + stages，前端渲染 RoadmapCard 关卡时间线），"
            "禁止在回复正文里输出路线图表格；调用前先调 get_goal_knowledge_tool 取原型/"
            "档位/速率作为数字依据。展示后等用户确认，正文只写一两句设计思路。"
        )
    elif current_id in ("assemble", "approve") and not has_proposal:
        guards.append(
            "校验：当前处于装配/审批阶段。必须先调用 present_plan_tool 展示完整提案"
            "（content 表格 + changes 变更清单），再调用 create_plan_tool(传 days) 触发审批；"
            "禁止在回复正文里完整输出计划表格（可写摘要）。用户 reject 带修改稿时，需重新 "
            "present_plan_tool + create_plan_tool，不得直接落库。"
        )

    return guards


class ContentValidationMiddleware(TransientPromptMiddleware):
    """AI 信息校验中间件 - 计划设计流程的大纲/普通结构化信息确定性兜底。

    wrap_model_call（基类 TransientPromptMiddleware 统一实现）：仅在最新消息为
    HumanMessage 时，若处于 plan-design 队列流程（能从历史重建队列快照），按
    当前阶段与历史临时合并校验提示到 request.system_message（F1：不落 checkpoint），
    约束模型必须走展示工具、不得把结构化内容写成正文。无队列快照时直接跳过（零开销）。
    """

    def _prompt(self, messages: list) -> Optional[str]:
        if not messages:
            return None
        if not isinstance(messages[-1], HumanMessage):
            return None

        # 非 plan-design 流程（无队列快照）直接跳过，不影响普通对话；
        # 复用 PlanQueueMiddleware 的单次队列快照（F3）
        queue = get_queue_snapshot(messages)
        if not queue:
            return None

        guards = _build_guards(messages, queue)
        if not guards:
            return None

        prompt = (
            "# AI 信息校验（本轮必须遵守）\n"
            + "\n".join(f"- {g}" for g in guards)
            + "\n请严格遵守上述校验项：结构化内容一律用对应展示工具渲染，不要重复输出到正文。"
        )
        logger.info(
            "[ContentValidation] Injected %d guard(s) | stage=%s",
            len(guards),
            _current_stage_id(queue),
        )
        return prompt
