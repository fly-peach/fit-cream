"""动作库难度推断回填脚本（exercises.difficulty）。

基于 exercise_seed.infer_difficulty（名称关键词 + 器械/分类启发式，与种子同一套规则）
重算存量动作的难度列。幂等：可重复执行，仅更新发生变化的行。

背景：存量难度分布 beginner 仅 ~2%（29 条）严重失衡，agent 给新手
difficulty=beginner 时候选池过小（真实产品问题）。规则详见 exercise_seed.infer_difficulty。

用法（rogers/ 目录，脚本会自动把项目根加入 sys.path）:
    python scripts/backfill_exercise_difficulty.py

可重复执行；每次输出更新行数与更新后难度分布。
"""
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update  # noqa: E402

from app.database import async_session_factory  # noqa: E402
from src.fitme.models.exercise import Exercise  # noqa: E402
from src.fitme.services.exercise_seed import infer_difficulty  # noqa: E402


async def backfill_difficulty() -> dict:
    """全量重算难度列（幂等，仅更新变化行）。"""
    async with async_session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(
                        Exercise.id,
                        Exercise.name_en,
                        Exercise.equipment,
                        Exercise.category,
                        Exercise.difficulty,
                    )
                )
            ).all()
        )

    pending: list[tuple] = []
    new_difficulties: dict = {}
    for ex_id, name_en, equipment, category, current in rows:
        target = infer_difficulty(name_en or "", equipment=equipment, category=category)
        new_difficulties[ex_id] = target
        if current != target:
            pending.append((ex_id, target))

    if pending:
        async with async_session_factory() as session:
            for ex_id, target in pending:
                await session.execute(
                    update(Exercise)
                    .where(Exercise.id == ex_id)
                    .values(difficulty=target)
                )
            await session.commit()

    distribution = Counter(new_difficulties.values())
    return {
        "total": len(rows),
        "updated": len(pending),
        "distribution": dict(sorted(distribution.items())),
    }


def main() -> None:
    result = asyncio.run(backfill_difficulty())
    print(
        f"难度回填完成：总 {result['total']} 条，更新 {result['updated']} 条；"
        f"分布 {result['distribution']}"
    )


if __name__ == "__main__":
    main()
