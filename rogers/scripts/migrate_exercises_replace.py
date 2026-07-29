"""一次性迁移脚本：用 exercises-dataset（1324 条）替换内置 39 条种子。

流程：
1. 若 dataset 尚未入库（无 media_id 的标记），插入 1324 条。
2. 按 name_en 精确匹配 + 手动 override 表，将内置 39 条映射到 dataset 动作。
3. 把 plan_day_exercises / checkin_exercises 的 exercise_id 重映射到新 id。
4. 删除已无引用的内置动作；仍被引用但无匹配的保留（避免 FK 孤儿）。

幂等：可重复执行（已入库则跳过插入，已删除则 0 影响）。

运行：
    cd rogers && uv run python scripts/migrate_exercises_replace.py
"""
import sys
import uuid
from pathlib import Path

# 让脚本可在任意 CWD 运行：把 rogers/ 加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, delete, func, select, update  # noqa: E402

from app.config import settings  # noqa: E402
from src.fitme.models.checkin import CheckinExercise  # noqa: E402
from src.fitme.models.exercise import Exercise  # noqa: E402
from src.fitme.models.plan import PlanDayExercise  # noqa: E402
from src.fitme.services.exercise_seed import load_dataset  # noqa: E402

# 内置 39 的 name_en -> dataset name（仅高置信度匹配；未列出的走精确匹配或保留）
# dataset 动作名与内置 name_en 多为模糊（如 Pull Up -> pull-up），故维护此 override 表。
NAME_EN_OVERRIDES = {
    "Incline Dumbbell Press": "dumbbell incline bench press",
    "Lat Pulldown": "cable lat pulldown full range of motion",
    "Barbell Row": "barbell bent over row",
    "Pull Up": "pull-up",
    "Barbell Squat": "barbell full squat",
    "Dumbbell Shoulder Press": "dumbbell seated shoulder press",
    "Lateral Raise": "dumbbell lateral raise",
    "Tricep Pushdown": "cable pushdown",
    "Deadlift": "barbell deadlift",
    "Push Up": "push-up",
    "Lying Leg Curl": "lever lying leg curl",
    "Seated Cable Row": "cable seated row",
    "Dips": "triceps dips floor",
    "Seated Dumbbell Curl": "dumbbell seated curl",
    "Standing Calf Raise": "barbell standing calf raise",
    "Incline Barbell Press": "barbell incline bench press",
    "Side Bend on Roman Chair": "dumbbell side bend",
    "Hammer Curl": "dumbbell hammer curl",
}


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def main() -> None:
    dsn = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(dsn)

    with engine.begin() as conn:
        # 1. 插入 1324 条（若 dataset 未入库：以 media_id 非空作为标记）
        has_media = conn.execute(
            select(func.count()).select_from(Exercise).where(Exercise.media_id.isnot(None))
        ).scalar()
        if not has_media:
            records = load_dataset()
            rows = [{**rec, "id": uuid.uuid4()} for rec in records]
            conn.execute(Exercise.__table__.insert(), rows)
            print(f"[1] 插入 dataset 动作 {len(rows)} 条")
        else:
            print(f"[1] dataset 已入库（{has_media} 条带 media_id），跳过插入")

        # 2. 收集内置 39（media_id IS NULL）与 dataset 动作（media_id NOT NULL）
        ours = conn.execute(
            select(Exercise.id, Exercise.name_en, Exercise.name).where(Exercise.media_id.is_(None))
        ).all()
        new_rows = conn.execute(
            select(Exercise.id, Exercise.name).where(Exercise.media_id.isnot(None))
        ).all()
        new_by_norm = {_norm(name): eid for eid, name in new_rows}

        # 3 + 4. 重映射引用 + 删除
        remapped = deleted = kept = unmatched = 0
        for oid, oname_en, _oname in ours:
            target_name = NAME_EN_OVERRIDES.get(oname_en)
            new_id = new_by_norm.get(_norm(target_name)) if target_name else None
            if new_id is None:
                new_id = new_by_norm.get(_norm(oname_en))

            if new_id is not None:
                conn.execute(
                    update(PlanDayExercise)
                    .where(PlanDayExercise.exercise_id == oid)
                    .values(exercise_id=new_id)
                )
                conn.execute(
                    update(CheckinExercise)
                    .where(CheckinExercise.exercise_id == oid)
                    .values(exercise_id=new_id)
                )
                conn.execute(delete(Exercise).where(Exercise.id == oid))
                remapped += 1
                deleted += 1
            else:
                unmatched += 1
                refs = conn.execute(
                    select(func.count()).select_from(PlanDayExercise).where(
                        PlanDayExercise.exercise_id == oid
                    )
                ).scalar() or 0
                refs += conn.execute(
                    select(func.count()).select_from(CheckinExercise).where(
                        CheckinExercise.exercise_id == oid
                    )
                ).scalar() or 0
                if refs == 0:
                    conn.execute(delete(Exercise).where(Exercise.id == oid))
                    deleted += 1
                else:
                    kept += 1
                    print(f"    保留（有 {refs} 处引用但无匹配）: {oname_en}")

        print(f"[2] 内置动作 {len(ours)} 条")
        print(f"[3] 重映射并删除 {remapped} 条，无匹配删除 {deleted - remapped} 条")
        print(f"[4] 无匹配保留 {kept} 条，无匹配共 {unmatched} 条")

        # 校验 FK 完整性
        orphan_plan = conn.execute(
            select(func.count()).select_from(PlanDayExercise).where(
                ~PlanDayExercise.exercise_id.in_(
                    select(Exercise.id).select_from(Exercise)
                )
            )
        ).scalar() or 0
        orphan_checkin = conn.execute(
            select(func.count()).select_from(CheckinExercise).where(
                ~CheckinExercise.exercise_id.in_(
                    select(Exercise.id).select_from(Exercise)
                )
            )
        ).scalar() or 0
        total = conn.execute(select(func.count()).select_from(Exercise)).scalar() or 0
        print(f"[校验] exercises 总数={total}，plan 孤儿={orphan_plan}，checkin 孤儿={orphan_checkin}")
        if orphan_plan or orphan_checkin:
            print("!! 检测到 FK 孤儿，请人工核查")
        else:
            print("OK: 无 FK 孤儿")


if __name__ == "__main__":
    main()
