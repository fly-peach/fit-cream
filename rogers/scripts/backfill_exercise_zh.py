"""一次性回填脚本：将库内 dataset 动作的中英双字段刷新到最新 transform_record 产物。

背景：库内 1324 条是用旧版 transform_record 导入的，name 存为英文，
且 body_part_zh/target_zh/equipment_zh/muscle_subgroup_zh/secondary_muscles_zh/
instruction_steps_en 等新加双语列均为 NULL。seed_exercises/migrate 幂等不会刷新存量行，
故按 media_id 全字段 UPDATE 一次。

幂等：可重复执行，结果始终对齐 load_dataset()。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, func, select, update  # noqa: E402

from app.config import settings  # noqa: E402
from src.fitme.models.exercise import Exercise  # noqa: E402
from src.fitme.services.exercise_seed import load_dataset  # noqa: E402


def _has_cjk(s: str | None) -> bool:
    return bool(s) and any("\u4e00" <= ch <= "\u9fff" for ch in s)


def main() -> None:
    dsn = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(dsn)

    records = load_dataset()
    by_media = {r["media_id"]: r for r in records if r.get("media_id")}
    print(f"load_dataset 取得 {len(records)} 条，{len(by_media)} 条带 media_id")

    with engine.begin() as conn:
        before = conn.execute(
            select(func.count()).select_from(Exercise).where(Exercise.media_id.isnot(None))
        ).scalar()
        before_zh = conn.execute(
            select(func.count()).select_from(Exercise).where(Exercise.name.op("~")("[一-龥]"))
        ).scalar()
        print(f"回填前：dataset 行 {before}，name 含中文 {before_zh}")

        updated = 0
        for mid, rec in by_media.items():
            fields = {k: v for k, v in rec.items() if k != "media_id"}
            res = conn.execute(
                update(Exercise).where(Exercise.media_id == mid).values(**fields)
            )
            updated += res.rowcount or 0

        after_zh = conn.execute(
            select(func.count()).select_from(Exercise).where(Exercise.name.op("~")("[一-龥]"))
        ).scalar()
        bp_zh = conn.execute(
            select(func.count()).select_from(Exercise).where(Exercise.body_part_zh.isnot(None))
        ).scalar()
        tgt_zh = conn.execute(
            select(func.count()).select_from(Exercise).where(Exercise.target_zh.isnot(None))
        ).scalar()
        eq_zh = conn.execute(
            select(func.count()).select_from(Exercise).where(Exercise.equipment_zh.isnot(None))
        ).scalar()
        sec_zh = conn.execute(
            select(func.count()).select_from(Exercise).where(Exercise.secondary_muscles_zh.isnot(None))
        ).scalar()
        steps_en = conn.execute(
            select(func.count()).select_from(Exercise).where(Exercise.instruction_steps_en.isnot(None))
        ).scalar()
        total = conn.execute(select(func.count()).select_from(Exercise)).scalar()

        print(f"UPDATE 命中 {updated} 行")
        print(f"回填后：总数 {total}，name 含中文 {after_zh}")
        print(
            f"  body_part_zh={bp_zh} target_zh={tgt_zh} equipment_zh={eq_zh} "
            f"secondary_muscles_zh={sec_zh} instruction_steps_en={steps_en}"
        )


if __name__ == "__main__":
    main()
