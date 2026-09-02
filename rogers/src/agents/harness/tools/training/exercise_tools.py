"""
动作库查询工具

供 Agent 调用，查询健身动作库。
支持两种检索模式：
- keyword：关键词 ilike 匹配（名称/描述，pg_trgm 加速）
- semantic_query：语义向量检索（exercises.embedding，按含义匹配，覆盖更全面）

直接调用 ExerciseService（同进程融合）。
"""

from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.tools._common import error_response, extract_user_id, session_scope
from src.fitme.services.exercise_service import ExerciseService


def _first_sentence(text: Optional[str], max_len: int = 80) -> str:
    """取描述首句并截断（工具返回只给设计所需摘要，完整步骤走详情页）。"""
    if not text:
        return ""
    text = text.strip()
    for sep in ("。", "！", "？", ".", "!", "?"):
        idx = text.find(sep)
        if idx != -1:
            text = text[: idx + 1]
            break
    text = text.strip()
    return text[:max_len] + ("…" if len(text) > max_len else "")


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
        description="搜索关键词，匹配动作名称或描述。传动作名词项（如'深蹲'、'卧推'），勿传整句。",
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
    config: RunnableConfig = None,  # type: ignore[assignment]
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

    semantic_query 走混合检索（向量 + 可选 keyword 词项 RRF 融合 + rerank 精排），
    结果按相关度排序并附 similarity 分数；keyword 走名称/描述词项匹配。
    两者同时提供时优先 semantic_query（keyword 作为 RRF 融合词项）；
    语义检索不可用（未装 pgvector / 未回填向量）或无命中时自动回退关键词检索。
    带筛选条件的语义检索零命中时，自动去掉筛选条件重试一次，并在返回中置
    filter_relaxed=true 提示模型结果已放宽筛选。

    返回字段为设计所需白名单（精简，降低逐日设计轮 token 载荷）：
    id/url/name/name_en/muscle_group/target_zh/muscle_subgroup_zh/equipment_zh/
    difficulty/category/is_compound/description（首句摘要）；语义模式附 similarity。
    image/gif_url/instruction_steps 等完整字段不进本返回，详情走 /exercises/<id>。
    每个返回动作的 exercise_id 即设计落库用的动作 ID。

    回复用户时，若涉及具体动作，须用返回的 `url` 以 markdown 链接形式
    附上站内详情链接（如 `[卧推动作详解](/exercises/<id>)`），
    只使用工具返回的 url，不编造。

    Returns:
        包含动作列表和推荐建议的结构化数据
    """
    user_id = extract_user_id(config)
    async with session_scope() as db:
        try:
            similarity_map = {}
            filter_relaxed = False
            used_semantic = False
            if semantic_query and await ExerciseService.semantic_available(db):
                keyword_terms = [keyword] if keyword else None
                scored = await ExerciseService.hybrid_search(
                    db,
                    semantic_query,
                    muscle_group=muscle_group,
                    equipment=equipment,
                    difficulty=difficulty,
                    keyword_terms=keyword_terms,
                    limit=20,
                )
                if scored:
                    exercises = [ex for ex, _ in scored]
                    similarity_map = {ex.id: round(sim, 3) for ex, sim in scored}
                    used_semantic = True
                elif muscle_group or equipment or difficulty:
                    # 带 filter 的语义检索零命中：去 filter 重试一次，附提示模型
                    relaxed = await ExerciseService.hybrid_search(
                        db,
                        semantic_query,
                        keyword_terms=keyword_terms,
                        limit=20,
                    )
                    if relaxed:
                        exercises = [ex for ex, _ in relaxed]
                        similarity_map = {ex.id: round(sim, 3) for ex, sim in relaxed}
                        used_semantic = True
                        filter_relaxed = True

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

            # 检索成本计费：query embedding + rerank 候选（估算 token；失败不影响结果）
            if used_semantic and user_id:
                try:
                    from src.agents.harness.orchestration.model_factory import estimate_tokens
                    from src.fitme.services.billing_service import BillingService

                    emb_tok = estimate_tokens(semantic_query or "")
                    rerank_tok = emb_tok + sum(
                        estimate_tokens(ExerciseService.build_embedding_text(ex))
                        for ex in exercises
                    )
                    await BillingService.consume_search_cost(
                        db,
                        user_id=user_id,
                        source="exercise_search",
                        embedding_tokens=emb_tok,
                        rerank_tokens=rerank_tok,
                        description="动作库检索",
                    )
                except Exception:
                    pass

            exercise_list = []
            for ex in exercises:
                item = {
                    "id": str(ex.id),
                    "url": f"/exercises/{ex.id}",
                    "name": ex.name,
                    "name_en": ex.name_en,
                    "muscle_group": ex.muscle_group,
                    "target_zh": ex.target_zh,
                    "muscle_subgroup_zh": ex.muscle_subgroup_zh,
                    "equipment_zh": ex.equipment_zh,
                    "difficulty": ex.difficulty,
                    "category": ex.category,
                    "is_compound": ex.is_compound,
                    "description": _first_sentence(ex.description),
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
                "filter_relaxed": filter_relaxed,
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