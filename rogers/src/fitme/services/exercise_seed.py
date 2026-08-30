"""动作库种子数据加载器

读取 vendored `seeds/exercises_dataset_opt.json`（© Gym visual 1324 动作数据集，中英双语优化版），
按字段映射 + 推断规则转换为 Exercise 记录。

幂等：仅当 `exercises` 表为空时才解析 JSON 并批量插入，避免每次启动重解析。
历史上一次性的「内置 39 条替换为 dataset + FK 重映射」迁移已于 2026-08 完成（脚本已随上线清理）。
"""
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from seeds.exercises import SEED_EXERCISES
from src.fitme.models.exercise import (
    EQUIPMENT_COARSENING,
    MUSCLE_GROUP_COARSENING,
    Exercise,
)

logger = logging.getLogger("fitcream")

DATASET_PATH = Path(__file__).resolve().parent.parent.parent.parent / "seeds" / "exercises_dataset_opt.json"

_CAL_PER_MIN = {"cardio": 9.0, "compound": 7.0, "isolation": 4.0}
_DIFFICULTY_KEYWORDS_ADVANCED = ("advanced", "one arm", "weighted", "explosive", "jump")
_DIFFICULTY_KEYWORDS_BEGINNER = ("assisted", "beginner")


def infer_difficulty(
    name: str, equipment: str | None = None, category: str | None = None
) -> str:
    """按名称关键词 + 器械/分类启发式推断动作难度（幂等规则，种子与回填脚本复用）。

    优先级：名称关键词（beginner > advanced）-> 器械/分类启发式 -> 默认 intermediate。
    目标分布：beginner 从 2% 提升到 ~15-25%（器械/弹力带孤立动作、自重孤立非拉伸入门友好）。
    """
    name_lower = (name or "").lower()
    if any(k in name_lower for k in _DIFFICULTY_KEYWORDS_BEGINNER):
        return "beginner"
    if any(k in name_lower for k in _DIFFICULTY_KEYWORDS_ADVANCED):
        return "advanced"
    if category == "isolation":
        if equipment in ("machine", "band"):
            return "beginner"
        if equipment == "bodyweight" and not any(
            k in name_lower for k in ("stretch", "拉伸")
        ):
            return "beginner"
    if equipment == "barbell" and category == "compound":
        return "intermediate"
    return "intermediate"


def _rewrite_media(path: str | None) -> str | None:
    """dataset 'images/0001-X.jpg' -> '/static/exercises/images/0001-X.jpg'"""
    if not path:
        return None
    return f"/static/exercises/{path}"


def _get_lang_value(field: Any, lang: str = "en") -> str | None:
    """从 {"en": ..., "zh": ...} 格式字段中提取指定语言的值。"""
    if isinstance(field, dict):
        return field.get(lang)
    return field


def transform_record(raw: dict[str, Any]) -> dict[str, Any]:
    """将一条 dataset 记录映射为 Exercise 可写入字段（含推断）。"""
    # 新格式: body_part 是 {"en": ..., "zh": ...} 对象
    body_part_en = _get_lang_value(raw.get("body_part"), "en")
    muscle_group = MUSCLE_GROUP_COARSENING.get(body_part_en) if body_part_en else None

    # secondary_muscles 是 {"en": [...], "zh": [...]} 对象
    secondary_obj = raw.get("secondary_muscles") or {}
    secondary_en: list[str] = list(secondary_obj.get("en") or []) if isinstance(secondary_obj, dict) else list(secondary_obj or [])
    is_compound = len(secondary_en) >= 2

    if body_part_en == "cardio":
        category = "cardio"
    else:
        category = "compound" if is_compound else "isolation"

    # name 是 {"en": ..., "zh": ...} 对象
    name_en = _get_lang_value(raw.get("name"), "en") or ""
    name_zh = _get_lang_value(raw.get("name"), "zh") or name_en

    instructions_obj = raw.get("instructions") or {}
    steps_obj = raw.get("instruction_steps") or {}
    steps_zh: list[str] = list(steps_obj.get("zh") or [])
    steps_en: list[str] = list(steps_obj.get("en") or [])
    description = steps_zh[0] if steps_zh else None

    # muscle_group, target, equipment 也是 {"en": ..., "zh": ...} 对象
    muscle_subgroup_en = _get_lang_value(raw.get("muscle_group"), "en")
    muscle_subgroup_zh = _get_lang_value(raw.get("muscle_group"), "zh")
    target_en = _get_lang_value(raw.get("target"), "en")
    target_zh = _get_lang_value(raw.get("target"), "zh")
    equipment_en = _get_lang_value(raw.get("equipment"), "en")
    equipment_zh = _get_lang_value(raw.get("equipment"), "zh")
    body_part_zh = _get_lang_value(raw.get("body_part"), "zh")

    # secondary_muscles 中文
    secondary_zh: list[str] = list(secondary_obj.get("zh") or []) if isinstance(secondary_obj, dict) else []

    # equipment 粗化为 8 类稳定值（equipment_zh 保留原中文标签）
    equipment = EQUIPMENT_COARSENING.get(equipment_en, "other") if equipment_en else None
    difficulty = infer_difficulty(name_en, equipment=equipment, category=category)

    return {
        "name": name_zh,
        "name_en": name_en,
        "muscle_group": muscle_group,
        "muscle_subgroup": muscle_subgroup_en,
        "muscle_subgroup_zh": muscle_subgroup_zh,
        "category": category,
        "is_compound": is_compound,
        "equipment": equipment,
        "equipment_zh": equipment_zh,
        "difficulty": difficulty,
        "calories_per_min": _CAL_PER_MIN.get(category),
        "description": description,
        "instructions": instructions_obj.get("zh"),
        "tips": None,
        "body_part": body_part_en,
        "body_part_zh": body_part_zh,
        "target": target_en,
        "target_zh": target_zh,
        "secondary_muscles": secondary_en,
        "secondary_muscles_zh": secondary_zh,
        "instruction_steps": steps_zh,
        "instruction_steps_en": steps_en,
        "instructions_en": instructions_obj.get("en"),
        "media_id": raw.get("media_id"),
        "image": _rewrite_media(raw.get("image")),
        "gif_url": _rewrite_media(raw.get("gif_url")),
        "attribution": raw.get("attribution"),
    }


def load_dataset() -> list[dict[str, Any]]:
    """读取并转换全部 dataset 记录（1324 条）。"""
    with open(DATASET_PATH, encoding="utf-8") as f:
        raw_list: list[dict[str, Any]] = json.load(f)
    return [transform_record(r) for r in raw_list]


async def seed_exercises(db: AsyncSession):
    """启动期种子：仅当表为空时插入 dataset 全量记录（幂等，稳态不解析 16MB）。"""
    count_result = await db.execute(select(Exercise.id))
    if count_result.first() is not None:
        return

    # 表为空：优先用 dataset 1324 条；若 dataset 缺失则回退到内置 39 条
    if DATASET_PATH.exists():
        logger.info("开始导入动作库 dataset（1324 条）...")
        records = load_dataset()
        source = "dataset"
    else:
        logger.warning("exercises_dataset_opt.json 缺失，回退内置 39 条种子")
        records = list(SEED_EXERCISES)
        source = "builtin"

    for rec in records:
        db.add(Exercise(**rec))
    await db.flush()
    logger.info(f"动作库种子完成：来源={source}，导入 {len(records)} 条")


async def normalize_exercise_equipment(db: AsyncSession):
    """幂等回填存量动作的 equipment 列为粗化值。

    seed_exercises 仅插空表，存量 1324 行仍是 dataset 细粒度原始值（28 种）。
    此函数将它们统一为 8 类稳定值，与 agent 工具描述一致。
    """
    # 1) 显式映射的细粒度值 -> 粗化值
    for raw, coarse in EQUIPMENT_COARSENING.items():
        await db.execute(
            update(Exercise).where(Exercise.equipment == raw).values(equipment=coarse)
        )
    # 2) map 未覆盖的细粒度值（medicine ball/stability ball/ergometer 等）兜底 other；
    #    已是粗化值的行不受影响，保证幂等。
    valid_coarse = list(set(EQUIPMENT_COARSENING.values()) | {"other"})
    await db.execute(
        update(Exercise)
        .where(Exercise.equipment.isnot(None))
        .where(Exercise.equipment.notin_(valid_coarse))
        .values(equipment="other")
    )
    logger.info("动作库 equipment 回填完成（粗化为 8 类）")
