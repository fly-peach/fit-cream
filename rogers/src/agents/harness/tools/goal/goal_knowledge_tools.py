"""
目标闯关知识层工具

get_goal_knowledge_tool：设计路线图前必调，返回按用户性别过滤的原型目录
（含量化区间，标注「人群参考值」）+ 按用户体重换算的力量标准表（有实测则
标注当前档位）+ 对应经验层级的进度速率 + 安全限值。
"""
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.tools._common import error_response, extract_user_id, session_scope
from src.fitme.services.goal_service import (
    GoalKnowledgeService,
    PerformanceTestService,
)
from src.fitme.services.user_service import UserService

_LEVEL_ORDER = ["untrained", "novice", "intermediate", "advanced", "elite"]
_GENDER_NORM = {"male": "male", "m": "male", "男": "male", "female": "female", "f": "female", "女": "female"}


def _norm_gender(raw: Optional[str]) -> str:
    if not raw:
        return "male"
    return _GENDER_NORM.get(str(raw).strip().lower(), "male")


async def _annotate_levels(standards: list, tests: dict) -> list:
    """把各档 kg 与实测比对，标注用户当前所在档位（取满足的最高档）。"""
    for st in standards:
        lift = st["lift"]
        test = tests.get(lift)
        if test:
            st["current"] = st["level"] == _current_level(standards, lift, test["value"])
        else:
            st["current"] = False
    return standards


def _current_level(standards: list, lift: str, value: float) -> Optional[str]:
    """按体重倍数换算各档 kg 后，返回 value 满足的最高档。"""
    rows = sorted(
        [s for s in standards if s["lift"] == lift],
        key=lambda s: s["bw_multiplier"],
    )
    level = None
    for r in rows:
        if r["kg"] is not None and value >= r["kg"]:
            level = r["level"]
    return level


class GetGoalKnowledgeInput(BaseModel):
    """获取目标闯关知识（原型/力量标准/进度速率/安全限值）"""

    archetype_key: Optional[str] = Field(
        default=None, description="指定原型 key（如 lean_aesthetic）；不填则返回全部可用原型目录"
    )
    experience_level: Optional[str] = Field(
        default=None,
        pattern="^(beginner|intermediate|advanced)$",
        description="用户经验层级，用于返回对应进度速率；不填默认 beginner",
    )


@tool(args_schema=GetGoalKnowledgeInput)
async def get_goal_knowledge_tool(
    archetype_key: Optional[str] = None,
    experience_level: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    获取目标闯关知识：身材原型目录 + 力量标准 + 进度速率 + 安全限值。设计路线图前必调。

    使用场景：
    - plan-creation 流程的 vision 步：向用户呈现可选身材原型（含量化区间，标注「人群参考值」）
    - 分解关卡前：拿当前力量档位、可持续进度速率、安全下限作为关卡数字的依据
    - 用户想调整目标时：重新取原型区间做比对

    返回内容：
    - archetypes: 按用户性别过滤的原型目录（含 target_metrics / stage_hint / 分性别叙事）
    - strength_standards: 按用户体重换算的各档 kg 值，有实测的动作标注当前档位
    - progress_rates: 对应经验层级的月度可持续变化区间（kg/月、%/月）
    - safety_limits: 安全限值（体脂下限、月度体重变化上限、单关增量硬上限）

    本工具只读，不落库、不中断。
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            body = await UserService.get_body_summary(db, user_id)
            gender = _norm_gender(body.get("gender"))
            weight = body.get("weight_kg")

            archetypes = await GoalKnowledgeService.get_archetypes(db, gender)
            standards = await GoalKnowledgeService.get_strength_standards(
                db, gender, weight
            )
            rates = await GoalKnowledgeService.get_progress_rates(
                db, experience_level or "beginner"
            )
            safety = await GoalKnowledgeService.get_safety_limits(db)

            tests = await PerformanceTestService.get_latest_tests(db, user_id)
            standards = await _annotate_levels(standards, tests)

            if archetype_key:
                filtered = [a for a in archetypes if a["key"] == archetype_key]
                if filtered:
                    archetypes = filtered
                else:
                    return {
                        "success": False,
                        "error": f"原型「{archetype_key}」不存在或不适用于当前用户",
                    }

            return {
                "success": True,
                "gender": gender,
                "bodyweight_kg": weight,
                "archetypes": archetypes,
                "strength_standards": standards,
                "progress_rates": rates,
                "safety_limits": safety,
                "latest_tests": tests,
                "note": "以上为人群参考值（公开力量标准与训练科学常用启发式），用于参考，非承诺。",
            }
    except Exception as e:
        return error_response(e)
