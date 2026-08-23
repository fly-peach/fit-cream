"""动作库召回评估服务（黄金集离线评估，schema v2）+ embedding 回填入口

黄金集：``seeds/search_eval_queries.json``（版本化 JSON，不落库、不进数据库表）。
schema v2 每条记录：
- ``query``：用户典型查询（语义/关键词检索输入）
- ``semantic_query``：可选，语义检索输入（缺省时用 query）
- ``relevant_filter``：filter 派生条目，相关集 = 运行时 DB 查询派生（结构过滤 AND
  name/name_en/description ilike 任一词项）。概念/过滤类查询用——相关集大（如「深蹲类动作」
  命中 80 条），recall@K 有数学上限，改测 precision/hit_rate。
- ``relevant_names``：手挑条目（语义安全查询，如「不伤膝盖」），相关集 = 实时解析动作名
  为库内 ID（动作 ID 是运行时生成的 UUID，无法在版本化 JSON 中硬编码）。
- ``keyword_terms``：可选，keyword 路的测试词项（名称词项匹配）；缺省则该条不计 keyword 模式。

评估口径（schema v2，与 get_exercises_tool 同一检索入口）：
- filter 派生条目：precision@K（top-K 相关占比）+ hit_rate@10
- 手挑条目：recall@K + MRR@K
- 分模式：``vector``（纯向量基线）/ ``vector_rerank``（hybrid_search，工具真实路径）/
  ``keyword_terms``（名称词项匹配）

输出：schema 版本号、分口径聚合、零命中清单、每条明细（含 vector_rerank top-10 动作名，
供「练胸复合动作 top-10 出现 bench press」「不伤膝盖 top-10 无深蹲类」人工抽查）。
管理端 /api/admin/search-quality/eval 实时调用。

``backfill_embeddings`` 为 exercises.embedding 的回填实现（幂等、后台任务入口），
scripts/backfill_exercise_embeddings.py 与管理端 /backfill 端点共用同一实现。
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from src.agents.harness.runtime.memory.embeddings import get_embedding_model
from src.fitme.models.exercise import Exercise
from src.fitme.services.exercise_service import ExerciseService

logger = logging.getLogger("fitcream")

GOLDEN_SET_PATH = (
    Path(__file__).resolve().parents[3] / "seeds" / "search_eval_queries.json"
)
DEFAULT_K = 20
SCHEMA_VERSION = 2

_BACKFILL_CONCURRENCY = 8
_BACKFILL_BATCH_SIZE = 50

_MODES = ("vector", "vector_rerank", "keyword_terms")


class SearchRecallService:
    # ============================================================
    # 黄金集
    # ============================================================

    @staticmethod
    def load_golden_set() -> list[dict[str, Any]]:
        """读取版本化黄金集；文件缺失时打 warning 返回空列表。"""
        if not GOLDEN_SET_PATH.exists():
            logger.warning("黄金集缺失: %s", GOLDEN_SET_PATH)
            return []
        try:
            with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning("黄金集解析失败: %s", e)
            return []

    @staticmethod
    async def resolve_relevant_ids(
        db: AsyncSession, names: list[str]
    ) -> set[UUID]:
        """把 relevant_names（中/英文动作名）实时解析为库内 ID 集合。"""
        if not names:
            return set()
        result = await db.execute(
            select(Exercise.id).where(
                or_(Exercise.name.in_(names), Exercise.name_en.in_(names))
            )
        )
        return {row[0] for row in result.all()}

    @staticmethod
    def _apply_structural_filters(stmt, f: dict[str, Any]):
        """结构过滤（muscle_group/equipment/difficulty/category）AND 叠加。"""
        for key in ("muscle_group", "equipment", "difficulty", "category"):
            val = f.get(key)
            if val:
                stmt = stmt.where(getattr(Exercise, key) == val)
        return stmt

    @staticmethod
    async def derive_filtered_ids(
        db: AsyncSession, f: dict[str, Any]
    ) -> set[UUID]:
        """filter 派生相关集：结构过滤 AND name/name_en/description ilike 任一词项。"""
        if not f:
            return set()
        stmt = SearchRecallService._apply_structural_filters(
            select(Exercise.id), f
        )
        name_any = f.get("name_any") or []
        if name_any:
            clauses = []
            for term in name_any:
                clauses.append(Exercise.name.ilike(f"%{term}%"))
                clauses.append(Exercise.name_en.ilike(f"%{term}%"))
                clauses.append(Exercise.description.ilike(f"%{term}%"))
            stmt = stmt.where(or_(*clauses))
        result = await db.execute(stmt)
        return {row[0] for row in result.all()}

    # ============================================================
    # 指标（纯计算）
    # ============================================================

    @staticmethod
    def _recall(hits: list[UUID], relevant: set[UUID]) -> float:
        if not relevant:
            # 零命中反例（relevant 为空）：期望无命中
            return 1.0 if not hits else 0.0
        return len(set(hits) & relevant) / len(relevant)

    @staticmethod
    def _mrr(hits: list[UUID], relevant: set[UUID]) -> float:
        """Mean Reciprocal Rank：首个相关命中的倒数排名（无命中为 0）。"""
        for rank, uid in enumerate(hits, start=1):
            if uid in relevant:
                return 1.0 / rank
        return 0.0

    @staticmethod
    def _precision(hits: list[UUID], relevant: set[UUID]) -> float:
        """precision@K：top-K 命中中相关占比（K 由 hits 长度决定）。"""
        if not hits:
            return 0.0
        return len(set(hits) & relevant) / len(hits)

    @staticmethod
    def _hit_rate(hits: list[UUID], relevant: set[UUID], top: int = 10) -> float:
        """hit_rate@10：top-10 是否出现至少一个相关命中。"""
        return 1.0 if any(uid in relevant for uid in hits[:top]) else 0.0

    # ============================================================
    # 检索入口（与 get_exercises_tool 同源）
    # ============================================================

    @staticmethod
    def _filters_of(q: dict[str, Any]) -> dict[str, Any]:
        f = q.get("relevant_filter") or {}
        return {
            "muscle_group": f.get("muscle_group"),
            "equipment": f.get("equipment"),
            "difficulty": f.get("difficulty"),
            "category": f.get("category"),
        }

    @staticmethod
    async def _vector_hits(
        db: AsyncSession, q: dict[str, Any], k: int
    ) -> list[UUID]:
        """纯向量基线（无 rerank）：语义检索 top-K 命中 ID。"""
        if not await ExerciseService.semantic_available(db):
            return []
        query_text = (q.get("semantic_query") or q.get("query") or "").strip()
        if not query_text:
            return []
        try:
            embedding = await get_embedding_model().aget_text_embedding(query_text)
        except Exception as e:
            logger.warning("[SearchEval] embedding 失败: %s", e)
            return []
        scored = await ExerciseService.semantic_search(
            db, embedding, limit=k, **SearchRecallService._filters_of(q)
        )
        return [ex.id for ex, _ in scored]

    @staticmethod
    async def _hybrid_scored(
        db: AsyncSession, q: dict[str, Any], k: int
    ) -> list[Any]:
        """hybrid_search（工具真实入口：向量 + 可选 RRF + rerank）。"""
        query_text = (q.get("semantic_query") or q.get("query") or "").strip()
        if not query_text:
            return []
        return await ExerciseService.hybrid_search(
            db,
            query_text,
            keyword_terms=q.get("keyword_terms") or None,
            limit=k,
            **SearchRecallService._filters_of(q),
        )

    @staticmethod
    async def _keyword_term_hits(
        db: AsyncSession, q: dict[str, Any], k: int
    ) -> list[UUID]:
        """名称词项匹配（keyword_terms 并集，结构过滤同工具路径）。"""
        ids: list[UUID] = []
        filters = SearchRecallService._filters_of(q)
        for term in q.get("keyword_terms") or []:
            items = await ExerciseService.search(
                db, keyword=term, limit=k, **filters
            )
            ids.extend(ex.id for ex in items)
        return list(dict.fromkeys(ids))

    # ============================================================
    # 评估
    # ============================================================

    @staticmethod
    async def evaluate(db: AsyncSession, k: int = DEFAULT_K) -> dict[str, Any]:
        """实时跑黄金集评估（不落库，schema v2）。

        Returns:
            ``{"schema_version", "k", "total_queries", "zero_hit_queries",
               "aggregates", "details"}``
        """
        golden = SearchRecallService.load_golden_set()
        details: list[dict[str, Any]] = []
        zero_hit_queries: list[dict[str, Any]] = []

        agg = {
            "filter_derived": {
                "queries": 0,
                "by_mode": {
                    m: {"queries": 0, "sum_precision": 0.0, "sum_hit_rate": 0.0}
                    for m in _MODES
                },
            },
            "hand_picked": {
                "queries": 0,
                "by_mode": {
                    m: {"queries": 0, "sum_recall": 0.0, "sum_mrr": 0.0}
                    for m in _MODES
                },
            },
        }

        for q in golden:
            is_filter = bool(q.get("relevant_filter"))
            if is_filter:
                relevant = await SearchRecallService.derive_filtered_ids(
                    db, q["relevant_filter"]
                )
            else:
                relevant = await SearchRecallService.resolve_relevant_ids(
                    db, q.get("relevant_names") or []
                )

            vector = await SearchRecallService._vector_hits(db, q, k)
            hybrid_scored = await SearchRecallService._hybrid_scored(db, q, k)
            hybrid = [ex.id for ex, _ in hybrid_scored]
            keyword = await SearchRecallService._keyword_term_hits(db, q, k)

            per_mode: dict[str, Any] = {}
            for mode in _MODES:
                if mode == "keyword_terms" and not q.get("keyword_terms"):
                    per_mode[mode] = None
                    continue
                hits = {"vector": vector, "vector_rerank": hybrid, "keyword_terms": keyword}[
                    mode
                ]
                if is_filter:
                    per_mode[mode] = {
                        "precision_at_k": round(
                            SearchRecallService._precision(hits, relevant), 4
                        ),
                        "hit_rate_at_10": round(
                            SearchRecallService._hit_rate(hits, relevant), 4
                        ),
                    }
                else:
                    per_mode[mode] = {
                        "recall_at_k": round(
                            SearchRecallService._recall(hits, relevant), 4
                        ),
                        "mrr_at_k": round(
                            SearchRecallService._mrr(hits, relevant), 4
                        ),
                    }
                if not relevant or per_mode[mode] is None:
                    continue
                bucket = agg["filter_derived" if is_filter else "hand_picked"]
                acc = bucket["by_mode"][mode]
                if is_filter:
                    acc["sum_precision"] += per_mode[mode]["precision_at_k"]
                    acc["sum_hit_rate"] += per_mode[mode]["hit_rate_at_10"]
                else:
                    acc["sum_recall"] += per_mode[mode]["recall_at_k"]
                    acc["sum_mrr"] += per_mode[mode]["mrr_at_k"]
                acc["queries"] += 1
            if relevant:
                agg["filter_derived" if is_filter else "hand_picked"]["queries"] += 1

            if relevant and not hybrid:
                zero_hit_queries.append(
                    {
                        "query": q.get("query"),
                        "kind": "filter_derived" if is_filter else "hand_picked",
                    }
                )

            details.append(
                {
                    "query": q.get("query"),
                    "kind": "filter_derived" if is_filter else "hand_picked",
                    "relevant_count": len(relevant),
                    "relevant_filter": q.get("relevant_filter"),
                    "keyword_terms": q.get("keyword_terms") or [],
                    "per_mode": {m: per_mode[m] for m in _MODES},
                    "hit_counts": {
                        m: len(
                            {
                                "vector": vector,
                                "vector_rerank": hybrid,
                                "keyword_terms": keyword,
                            }[m]
                        )
                        for m in _MODES
                    },
                    "vector_rerank_top10": [
                        ex.name for ex, _ in hybrid_scored[:10]
                    ],
                }
            )

        aggregates: dict[str, Any] = {}
        for bucket in ("filter_derived", "hand_picked"):
            by_mode = {}
            for mode, acc in agg[bucket]["by_mode"].items():
                n = acc["queries"]
                if bucket == "filter_derived":
                    by_mode[mode] = {
                        "queries": n,
                        "average_precision_at_k": round(acc["sum_precision"] / n, 4)
                        if n
                        else None,
                        "average_hit_rate_at_10": round(acc["sum_hit_rate"] / n, 4)
                        if n
                        else None,
                    }
                else:
                    by_mode[mode] = {
                        "queries": n,
                        "average_recall_at_k": round(acc["sum_recall"] / n, 4)
                        if n
                        else None,
                        "average_mrr_at_k": round(acc["sum_mrr"] / n, 4)
                        if n
                        else None,
                    }
            aggregates[bucket] = {
                "queries": agg[bucket]["queries"],
                "by_mode": by_mode,
            }

        return {
            "schema_version": SCHEMA_VERSION,
            "k": k,
            "total_queries": len(golden),
            "zero_hit_queries": zero_hit_queries,
            "aggregates": aggregates,
            "details": details,
        }

    # ============================================================
    # embedding 回填（脚本 / 管理端后台任务共用）
    # ============================================================

    @staticmethod
    async def backfill_embeddings(force: bool = False) -> dict[str, Any]:
        """增量（默认）/全量（force）回填 exercises.embedding。

        幂等：单条失败不影响整批；未回填仅新字段不生效，不破坏现有检索。
        基于 ExerciseService.build_embedding_text（改检索文本后必须重跑以生效）。
        """
        async def _vector_column_exists() -> bool:
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
            return row is not None

        if not await _vector_column_exists():
            return {
                "ok": 0,
                "failed": 0,
                "message": "exercises.embedding 向量列不存在（pgvector 未启用），回填跳过",
            }

        model = get_embedding_model()
        sem = asyncio.Semaphore(_BACKFILL_CONCURRENCY)

        async with async_session_factory() as session:
            stmt = select(Exercise)
            if not force:
                stmt = stmt.where(Exercise.embedding.is_(None))
            rows = list((await session.execute(stmt)).scalars().all())

        total = len(rows)
        if total == 0:
            return {"ok": 0, "failed": 0, "message": "无待回填动作"}

        done, failed = 0, 0

        async def embed_one(ex: Exercise):
            async with sem:
                vec = await model.aget_text_embedding(
                    ExerciseService.build_embedding_text(ex)
                )
            return ex.id, vec

        for start in range(0, total, _BACKFILL_BATCH_SIZE):
            batch = rows[start : start + _BACKFILL_BATCH_SIZE]
            results = await asyncio.gather(
                *(embed_one(ex) for ex in batch), return_exceptions=True
            )
            async with async_session_factory() as session:
                for item in results:
                    if isinstance(item, Exception):
                        failed += 1
                        logger.warning("[Backfill] 向量化失败: %s", item)
                        continue
                    ex_id, vec = item
                    await session.execute(
                        update(Exercise).where(Exercise.id == ex_id).values(embedding=vec)
                    )
                    done += 1
                await session.commit()

        return {
            "ok": done,
            "failed": failed,
            "total": total,
            "message": f"回填完成：成功 {done}，失败 {failed}",
        }
