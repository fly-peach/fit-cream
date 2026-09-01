"""
用户级 Token 用量服务

集中封装 user_token_usages 表的写入（upsert 累加）与聚合查询，
供对话流（chat）、记忆处理（memory 后台任务）、本人查询与管理端统计共用。

与 thread_usages 的「覆盖式」语义区分：本表按 (user, date, source) 累加消费。
"""
from datetime import date, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from src.agents.models.user_token_usage import UserTokenUsage
from src.fitme.schemas.usage import (
    TokenDailyPoint,
    TokenSourceStat,
    UserTokenUsageOut,
)
from utils.timeutil import today
# 来源取值约定（与 user_token_usages.source 一致）
SOURCE_CHAT = "chat"
SOURCE_MEMORY_EXTRACTION = "memory_extraction"
SOURCE_MEMORY_CONSOLIDATION = "memory_consolidation"


class UsageService:
    @staticmethod
    async def record(
        db: AsyncSession,
        *,
        user_id,
        source: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        llm_calls: int = 0,
        estimated: bool = False,
        usage_date: Optional[date] = None,
    ) -> None:
        """累加当日 token 用量（upsert，含 commit）。

        user_id 接受 UUID 或字符串（SQLAlchemy 自动转换，与 ThreadUsage 一致）。
        """
        if total_tokens <= 0 and not llm_calls:
            return
        usage_date = usage_date or today()

        stmt = pg_insert(UserTokenUsage).values(
            id=uuid4(),
            user_id=user_id,
            usage_date=usage_date,
            source=source,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            llm_calls=llm_calls,
            estimated=estimated,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_user_token_usage",
            set_={
                "input_tokens": UserTokenUsage.input_tokens + input_tokens,
                "output_tokens": UserTokenUsage.output_tokens + output_tokens,
                "total_tokens": UserTokenUsage.total_tokens + total_tokens,
                "llm_calls": UserTokenUsage.llm_calls + llm_calls,
                "estimated": UserTokenUsage.estimated | estimated,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)
        await db.commit()

    @staticmethod
    async def record_background(
        *,
        user_id,
        source: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        llm_calls: int = 0,
        estimated: bool = False,
    ) -> None:
        """记忆后台任务（无请求级 db）的独立会话写入，失败仅告警不抛错。

        同时按真实用量扣费（记忆提取/整合同样消耗我方 token）。
        """
        try:
            async with async_session_factory() as session:
                await UsageService.record(
                    session,
                    user_id=user_id,
                    source=source,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    llm_calls=llm_calls,
                    estimated=estimated,
                )
                from src.fitme.services.billing_service import BillingService

                await BillingService.consume(
                    session,
                    user_id=user_id,
                    source=source,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated=estimated,
                    billed=True,
                    description=f"记忆后台（{source}）",
                )
        except Exception:
            import logging

            logging.getLogger("fitcream.usage").warning(
                f"[Usage] record_background failed | user={str(user_id)[:8]} | source={source}",
                exc_info=True,
            )

    @staticmethod
    async def get_user_summary(db: AsyncSession, user_id, days: int = 30) -> UserTokenUsageOut:
        """用户累计总量 + 分来源 + 近 N 天日趋势。"""
        res = (await db.execute(
            select(
                func.coalesce(func.sum(UserTokenUsage.total_tokens), 0),
                func.coalesce(func.sum(UserTokenUsage.input_tokens), 0),
                func.coalesce(func.sum(UserTokenUsage.output_tokens), 0),
                func.coalesce(func.sum(UserTokenUsage.llm_calls), 0),
            ).where(UserTokenUsage.user_id == user_id)
        )).one()

        by_source = [
            TokenSourceStat(
                source=source,
                total_tokens=int(total or 0),
                input_tokens=int(i or 0),
                output_tokens=int(o or 0),
                llm_calls=int(c or 0),
            )
            for source, total, i, o, c in (
                await db.execute(
                    select(
                        UserTokenUsage.source,
                        func.sum(UserTokenUsage.total_tokens),
                        func.sum(UserTokenUsage.input_tokens),
                        func.sum(UserTokenUsage.output_tokens),
                        func.sum(UserTokenUsage.llm_calls),
                    )
                    .where(UserTokenUsage.user_id == user_id)
                    .group_by(UserTokenUsage.source)
                )
            ).all()
        ]

        since = today() - timedelta(days=days - 1)
        daily_rows = (
            await db.execute(
                select(
                    UserTokenUsage.usage_date,
                    func.sum(UserTokenUsage.total_tokens),
                    func.sum(UserTokenUsage.input_tokens),
                    func.sum(UserTokenUsage.output_tokens),
                )
                .where(UserTokenUsage.user_id == user_id, UserTokenUsage.usage_date >= since)
                .group_by(UserTokenUsage.usage_date)
                .order_by(UserTokenUsage.usage_date.asc())
            )
        ).all()
        filled = {since + timedelta(days=i): None for i in range(days)}
        row_map = {d: (t, i, o) for d, t, i, o in daily_rows}
        daily = [
            TokenDailyPoint(
                usage_date=d,
                total_tokens=int((row_map.get(d) or (0, 0, 0))[0] or 0),
                input_tokens=int((row_map.get(d) or (0, 0, 0))[1] or 0),
                output_tokens=int((row_map.get(d) or (0, 0, 0))[2] or 0),
            )
            for d in filled
        ]

        return UserTokenUsageOut(
            total_tokens=int(res[0] or 0),
            input_tokens=int(res[1] or 0),
            output_tokens=int(res[2] or 0),
            llm_calls=int(res[3] or 0),
            by_source=by_source,
            daily=daily,
        )

    @staticmethod
    async def batch_user_totals(db: AsyncSession, user_ids: list) -> dict:
        """批量统计用户累计 token 与近 7 天 token（避免列表逐用户 N+1）。

        返回 {user_id: {"total_tokens": int, "tokens_7d": int}}。
        """
        result: dict = {uid: {"total_tokens": 0, "tokens_7d": 0} for uid in user_ids}
        if not user_ids:
            return result

        total_rows = (
            await db.execute(
                select(
                    UserTokenUsage.user_id,
                    func.sum(UserTokenUsage.total_tokens),
                )
                .where(UserTokenUsage.user_id.in_(user_ids))
                .group_by(UserTokenUsage.user_id)
            )
        ).all()
        for uid, total in total_rows:
            result[uid]["total_tokens"] = int(total or 0)

        since = today() - timedelta(days=6)
        week_rows = (
            await db.execute(
                select(
                    UserTokenUsage.user_id,
                    func.sum(UserTokenUsage.total_tokens),
                )
                .where(
                    UserTokenUsage.user_id.in_(user_ids),
                    UserTokenUsage.usage_date >= since,
                )
                .group_by(UserTokenUsage.user_id)
            )
        ).all()
        for uid, total in week_rows:
            result[uid]["tokens_7d"] = int(total or 0)

        return result

    @staticmethod
    async def get_overview_totals(db: AsyncSession) -> tuple[int, int]:
        """全局累计 token 与近 7 天 token。"""
        total = (
            await db.execute(select(func.coalesce(func.sum(UserTokenUsage.total_tokens), 0)))
        ).scalar_one()
        since = today() - timedelta(days=6)
        tokens_7d = (
            await db.execute(
                select(func.coalesce(func.sum(UserTokenUsage.total_tokens), 0)).where(
                    UserTokenUsage.usage_date >= since
                )
            )
        ).scalar_one()
        return int(total or 0), int(tokens_7d or 0)

    @staticmethod
    async def get_trend_series(db: AsyncSession, days: int = 30) -> list[int]:
        """近 N 天每日全量 token 用量序列（日期缺失补 0）。"""
        since = today() - timedelta(days=days - 1)
        rows = (
            await db.execute(
                select(
                    UserTokenUsage.usage_date,
                    func.sum(UserTokenUsage.total_tokens),
                )
                .where(UserTokenUsage.usage_date >= since)
                .group_by(UserTokenUsage.usage_date)
            )
        ).all()
        row_map = {d: int(t or 0) for d, t in rows}
        return [row_map.get(since + timedelta(days=i), 0) for i in range(days)]