"""
计划提案展示工具

纯展示工具：把 Agent 设计的结构化计划提案输出给前端，驱动 Plan 卡片渲染。
不落库、不中断、无副作用，仅作为 ReAct 步骤流中的一个标记节点。

配合流程（见 skills/plan-creation/SKILL.md）：
    AI 设计提案 -> 调用 present_plan_tool（前端渲染 Plan 卡片预览）
    -> AI 调用 create_plan_tool -> HumanInTheLoopMiddleware 中断 -> 审批

前端在 AgentTrace 中按工具名 present_plan_tool 特判为 <Plan> 卡片，
读取本工具的入参（title/description/content）渲染，而非读取返回值。
"""

from typing import Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class PresentPlanInput(BaseModel):
    """计划提案入参"""

    title: str = Field(description="计划标题，如「4 周增肌入门计划」")
    description: str = Field(description="一句话计划摘要，如「每周 4 次力量训练，渐进超负荷」")
    content: str = Field(
        description=(
            "计划正文（markdown）：包含训练日/动作/组数/次数/重量的表格，"
            "或饮食计划的每日餐食安排。前端会渲染为 markdown。"
            "须按用户经验水平分层设计，并在正文开头注明面向的经验层级"
            "（初学者/进阶/资深）与对应的强度/容量规格。"
        )
    )
    changes: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description=(
            "即将执行的数据变更清单（用户批准前的变更总览），每项为 "
            "{\"domain\": 域, \"action\": 操作, \"target\": 对象, \"detail\": 说明}，"
            "如 [{\"domain\": \"训练计划\", \"action\": \"新增\", "
            "\"target\": \"4周增肌入门计划\", \"detail\": \"每周4天力量训练\"}, "
            "{\"domain\": \"用户档案\", \"action\": \"更新\", "
            "\"target\": \"体重\", \"detail\": \"72kg\"}]。"
            "涵盖本次批准通过后会写入数据库的全部变更。"
        ),
    )


@tool(args_schema=PresentPlanInput)
async def present_plan_tool(
    title: str,
    description: str,
    content: str,
    changes: Optional[List[Dict[str, str]]] = None,
) -> dict:
    """
    向用户展示一份结构化计划提案（训练计划或饮食计划）。

    使用场景：
    - 设计完成训练/饮食计划后，正式创建（落库）前，先用本工具把提案展示给用户预览
    - 调用本工具后应紧接着调用 create_plan_tool / create_diet_plan_tool 触发用户审批

    changes 传入本次将写入数据库的变更清单，前端渲染为变更总览表格，
    用户确认后才会在审批通过时真正执行。

    本工具仅用于前端展示，不会写入数据库，也不会触发审批中断。
    真正的落库与审批由 create_plan_tool / create_diet_plan_tool 完成。

    Args:
        title: 计划标题
        description: 一句话摘要
        content: markdown 正文（动作/组数/次数表格 或 餐食安排）
        changes: 即将执行的数据变更清单

    Returns:
        ``{"ok": True}``，无其他业务数据
    """
    return {"ok": True}
