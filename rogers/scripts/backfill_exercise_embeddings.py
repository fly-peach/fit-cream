"""动作库语义向量回填脚本（exercises.embedding）。

基于 ExerciseService.build_embedding_text（名称中英 + 肌群 + 器械 + 难度 + 分类 +
描述 + 次要肌群）调用 DashScope text-embedding-v3 生成 1024 维向量，支撑：
- get_exercises_tool 的 semantic_query 语义检索
- 打卡未匹配动作的语义候选兜底

实现与 src/fitme/services/search_recall_service.py 的
SearchRecallService.backfill_embeddings 共用（脚本 / 管理端后台任务同一入口）。

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

from src.fitme.services.search_recall_service import SearchRecallService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="动作库语义向量回填")
    parser.add_argument(
        "--force", action="store_true", help="全量重算（包含已有向量的行）"
    )
    args = parser.parse_args()
    result = asyncio.run(SearchRecallService.backfill_embeddings(force=args.force))
    print(result.get("message", "回填完成"))


if __name__ == "__main__":
    main()
