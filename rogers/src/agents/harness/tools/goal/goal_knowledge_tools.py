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
    - archetypes: 按用户性别取行的原型目录（扁平 target_metrics / stage_hint /
      stage_narrative_hint / target_exercise_goal / target_exercises / image）
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


class GetExerciseGroupInput(BaseModel):
    """获取身材原型的推荐动作组"""

    archetype_key: str = Field(
        description=(
            "原型 key（lean_aesthetic / v_taper / strength_power / "
            "muscular_mass / healthy_balanced / toned_curves）"
        )
    )


@tool(args_schema=GetExerciseGroupInput)
async def get_exercise_group_tool(
    archetype_key: str,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    获取身材原型的推荐动作组（按用户性别取行）：分组动作清单（含 exercise_id）+ 达成兜底指标。

    使用场景：
    - 为用户选定的身材目标生成训练计划时：按动作组（胸/背/肩/腿/核心…）取动作 ID 编排每日计划
    - 每次生成/修改计划都必须保留末组「拉伸」环节（收尾拉伸为硬性要求）
    - target_exercise_goal 为达成效果的兜底参考指标（人群参考值，非承诺），
      可用于向用户说明预期，不参与关卡出口计算

    返回内容：
    - archetype: 原型信息（key/name/tagline/description/image/stage_hint/target_metrics）
    - exercise_groups: [{group, exercises: [{id, name, name_en, muscle_group,
      equipment, difficulty}]}]
    - target_exercise_goal: 达成兜底指标清单（display 为人读文案）

    本工具只读，不落库、不中断。
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            body = await UserService.get_body_summary(db, user_id)
            gender = _norm_gender(body.get("gender"))

            groups = await GoalKnowledgeService.get_exercise_groups(db, gender)
            matched = [g for g in groups if g["key"] == archetype_key]
            if not matched:
                return {
                    "success": False,
                    "error": f"原型「{archetype_key}」不存在或不适用于当前用户性别",
                }
            arch = matched[0]
            return {
                "success": True,
                "gender": gender,
                "archetype": {
                    k: arch.get(k)
                    for k in (
                        "key",
                        "gender",
                        "name",
                        "tagline",
                        "description",
                        "image",
                        "training_bias",
                        "diet_bias",
                        "stage_hint",
                        "stage_narrative_hint",
                        "target_metrics",
                    )
                },
                "exercise_groups": arch.get("exercise_groups", []),
                "target_exercise_goal": arch.get("target_exercise_goal", []),
                "note": (
                    "推荐动作组为该身材的安全入门配置；编排计划时可在此基础上按用户"
                    "水平增减，末组「拉伸」必须保留。"
                ),
            }
    except Exception as e:
        return error_response(e)
