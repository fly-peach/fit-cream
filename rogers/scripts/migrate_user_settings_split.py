"""用户目标/基础信息拆表迁移脚本。

背景：UserSettings 拆为两张表——
- user_goals（目标：goal/训练/营养/通知偏好）
- user_settings（基础信息：当前身高/体重）

步骤：
1. 把旧 user_settings 的目标/营养/通知列复制到新建的 user_goals（幂等 upsert）。
2. 用每个用户最新 HealthMetric 回填 user_settings.height_cm / weight_kg。
3. （可选 --drop）删除 user_settings 已迁移的旧列（破坏性，验证后再执行）。

用法（rogers/ 目录，脚本会自动把项目根加入 sys.path）:
    python scripts/migrate_user_settings_split.py           # 迁移 + 回填
    python scripts/migrate_user_settings_split.py --drop    # 迁移 + 回填 + 删旧列
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.database import async_session_factory  # noqa: E402

OLD_GOAL_COLUMNS = [
    "goal",
    "weekly_training_goal",
    "target_weight_kg",
    "target_body_fat_pct",
    "calorie_goal",
    "protein_goal_g",
    "carbs_goal_g",
    "fat_goal_g",
    "notification_enabled",
]


async def migrate_goals() -> int:
    """把旧 user_settings 的目标列复制到 user_goals，返回复制的用户数。"""
    async with async_session_factory() as session:
        rows = (
            await session.execute(text(
                "SELECT user_id, goal, weekly_training_goal, target_weight_kg,"
                " target_body_fat_pct, calorie_goal, protein_goal_g, carbs_goal_g,"
                " fat_goal_g, notification_enabled FROM user_settings"
            ))
        ).all()
        count = 0
        for row in rows:
            user_id = row.user_id
            cols = ", ".join(OLD_GOAL_COLUMNS)
            placeholders = ", ".join(f":{c}" for c in OLD_GOAL_COLUMNS)
            params = {c: getattr(row, c) for c in OLD_GOAL_COLUMNS}
            params["user_id"] = user_id
            await session.execute(text(
                f"INSERT INTO user_goals (user_id, {cols})"
                f" VALUES (:user_id, {placeholders})"
                " ON CONFLICT (user_id) DO UPDATE SET"
                + ", ".join(f"{c} = EXCLUDED.{c}" for c in OLD_GOAL_COLUMNS)
            ), params)
            count += 1
        await session.commit()
        return count


async def backfill_base_info() -> tuple[int, int]:
    """用最新 HealthMetric 回填 user_settings.height_cm / weight_kg，返回(身高,体重)回填数。"""
    async with async_session_factory() as session:
        h = await session.execute(text(
            "UPDATE user_settings us SET height_cm = hm.height_cm"
            " FROM (SELECT DISTINCT ON (user_id) user_id, height_cm"
            "       FROM health_metrics ORDER BY user_id, measure_date DESC) hm"
            " WHERE us.user_id = hm.user_id AND hm.height_cm IS NOT NULL"
            "   AND us.height_cm IS NULL"
        ))
        w = await session.execute(text(
            "UPDATE user_settings us SET weight_kg = hm.weight_kg"
            " FROM (SELECT DISTINCT ON (user_id) user_id, weight_kg"
            "       FROM health_metrics ORDER BY user_id, measure_date DESC) hm"
            " WHERE us.user_id = hm.user_id AND hm.weight_kg IS NOT NULL"
            "   AND us.weight_kg IS NULL"
        ))
        await session.commit()
        return h.rowcount, w.rowcount


async def drop_old_columns() -> list[str]:
    """删除 user_settings 已迁移的旧列（破坏性）。"""
    async with async_session_factory() as session:
        dropped = []
        for col in OLD_GOAL_COLUMNS:
            await session.execute(text(
                f'ALTER TABLE user_settings DROP COLUMN IF EXISTS "{col}"'
            ))
            dropped.append(col)
        await session.commit()
        return dropped


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop", action="store_true", help="迁移后删除 user_settings 旧列（破坏性）")
    args = parser.parse_args()

    migrated = await migrate_goals()
    print(f"user_goals 已复制/更新 {migrated} 个用户的目标数据")

    h, w = await backfill_base_info()
    print(f"user_settings 身高回填 {h}，体重回填 {w}")

    if args.drop:
        dropped = await drop_old_columns()
        print(f"已删除 user_settings 旧列: {', '.join(dropped)}")
    else:
        print("未删除旧列。确认无误后以 --drop 删除（破坏性，先备份）")


if __name__ == "__main__":
    asyncio.run(main())