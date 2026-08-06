"""动作库语义向量回填脚本（exercises.embedding）。

基于 ExerciseService.build_embedding_text（名称中英 + 肌群 + 器械 + 描述）
调用 DashScope text-embedding-v3 生成 1024 维向量，支撑：
- get_exercises_tool 的 semantic_query 语义检索
- 打卡未匹配动作的语义候选兜底

用法（rogers/ 目录，脚本会自动把项目根加入 sys.path）:
    python scripts/backfill_exercise_embeddings.py           # 仅回填 embedding 为 NULL 的行
    python scripts/backfill_exercise_embeddings.py --force   # 全量重算

幂等：可重复执行；单条失败不影响整批，失败条数最终汇总。
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text, update  # noqa: E402

from app.database import async_session_factory  # noqa: E402
from src.agents.harness.runtime.memory.embeddings import get_embedding_model  # noqa: E402
from src.fitme.models.exercise import Exercise  # noqa: E402
from src.fitme.services.exercise_service import ExerciseService  # noqa: E402

CONCURRENCY = 8
BATCH_SIZE = 50


async def _require_vector_column() -> None:
    """确认 exercises.embedding 向量列存在，否则终止（不做降级）。

    pgvector 扩展不可用的环境不会创建该列，语义检索功能整体关闭，无需回填。
    """
    async with async_session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT 1 FROM information_schema.columns"
                    " WHERE table_name = 'exercises' AND column_name = 'embedding'"
                    " AND udt_name = 'vector'"
                )
            )
        ).first()
    if row is None:
        raise SystemExit(
            "exercises.embedding 向量列不存在（pgvector 扩展不可用，语义检索已关闭）。"
            "若已安装 pgvector，请先启动一次应用（init_db 自动补列）再回填。"
        )


async def backfill(force: bool) -> None:
    await _require_vector_column()
    model = get_embedding_model()
    sem = asyncio.Semaphore(CONCURRENCY)

    async with async_session_factory() as session:
        stmt = select(Exercise)
        if not force:
            stmt = stmt.where(Exercise.embedding.is_(None))
        rows = list((await session.execute(stmt)).scalars().all())

    total = len(rows)
    print(f"待回填动作数: {total} (force={force})")
    if total == 0:
        return

    done = 0
    failed = 0

    async def embed_one(ex: Exercise):
        async with sem:
            vec = await model.aget_text_embedding(
                ExerciseService.build_embedding_text(ex)
            )
        return ex.id, vec

    for start in range(0, total, BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        results = await asyncio.gather(
            *(embed_one(ex) for ex in batch), return_exceptions=True
        )
        async with async_session_factory() as session:
            for item in results:
                if isinstance(item, Exception):
                    failed += 1
                    print(f"  向量化失败: {item}")
                    continue
                ex_id, vec = item
                await session.execute(
                    update(Exercise).where(Exercise.id == ex_id).values(embedding=vec)
                )
                done += 1
            await session.commit()
        print(f"进度: {done}/{total} (失败 {failed})")

    print(f"回填完成: 成功 {done}, 失败 {failed}")


def main() -> None:
    parser = argparse.ArgumentParser(description="动作库语义向量回填")
    parser.add_argument(
        "--force", action="store_true", help="全量重算（包含已有向量的行）"
    )
    args = parser.parse_args()
    asyncio.run(backfill(args.force))


if __name__ == "__main__":
    main()
