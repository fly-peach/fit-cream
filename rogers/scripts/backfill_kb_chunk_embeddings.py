"""知识库 chunk 语义向量回填脚本（kb_chunks.embedding）。

调用 DashScope text-embedding-v3 为存量 / 缺失向量的 chunk 补向量，支撑：
- search_documents 的语义混合检索（向量路召回）

用法（rogers/ 目录，脚本会自动把项目根加入 sys.path）:
    python scripts/backfill_kb_chunk_embeddings.py                        # 仅回填 embedding IS NULL 的行
    python scripts/backfill_kb_chunk_embeddings.py --kb <kb_id>           # 仅回填指定知识库
    python scripts/backfill_kb_chunk_embeddings.py --force                # 全量重算（包含已有向量）
    python scripts/backfill_kb_chunk_embeddings.py --ensure-column        # 列缺失时自动补列后回填

幂等：可重复执行；单条失败不影响整批，失败条数最终汇总。
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text, update  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import async_session_factory  # noqa: E402
from src.knowledge_base.embeddings import embed_chunks  # noqa: E402
from src.knowledge_base.models.chunk import KBChunk  # noqa: E402

CONCURRENCY = 8
BATCH_SIZE = 50


async def _ensure_vector_column(create: bool = False) -> None:
    """确认 kb_chunks.embedding 向量列存在；--ensure-column 时自动补列。

    pgvector 扩展不可用的环境不会创建该列，语义检索整体关闭，无需回填。
    """

    async def _column_exists(session) -> bool:
        row = (
            await session.execute(
                text(
                    "SELECT 1 FROM information_schema.columns"
                    " WHERE table_name = 'kb_chunks' AND column_name = 'embedding'"
                    " AND udt_name = 'vector'"
                )
            )
        ).first()
        return row is not None

    async with async_session_factory() as session:
        if await _column_exists(session):
            return
        if not create:
            raise SystemExit(
                "kb_chunks.embedding 向量列不存在（pgvector 扩展不可用，语义检索已关闭）。"
                "若已安装 pgvector，请先启动一次应用（init_db 自动补列）"
                "或使用 --ensure-column 自动补列后再回填。"
            )
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await session.execute(
            text(
                "ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS embedding"
                f" vector({settings.EMBEDDING_DIMENSION})"
            )
        )
        await session.commit()
        print("已补列 kb_chunks.embedding（自动）")


async def backfill(kb_id: str | None, force: bool, ensure_column: bool = False) -> None:
    await _ensure_vector_column(create=ensure_column)

    async with async_session_factory() as session:
        stmt = (
            "SELECT c.id, c.content FROM kb_chunks c"
            " JOIN wiki_documents d ON d.id = c.document_id"
            " WHERE d.archived = FALSE"
        )
        params: dict = {}
        if kb_id:
            stmt += " AND d.kb_id = :kb_id"
            params["kb_id"] = kb_id
        if not force:
            stmt += " AND c.embedding IS NULL"
        rows = list((await session.execute(text(stmt), params)).all())

    total = len(rows)
    print(f"待回填 chunk 数: {total} (kb={kb_id or 'all'}, force={force})")
    if total == 0:
        return

    done = 0

    for start in range(0, total, BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        vectors = await embed_chunks([r[1] for r in batch])
        async with async_session_factory() as session:
            for (chunk_id, _content), vec in zip(batch, vectors):
                if vec is None:
                    continue
                await session.execute(
                    update(KBChunk).where(KBChunk.id == chunk_id).values(embedding=vec)
                )
                done += 1
            await session.commit()
        print(f"进度: {done}/{total}")

    print(f"回填完成: 成功 {done}/{total}")


def main() -> None:
    parser = argparse.ArgumentParser(description="知识库 chunk 语义向量回填")
    parser.add_argument("--kb", default=None, help="仅回填指定知识库 UUID")
    parser.add_argument(
        "--force", action="store_true", help="全量重算（包含已有向量的行）"
    )
    parser.add_argument(
        "--ensure-column",
        action="store_true",
        help="列缺失时自动执行 CREATE EXTENSION vector + ALTER TABLE 补列",
    )
    args = parser.parse_args()
    asyncio.run(backfill(args.kb, args.force, args.ensure_column))


if __name__ == "__main__":
    main()