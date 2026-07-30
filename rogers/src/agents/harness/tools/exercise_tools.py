"""
动作库查询工具

供 Agent 调用，查询健身动作库。
直接调用 ExerciseService（同进程融合）。
"""

from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.database import async_session_factory
from src.fitme.services.exercise_service import ExerciseService


class GetExercisesInput(BaseModel):
    """查询动作库的输入参数"""

    muscle_group: Optional[str] = Field(
        default=None,
        description=(
            "目标肌群筛选。可选值：chest(胸)、back(背)、legs(腿)、"
            "shoulders(肩)、arms(手臂)、core(核心)、full_body(全身)。"
            "不填则返回所有动作。"
        ),
    )
    equipment: Optional[str] = Field(
        default=None,
        description=(
            "器械类型筛选。可选值：barbell(杠铃)、dumbbell(哑铃)、"
            "machine(器械)、bodyweight(自重)、cable(绳索)、kettlebell(壶铃)、band(弹力带)。"
            "不填则不限制器械。"
        ),
    )
    keyword: Optional[str] = Field(
        default=None,
        description="搜索关键词，匹配动作名称或描述。例如'深蹲'、'卧推'。",
    )
    difficulty: Optional[str] = Field(
        default=None,
        description="难度筛选：beginner(初级)、intermediate(中级)、advanced(高级)。",
    )


@tool(args_schema=GetExercisesInput)
async def get_exercises_tool(
    muscle_group: Optional[str] = None,
    equipment: Optional[str] = None,
    keyword: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> dict:
    """
    查询健身动作库，根据肌群、器械、关键词等条件筛选动作。

    使用场景：
    - 用户问"练胸有什么动作"→ muscle_group="chest"
    - 用户问"没有器械怎么练"→ equipment="bodyweight"
    - 用户问"推荐一些背部动作"→ muscle_group="back"
    - 用户问"有什么适合新手的动作"→ difficulty="beginner"

    Returns:
        包含动作列表和推荐建议的结构化数据
    """
    async with async_session_factory() as db:
        try:
            exercises = await ExerciseService.search(
                db,
                muscle_group=muscle_group,
                equipment=equipment,
                keyword=keyword,
                difficulty=difficulty,
                limit=20,
            )

            exercise_list = [
                {
                    "id": str(ex.id),
                    "name": ex.name,
                    "name_en": ex.name_en,
                    "muscle_group": ex.muscle_group,
                    "target": ex.target,
                    "target_zh": ex.target_zh,
                    "equipment": ex.equipment,
                    "equipment_zh": ex.equipment_zh,
                    "difficulty": ex.difficulty,
                    "category": ex.category,
                    "is_compound": ex.is_compound,
                    "description": ex.description,
                    "instruction_steps": ex.instruction_steps,
                    "image": ex.image,
                    "gif_url": ex.gif_url,
                }
                for ex in exercises
            ]

            # 生成推荐文本
            recommendation = _build_recommendation(
                exercises, muscle_group, equipment
            )

            return {
                "success": True,
                "count": len(exercise_list),
                "exercises": exercise_list,
                "recommendation": recommendation,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


def _build_recommendation(exercises, muscle_group, equipment) -> str:
    """根据查询结果生成推荐文本"""
    if not exercises:
        return "没有找到匹配的动作，试试调整筛选条件。"

    muscle_names = {
        "chest": "胸部",
        "back": "背部",
        "legs": "腿部",
        "shoulders": "肩部",
        "arms": "手臂",
        "core": "核心",
        "full_body": "全身",
    }

    parts = []
    if muscle_group and muscle_group in muscle_names:
        parts.append(f"以下是{muscle_names[muscle_group]}训练推荐动作")
    elif equipment:
        parts.append(f"以下是使用{equipment}的推荐动作")
    else:
        parts.append("以下是推荐动作")

    # 按难度分组统计
    beginner_count = sum(1 for e in exercises if e.difficulty == "beginner")
    intermediate_count = sum(1 for e in exercises if e.difficulty == "intermediate")
    advanced_count = sum(1 for e in exercises if e.difficulty == "advanced")

    level_info = []
    if beginner_count:
        level_info.append(f"初级{beginner_count}个")
    if intermediate_count:
        level_info.append(f"中级{intermediate_count}个")
    if advanced_count:
        level_info.append(f"高级{advanced_count}个")

    if level_info:
        parts.append(f"（{'、'.join(level_info)}）")

    return "".join(parts) + "。建议从初级动作开始，逐步提升难度。"