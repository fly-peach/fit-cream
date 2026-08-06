"""
动作库查询工具

供 Agent 调用，查询健身动作库。
支持两种检索模式：
- keyword：关键词 ilike 匹配（名称/描述，pg_trgm 加速）
- semantic_query：语义向量检索（exercises.embedding，按含义匹配，覆盖更全面）

直接调用 ExerciseService（同进程融合）。
"""

from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.runtime.memory.embeddings import get_embedding_model
from src.agents.harness.tools._common import error_response, session_scope
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
    semantic_query: Optional[str] = Field(
        default=None,
        description=(
            "自然语言语义查询，按动作含义匹配（比 keyword 更全面，可找到名称不含关键词的动作）。"
            "例如'不需要器械就能练背的动作'、'适合膝盖不适人群的腿部训练'、'练爆发力的动作'。"
            "用户用描述性语言表达需求时优先使用本参数，可与肌群/器械/难度筛选组合。"
        ),
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
    semantic_query: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> dict:
    """
    查询健身动作库，根据肌群、器械、关键词或语义描述筛选动作。

    使用场景：
    - 用户问"练胸有什么动作"→ muscle_group="chest"
    - 用户问"没有器械怎么练"→ equipment="bodyweight"
    - 用户问"推荐一些背部动作"→ muscle_group="back"
    - 用户问"有什么适合新手的动作"→ difficulty="beginner"
    - 用户问"有什么不伤膝盖的腿部动作"→ semantic_query="适合膝盖不适人群的腿部训练"
    - 用户问"练核心稳定性的动作"→ semantic_query="核心稳定性训练"

    semantic_query 走语义向量检索，结果按相似度排序并附 similarity 分数；
    keyword 走名称/描述关键词匹配。两者同时提供时优先 semantic_query；
    语义检索不可用（未装 pgvector / 未回填向量）或无命中时自动回退关键词检索。

    Returns:
        包含动作列表和推荐建议的结构化数据
    """
    async with session_scope() as db:
        try:
            similarity_map = {}
            used_semantic = False
            if semantic_query and await ExerciseService.semantic_available(db):
                query_embedding = await get_embedding_model().aget_text_embedding(
                    semantic_query
                )
                scored = await ExerciseService.semantic_search(
                    db,
                    query_embedding,
                    muscle_group=muscle_group,
                    equipment=equipment,
                    difficulty=difficulty,
                    limit=20,
                )
                if scored:
                    exercises = [ex for ex, _ in scored]
                    similarity_map = {ex.id: round(sim, 3) for ex, sim in scored}
                    used_semantic = True

            if not used_semantic:
                # 语义检索不可用（pgvector 缺失/未回填）或无命中时，回退关键词检索；
                # 未提供 keyword 时用 semantic_query 文本兜底
                exercises = await ExerciseService.search(
                    db,
                    muscle_group=muscle_group,
                    equipment=equipment,
                    keyword=keyword or semantic_query,
                    difficulty=difficulty,
                    limit=20,
                )

            exercise_list = []
            for ex in exercises:
                item = {
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
                if used_semantic:
                    item["similarity"] = similarity_map.get(ex.id)
                exercise_list.append(item)

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
            return error_response(e)


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