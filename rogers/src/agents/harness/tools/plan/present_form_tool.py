"""
信息采集表单展示工具

纯展示工具：把需要用户补全的多维度信息采集表单输出给前端，驱动 FormCard 渲染。
不落库、不中断、无副作用，仅作为 ReAct 步骤流中的一个标记节点。

表单模板（字段定义/类型/选项）定义在前端 form-templates.ts，本工具只传
form_id 与已知字段的预填值。前端把已有值渲染为只读（档案已有数据不让用户改），
缺失字段渲染为可编辑控件。

配合流程（见 skills/plan-creation/SKILL.md）：
    get_user_summary_tool 查缺 -> present_form_tool 弹表单
    -> 用户填写提交（结构化用户消息回到对话）
    -> body_profile 字段调 update_user_profile_tool 落库；
       其余维度字段仅用于本次规划，禁止写库
"""

from typing import Any, Dict, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class PresentFormInput(BaseModel):
    """信息采集表单入参"""

    form_id: str = Field(
        description=(
            "前端表单模板 key。可选值以前端 form-templates.ts 的 FORM_TEMPLATES keys "
            "为准（单一来源，勿在此枚举）：body_profile(基础身体数据，可落库)、"
            "health_safety(健康与安全基线)、fitness_level(当前体能水平)、"
            "exercise_history(运动经历与习惯)、diet_profile(饮食偏好与结构)、"
            "baseline(基线评测数据)、lifestyle(生活方式与客观环境)。"
            "其中 body_profile 提交后写入档案，其余表单仅本次参考、禁止写库。"
        )
    )
    title: str = Field(description="表单卡片标题，如「补充基础身体数据」")
    description: str = Field(description="一句话说明为什么需要这些信息")
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "已知字段的预填值 {字段key: 值}，如 {\"height_cm\": 175}。"
            "未知/需用户填写的字段不要传入。"
            "后端档案已有的数据必须传入（前端渲染为只读，用户不可修改）。"
        ),
    )


@tool(args_schema=PresentFormInput)
async def present_form_tool(
    form_id: str,
    title: str,
    description: str,
    fields: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    向用户展示一张信息采集表单（纯展示，不落库不中断）。

    使用场景：
    - 设计计划前的 Intake 阶段，需要用户补全某个维度的信息时调用
    - get_user_summary_tool 返回 missing_fields 非空时，用 body_profile 表单补全
    - 收集规划参考信息（健康/体能/经历/生活方式）时逐卡调用

    调用后等待用户提交：用户填写的内容会以「[表单提交: <form_id>]」结构化
    消息回到对话，你读取后继续流程。

    数据落库边界（重要）：
    - body_profile 提交的字段 -> 调用 update_user_profile_tool 写入档案
    - 其余表单提交的字段 -> 仅用于本次计划设计，禁止调用任何工具写入数据库

    Args:
        form_id: 前端表单模板 key
        title: 表单卡片标题
        description: 一句话说明
        fields: 已知字段的预填值 {字段key: 值}

    Returns:
        ``{"ok": True}``，无其他业务数据
    """
    return {"ok": True}
