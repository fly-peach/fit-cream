"""
路线图工具（present == 落库）

- present_roadmap_tool：纯展示（不落库不中断），驱动前端 RoadmapCard，用户确认发
  「[确认路线图]」
- create_roadmap_tool：调 GoalRoadmapService 确定性校验 + 落库；加入 HITL 审批中断
- get_roadmap_tool：返回 active 路线图全量 + 最新力量基线 + 最新身体指标；流程开始
  判定「是否已有路线图」也用它
- record_baseline_tool：基线/复测落库（performance_tests + HealthMetric）
"""
from typing import List, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.tools._common import error_response, extract_user_id, session_scope
from src.fitme.schemas.goal import (
    GoalRoadmapCreate,
    MetricCriterion,
    PerformanceTestCreate,
    StageDesign,
)
from src.fitme.services.goal_service import (
    GoalRoadmapService,
    PerformanceTestService,
    roadmap_to_dict,
)
from src.fitme.services.user_service import UserService


class PresentRoadmapInput(BaseModel):
    """路线图提案入参（与 create_roadmap_tool 的 stages 结构保持一致：提案==落库）"""

    title: str = Field(min_length=1, max_length=200, description="路线图标题")
    description: Optional[str] = Field(default=None, description="一句话说明")
    stages: List[StageDesign] = Field(
        min_length=2, max_length=8, description="关卡列表（2-8 关）"
    )


@tool(args_schema=PresentRoadmapInput)
async def present_roadmap_tool(
    title: str,
    description: Optional[str] = None,
    stages: List[StageDesign] = None,  # type: ignore[assignment]
) -> dict:
    """
    向用户展示闯关路线图提案（纯展示，不落库不中断）。前端渲染 RoadmapCard（纵向关卡时间线）。

    使用场景：
    - plan-creation 流程的 roadmap 步：按原型/档位/速率分解关卡后调用，代替在正文里写路线图表格
    - 用户确认后发结构化消息「[确认路线图]」回到对话，你读取后再调用 create_roadmap_tool 落库

    关卡是**检查点**而非日期承诺：expected_weeks 仅作排期参考，出关以复测达标为准。

    Args:
        title: 路线图标题，如「薄肌有线条 · 3 关闯关路线」
        description: 一句话说明
        stages: 关卡设计（stage_index/title/exit_criteria/expected_weeks/training_focus）

    Returns:
        ``{"ok": True}``
    """
    return {"ok": True}


class CreateRoadmapInput(BaseModel):
    """创建路线图入参（提案==落库，stages 结构与 present_roadmap_tool 一致）"""

    archetype_key: str = Field(min_length=1, max_length=50, description="身材原型 key，如 lean_aesthetic")
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None)
    target_metrics: List[MetricCriterion] = Field(
        default_factory=list, description="最终目标（末关近似，含 op/value/unit）"
    )
    stages: List[StageDesign] = Field(min_length=2, max_length=8)
    experience_level: Optional[str] = Field(
        default="beginner",
        pattern="^(beginner|intermediate|advanced)$",
        description="用户经验层级，用于进度速率校验",
    )


@tool(args_schema=CreateRoadmapInput)
async def create_roadmap_tool(
    archetype_key: str,
    title: str,
    description: Optional[str] = None,
    target_metrics: List[MetricCriterion] = None,  # type: ignore[assignment]
    stages: List[StageDesign] = None,  # type: ignore[assignment]
    experience_level: str = "beginner",
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    创建（或整体替换）用户的闯关路线图：确定性校验 + 落库。触发用户审批中断。

    使用场景：
    - roadmap 步用户确认「[确认路线图]」后调用；已有 active 路线图会先置 archived（整体替换）
    - 执行前要求用户审批确认（approve 落库 / reject 返回修订）

    校验规则（违规直接拒绝并回传清单，需修正后重试）：
    - 关卡 2-8 个、stage_index 连续、每关出口条件 1-5 条、expected_weeks 2-16
    - 力量类指标跨关单调不减、体脂/腰围单调不增
    - 每关每指标增量不超过进度速率 × 周数换算 × 1.3 容差
    - body_fat_pct 不低于安全下限
    - 末关与原型目标偏离超 15% 会带 warnings（不阻断）

    Returns:
        落库结果：roadmap_id + 各 milestone 状态 + warnings（如有）
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            body = await UserService.get_body_summary(db, user_id)
            gender = body.get("gender") or "male"

            data = GoalRoadmapCreate(
                archetype_key=archetype_key,
                title=title,
                description=description,
                target_metrics=target_metrics or [],
                stages=stages or [],
                horizon_months=None,
            )
            roadmap = await GoalRoadmapService.create_roadmap(
                db, user_id, data, gender=gender, experience_level=experience_level
            )
            result = roadmap_to_dict(roadmap, include_warnings=True)
            return {
                "success": True,
                "roadmap_id": str(roadmap.id),
                "roadmap": result,
                "milestones": [
                    {"stage_index": m["stage_index"], "status": m["status"]}
                    for m in result["milestones"]
                ],
                "warnings": result.get("warnings", []),
                "message": f"路线图「{roadmap.title}」已创建并设为当前闯关路线（共 {len(roadmap.milestones)} 关）",
            }
    except Exception as e:
        return error_response(e)


@tool
async def get_roadmap_tool(config: "RunnableConfig" = None) -> dict:  # type: ignore[assignment]
    """
    查看当前用户的闯关路线图（active）全量 + 最新力量基线 + 最新身体指标。

    使用场景：
    - plan-creation 流程**开始时**判定分支：调用本工具，若已有 active 路线图，
      vision/baseline/roadmap 三项直接标 skipped，按当前关继续设计计划
    - 用户问「我的闯关进度」「现在在哪个关卡」

    Returns:
        路线图（stages+出口条件+状态）、当前关、最新力量基线、最新身体指标
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            roadmap = await GoalRoadmapService.get_active_roadmap(db, user_id)
            tests = await PerformanceTestService.get_latest_tests(db, user_id)
            health = await UserService.get_latest_health_metric(db, user_id)

            body = {
                "weight_kg": float(health.weight_kg) if health and health.weight_kg is not None else None,
                "body_fat_pct": float(health.body_fat_pct) if health and health.body_fat_pct is not None else None,
                "waist_cm": float(health.waist_cm) if health and health.waist_cm is not None else None,
                "height_cm": float(health.height_cm) if health and health.height_cm is not None else None,
            }

            if not roadmap:
                return {
                    "success": True,
                    "has_roadmap": False,
                    "roadmap": None,
                    "latest_tests": tests,
                    "body_metrics": body,
                    "message": "当前没有活跃闯关路线图",
                }

            current = await GoalRoadmapService.get_current_milestone(db, user_id)
            return {
                "success": True,
                "has_roadmap": True,
                "roadmap": roadmap_to_dict(roadmap),
                "current_milestone": {
                    "id": str(current.id),
                    "stage_index": current.stage_index,
                    "title": current.title,
                    "exit_criteria": current.exit_criteria,
                    "expected_weeks": current.expected_weeks,
                }
                if current
                else None,
                "latest_tests": tests,
                "body_metrics": body,
            }
    except Exception as e:
        return error_response(e)


class RecordBaselineInput(BaseModel):
    """基线/复测记录入参"""

    lifts: List[PerformanceTestCreate] = Field(
        min_length=1, description="力量动作测试记录（bench/squat/deadlift/ohp/pull_up）"
    )
    body_fat_pct: Optional[float] = Field(default=None, ge=0, le=100)
    waist_cm: Optional[float] = Field(default=None, ge=0, le=500)
    weight_kg: Optional[float] = Field(default=None, ge=0, le=500)


@tool(args_schema=RecordBaselineInput)
async def record_baseline_tool(
    lifts: List[PerformanceTestCreate] = None,  # type: ignore[assignment]
    body_fat_pct: Optional[float] = None,
    waist_cm: Optional[float] = None,
    weight_kg: Optional[float] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    记录力量/身体基线（或复测）数据到数据库：performance_tests + HealthMetric。不中断直接执行。

    使用场景：
    - plan-creation 流程 baseline 步：baseline 表单提交后，把 reference_lifts 与
      circumference 解析为 lifts + 身体指标落库
    - 后续复测：再次提交同动作 30 天内已有测试记录时自动跳过（幂等）

    Args:
        lifts: 力量动作测试列表（value 为 kg；pull_up 为次数）
        body_fat_pct / waist_cm / weight_kg: 可选身体指标（写 HealthMetric）

    Returns:
        已记录 / 已跳过（30 天内重复）的动作清单
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            result = await PerformanceTestService.record_tests(
                db,
                user_id,
                lifts or [],
                {
                    "body_fat_pct": body_fat_pct,
                    "waist_cm": waist_cm,
                    "weight_kg": weight_kg,
                },
            )
            msg = f"已记录基线：{', '.join(result['recorded'])}"
            if result["skipped"]:
                msg += f"（{', '.join(result['skipped'])} 近 30 天已有记录，未重复录入）"
            return {"success": True, **result, "message": msg}
    except Exception as e:
        return error_response(e)
