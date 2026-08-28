"""目标闯关知识层种子数据加载器

读取 `seeds/goal_knowledge.json`，灌入 4 张知识表：
- goal_archetypes（身材原型库）
- strength_standards（力量标准表）
- progress_rates（进度速率表）
- goal_safety_limits（安全限值表）

幂等：各表**仅当为空时**插入（模式照抄 exercise_seed.py），避免每次启动重灌。
数字口径为公开力量标准（ExRx.net / Strength Level 近似值）与训练科学常用
启发式（Helms/McDonald 流派的可持续速率），作为**人群参考值**而非承诺。
"""
import json
import logging
from pathlib import Path

from sqlalchemy import select
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


def _load_seed() -> dict:
    with open(SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


async def seed_goal_knowledge(db: AsyncSession) -> None:
    """启动期种子：各知识表仅当为空时插入（幂等）。

    对空库友好：种子 JSON 缺失时记录错误不阻断启动（照 exercise seed 容错口径）。
    表结构缺失（生产未执行迁移 SQL）时同样记录错误不阻断。
    """
    data = _load_seed()

    # ---- goal_archetypes ----
    if (await db.execute(select(GoalArchetype.id))).first() is None:
        for arch in data.get("archetypes", []):
            db.add(
                GoalArchetype(
                    key=arch["key"],
                    name=arch["name"],
                    tagline=arch.get("tagline"),
                    description=arch.get("description"),
                    target_metrics=arch.get("target_metrics", {}),
                    training_bias=arch.get("training_bias"),
                    diet_bias=arch.get("diet_bias"),
                    stage_hint=arch.get("stage_hint"),
                    stage_narrative_hint=arch.get("stage_narrative_hint"),
                    display_order=arch.get("display_order", 0),
                    is_active=arch.get("is_active", True),
                )
            )
        await db.flush()
        logger.info("goal_archetypes 种子完成：%d 条", len(data.get("archetypes", [])))

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
