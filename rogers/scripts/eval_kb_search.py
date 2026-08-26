"""知识库搜索评测脚本（个性化 + 中文召回 + 性能改造的量化验证）。

用法（rogers/ 目录，脚本自动把项目根加入 sys.path，复用 .env 的
DATABASE_URL / DASHSCOPE_API_KEY）:
    python scripts/eval_kb_search.py                          # 完整模式（ILIKE + 画像）
    python scripts/eval_kb_search.py --no-profile             # 基线：不注入画像
    python scripts/eval_kb_search.py --no-ilike               # 对照：关 ILIKE 路
    python scripts/eval_kb_search.py --no-profile --no-ilike  # 旧基线

用例文件：scripts/data/kb_search_eval.json，每条用例：
    {
      "query": "...",
      "group": "generic | personalized | keyword",  # 分组，仅用于汇总展示
      "kb_ids": ["..."],                            # 可选，限定知识库；缺省搜索全部 KB
      "expect_doc_ids": ["..."],                    # 三选一：期望命中文档 ID
      "expect_title_keywords": ["..."],             # 或：标题含关键词
      "expect_content_keywords": ["..."],           # 或：内容含关键词
      "profile_hint": "..."                         # 可选（个性化用例）
    }

指标：recall@5 / recall@10 / MRR@10，按 通用/个性化/关键词 分组汇总输出表格。
直接调用 KBSearchService（绕过工具层），profile_hint 显式传入。
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 将仓库根 .env 写入 os.environ（rerank/embedding 客户端直接读环境变量，非 settings）
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import app.models  # noqa: E402,F401  注册所有 ORM 模型（Base.metadata）
from src.knowledge_base.embeddings import aget_query_embedding  # noqa: E402
from src.knowledge_base.services.search_service import KBSearchService  # noqa: E402

EVAL_LIMIT = 10
DATA_FILE = Path(__file__).resolve().parent / "data" / "kb_search_eval.json"


def _is_match(result: dict, case: dict) -> bool:
    if case.get("expect_doc_ids"):
        return result["document_id"] in set(case["expect_doc_ids"])
    if case.get("expect_title_keywords"):
        title = result.get("document_title") or ""
        return any(k in title for k in case["expect_title_keywords"])
    if case.get("expect_content_keywords"):
        content = result.get("content") or ""
        return any(k in content for k in case["expect_content_keywords"])
    return False


def _metrics(results: list[dict], case: dict) -> tuple[float, float, float]:
    """recall@5 / recall@10 / MRR@10。

    expect_doc_ids 时按期望文档集合求召回率；关键词期望时按「是否命中」计 0/1。
    """
    expected_ids = set(case.get("expect_doc_ids") or [])
    top5 = results[:5]
    top10 = results[:10]
    found5 = {r["document_id"] for r in top5 if _is_match(r, case)}
    found10 = {r["document_id"] for r in top10 if _is_match(r, case)}
    if expected_ids:
        denom = len(expected_ids)
        rec5 = len(expected_ids & found5) / denom
        rec10 = len(expected_ids & found10) / denom
    else:
        rec5 = 1.0 if found5 else 0.0
        rec10 = 1.0 if found10 else 0.0
    mrr = 0.0
    for i, r in enumerate(top10):
        if _is_match(r, case):
            mrr = 1.0 / (i + 1)
            break
    return rec5, rec10, mrr


async def _run_case(db, case: dict, use_profile: bool, use_ilike: bool) -> list[dict]:
    query = case["query"]
    profile_hint = case.get("profile_hint") if use_profile else None
    kb_ids = case.get("kb_ids") or []
    if not kb_ids:
        return await KBSearchService.search_across_knowledge_bases(
            db, query, limit=EVAL_LIMIT, profile_hint=profile_hint, use_ilike=use_ilike
        )
    query_embedding = await aget_query_embedding(query)
    all_results: list[dict] = []
    for kb_id in kb_ids:
        try:
            all_results.extend(
                await KBSearchService.search_documents(
                    db,
                    UUID(kb_id),
                    query,
                    EVAL_LIMIT,
                    query_embedding,
                    profile_hint,
                    use_ilike,
                )
            )
        except Exception as e:
            print(f"  [warn] KB {kb_id} 搜索失败: {e}")
    all_results.sort(key=lambda x: x.get("rank", 0), reverse=True)
    return all_results[:EVAL_LIMIT]


def _fmt_table(rows: list[tuple]) -> None:
    header = ("#", "query", "group", "rec@5", "rec@10", "mrr@10")
    widths = [4, 28, 11, 7, 7, 7]
    line = "  ".join(h.ljust(w) for h, w in zip(header, widths))
    print(line)
    print("-" * len(line))
    for idx, (query, group, rec5, rec10, mrr) in enumerate(rows, start=1):
        q = query if len(query) <= 26 else query[:25] + "…"
        print(
            f"{idx:<4}  {q:<28}  {group:<11}  {rec5:<7.3f}  {rec10:<7.3f}  {mrr:<7.3f}"
        )


def _fmt_summary(name: str, rows: list[tuple]) -> None:
    if not rows:
        return
    n = len(rows)
    avg = lambda i: sum(r[i] for r in rows) / n  # noqa: E731
    print(
        f"{name:<12} n={n:<3} rec@5={avg(2):.3f}  rec@10={avg(3):.3f}  mrr@10={avg(4):.3f}"
    )


async def main(use_profile: bool, use_ilike: bool) -> None:
    if not DATA_FILE.exists():
        raise SystemExit(f"评测用例文件不存在: {DATA_FILE}")
    cases = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    print(f"加载评测用例 {len(cases)} 条（profile={'on' if use_profile else 'off'}, "
          f"ilike={'on' if use_ilike else 'off'}）\n")

    from app.database import async_session_factory

    rows: list[tuple] = []
    async with async_session_factory() as db:
        for case in cases:
            results = await _run_case(db, case, use_profile, use_ilike)
            rec5, rec10, mrr = _metrics(results, case)
            rows.append((case["query"], case.get("group", "-"), rec5, rec10, mrr))

    _fmt_table(rows)
    print("\n--- 汇总 ---")
    for group in ("generic", "personalized", "keyword"):
        _fmt_summary(group, [r for r in rows if r[1] == group])
    _fmt_summary("overall", rows)


def main_cli() -> None:
    parser = argparse.ArgumentParser(description="知识库搜索评测（A/B 对照）")
    parser.add_argument("--no-profile", action="store_true", help="不注入用户画像（基线对照）")
    parser.add_argument("--no-ilike", action="store_true", help="关闭 ILIKE 中文子串路（对照）")
    args = parser.parse_args()
    asyncio.run(main(use_profile=not args.no_profile, use_ilike=not args.no_ilike))


if __name__ == "__main__":
    main_cli()
