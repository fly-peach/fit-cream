"""归档同一用户的重复 active 计划/饮食计划脚本（任务 2 约束前置）。

在创建 uq_plan_active / uq_diet_plan_active 部分唯一索引前执行：
检出同一 user_id 存在多个 status='active' 的 plans / diet_plans，
仅保留最新一条（按 updated_at 降序第 1 条），其余置为 archived。

用法（rogers/ 目录，脚本会自动把项目根加入 sys.path）:
    python scripts/archive_duplicate_active_plans.py

幂等：可重复执行；无重复 active 时输出 0 条。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update  # noqa: E402

from app.database import async_session_factory  # noqa: E402
from src.fitme.models.diet_plan import DietPlan  # noqa: E402
from src.fitme.models.plan import Plan  # noqa: E402


async def _archive_duplicates(model) -> int:
    """对单个模型，把同 user_id 多余的 active 记为 archived，返回归档条数。"""
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(model.id, model.user_id, model.updated_at)
                .where(model.status == "active")
                .order_by(model.user_id, model.updated_at.desc())
            )
        ).all()
        by_user: dict = {}
        for mid, uid, _updated_at in rows:
            by_user.setdefault(uid, []).append(mid)
        to_archive = []
        for uid, ids in by_user.items():
            if len(ids) > 1:
                to_archive.extend(ids[1:])
        if not to_archive:
            return 0
        await session.execute(
            update(model).where(model.id.in_(to_archive)).values(status="archived")
        )
        await session.commit()
        return len(to_archive)


async def main() -> None:
    archived_plans = await _archive_duplicates(Plan)
    archived_diet = await _archive_duplicates(DietPlan)
    print(f"plans 归档 {archived_plans} 条，diet_plans 归档 {archived_diet} 条")
    print("完成后重启应用（init_db 将创建 uq_plan_active / uq_diet_plan_active）")


if __name__ == "__main__":
    asyncio.run(main())