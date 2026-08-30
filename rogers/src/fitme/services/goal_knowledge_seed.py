"""目标闯关知识层种子数据加载器

读取 `seeds/goal_knowledge.json`，灌入 4 张知识表：
- goal_archetypes（身材原型库，v2：一行 = 一个 (key, gender) 组合，字段扁平化，
  含 image / target_exercises / target_exercise_goal 展示字段）
- strength_standards（力量标准表）
- progress_rates（进度速率表）
- goal_safety_limits（安全限值表）

goal_archetypes 每次启动按 (key, gender) upsert（种子 JSON 为唯一真源，11 行开销可忽略）；
其余 3 表维持「仅当为空时插入」的幂等口径。
数字口径为公开力量标准（ExRx.net / Strength Level 近似值）与训练科学常用
启发式（Helms/McDonald 流派的可持续速率），作为**人群参考值**而非承诺。
"""
import json
import logging
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.goal import (
    GoalArchetype,
    GoalSafetyLimit,
    ProgressRate,
    StrengthStandard,
)

logger = logging.getLogger("fitcream")

SEED_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "seeds" / "goal_knowledge.json"
)

_ARCHETYPE_UPSERT_FIELDS = (
    "name",
    "tagline",
    "description",
    "image",
    "target_metrics",
    "target_exercise_goal",
    "target_exercises",
    "training_bias",
    "diet_bias",
    "stage_hint",
    "stage_narrative_hint",
    "display_order",
    "is_active",
)


def _load_seed() -> dict:
    with open(SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


def _archetype_row(arch: dict) -> dict:
    row = {"key": arch["key"], "gender": arch.get("gender", "male")}
    for field in _ARCHETYPE_UPSERT_FIELDS:
        row[field] = arch.get(field)
    row["target_metrics"] = arch.get("target_metrics") or []
    row["target_exercise_goal"] = arch.get("target_exercise_goal") or []
    row["target_exercises"] = arch.get("target_exercises") or []
    row["display_order"] = arch.get("display_order", 0)
    row["is_active"] = arch.get("is_active", True)
    return row


async def _upsert_archetypes(db: AsyncSession, archetypes: list[dict]) -> None:
    """按 (key, gender) upsert：存在则逐字段更新，缺失则插入（PG ON CONFLICT）。"""
    for arch in archetypes:
        row = _archetype_row(arch)
        await db.execute(
            pg_insert(GoalArchetype)
            .values(**row)
            .on_conflict_do_update(
                index_elements=[GoalArchetype.key, GoalArchetype.gender],
                set_={f: row[f] for f in _ARCHETYPE_UPSERT_FIELDS},
            )
        )
    await db.flush()
    logger.info("goal_archetypes 种子 upsert 完成：%d 行", len(archetypes))


async def seed_goal_knowledge(db: AsyncSession) -> None:
    """启动期种子：原型表按 (key,gender) upsert，其余知识表仅当为空时插入。

    对空库友好：种子 JSON 缺失时记录错误不阻断启动（照 exercise seed 容错口径）。
    表结构缺失（生产未执行迁移 SQL）时同样记录错误不阻断。
    """
    data = _load_seed()

    # ---- goal_archetypes（v2：种子为唯一真源，每次启动全量 upsert）----
    archetypes = data.get("archetypes", [])
    if archetypes:
        await _upsert_archetypes(db, archetypes)

    # ---- strength_standards（按 gender -> lift -> level -> multiplier 展平）----
    if (await db.execute(select(StrengthStandard.id))).first() is None:
        rows = []
        for gender, lifts in (data.get("strength_standards") or {}).items():
            for lift, levels in lifts.items():
                for level, multiplier in levels.items():
                    rows.append(
                        StrengthStandard(
                            gender=gender,
                            lift=lift,
                            level=level,
                            bw_multiplier=multiplier,
                        )
                    )
        db.add_all(rows)
        await db.flush()
        logger.info("strength_standards 种子完成：%d 条", len(rows))

    # ---- progress_rates ----
    if (await db.execute(select(ProgressRate.id))).first() is None:
        rows = [ProgressRate(**r) for r in data.get("progress_rates", [])]
        db.add_all(rows)
        await db.flush()
        logger.info("progress_rates 种子完成：%d 条", len(rows))

    # ---- goal_safety_limits ----
    if (await db.execute(select(GoalSafetyLimit.id))).first() is None:
        rows = []
        for lim in data.get("safety_limits", []):
            rows.append(
                GoalSafetyLimit(
                    metric=lim["metric"],
                    gender=lim["gender"],
                    floor_value=lim.get("floor_value"),
                    ceiling_value=lim.get("ceiling_value"),
                    note=lim.get("note"),
                )
            )
        db.add_all(rows)
        await db.flush()
        logger.info("goal_safety_limits 种子完成：%d 条", len(rows))

    # ---- 下线旧结构残留行（v2 种子不再包含的行，如旧的不分性别原型）----
    keys = {a["key"] for a in archetypes}
    stale = (
        await db.execute(
            select(GoalArchetype.id).where(GoalArchetype.key.notin_(keys))
        )
    ).scalars().all()
    if stale:
        await db.execute(
            update(GoalArchetype)
            .where(GoalArchetype.id.in_(list(stale)))
            .values(is_active=False)
        )
        await db.flush()
        logger.info("goal_archetypes 旧结构行下线：%d 条（is_active=false）", len(stale))
