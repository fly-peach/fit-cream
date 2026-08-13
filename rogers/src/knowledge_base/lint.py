"""
知识库健康检查（纯逻辑，由 Service 层传入数据）

参考 LLM Wiki mcp/tools/lint.py 的 LintHandler，实现 15+ 条确定性检查。
LintContext 一次性预计算 source/wiki lookup + 计数，所有检查共享。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.knowledge_base.frontmatter import extract_tags, parse_frontmatter

_FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]]+)\]:\s*(.+)$", re.MULTILINE)
_FOOTNOTE_USE_RE = re.compile(r"\[\^([^\]]+)\](?!:)")
_SOURCE_EXT_RE = re.compile(r"\.(pdf|docx?|pptx?|xlsx?|csv|html?|md|txt)$", re.IGNORECASE)
_ROOT_PAGES = frozenset({"overview.md", "index.md", "readme.md", "log.md"})
_MAX_ISSUES_PER_GROUP = 40

Scope = Literal["all", "wiki", "sources"]


@dataclass(frozen=True)
class LintIssue:
    severity: Literal["error", "warn"]
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class LintContext:
    source_lookup: dict[str, dict]
    wiki_lookup: dict[str, dict]
    wiki_page_count: int


def _doc_path(doc: dict) -> str:
    return f"{doc.get('path', '/')}{doc.get('filename', '')}"


def _is_wiki_page(doc: dict) -> bool:
    return doc.get("path", "/").startswith("/wiki/")


def _is_root_page(doc: dict) -> bool:
    return doc.get("filename", "").lower() in _ROOT_PAGES


def _is_ledger_page(doc: dict) -> bool:
    return doc.get("filename", "").lower() == "log.md"


def _doc_keys(doc: dict) -> list[str]:
    filename = doc.get("filename", "").lower()
    title = str(doc.get("title") or "").lower()
    keys = [filename, _SOURCE_EXT_RE.sub("", filename)]
    if title:
        keys.extend([title, _SOURCE_EXT_RE.sub("", title)])
    return [k for k in keys if k]


def _build_context(docs: list[dict]) -> LintContext:
    source_lookup: dict[str, dict] = {}
    wiki_lookup: dict[str, dict] = {}
    wiki_count = 0
    for doc in docs:
        if _is_wiki_page(doc):
            wiki_count += 1
            relative = _doc_path(doc).replace("/wiki/", "", 1)
            wiki_lookup[relative.lower()] = doc
            wiki_lookup.setdefault(doc.get("filename", "").lower(), doc)
        else:
            for key in _doc_keys(doc):
                source_lookup.setdefault(key, doc)
    return LintContext(source_lookup, wiki_lookup, wiki_count)


def _resolve_source(filename: str, source_lookup: dict[str, dict]) -> dict | None:
    key = filename.strip().lower()
    if key in source_lookup:
        return source_lookup[key]
    return source_lookup.get(_SOURCE_EXT_RE.sub("", key))


def _resolve_wiki_link(link_path: str, wiki_lookup: dict[str, dict]) -> dict | None:
    key = link_path.split("#", 1)[0].lower()
    return (
        wiki_lookup.get(key)
        or wiki_lookup.get(f"{key}.md")
        or wiki_lookup.get(key.split("/")[-1])
    )


def _normalize_tags(tags: list[str]) -> list[str]:
    return sorted({str(t).strip().lower() for t in tags if str(t).strip()})


def _lint_frontmatter(doc: dict, meta: dict) -> list[LintIssue]:
    path = _doc_path(doc)
    if not meta:
        return [LintIssue("error", "missing-frontmatter", path, "wiki 页无 YAML frontmatter")]

    issues: list[LintIssue] = []
    title = meta.get("title")
    description = meta.get("description")
    fm_tags = extract_tags(meta)

    if not isinstance(title, str) or not title.strip():
        issues.append(LintIssue("error", "missing-title", path, "frontmatter 缺少 title"))
    if not isinstance(description, str) or not description.strip():
        issues.append(LintIssue("warn", "missing-description", path, "frontmatter 缺少 description"))
    if fm_tags is None or len(fm_tags) == 0:
        issues.append(LintIssue("error", "missing-tags", path, "frontmatter 缺少 tags"))
    elif len(fm_tags) < 2:
        issues.append(LintIssue("warn", "too-few-tags", path, "tags 应至少 2 个"))

    indexed_tags = [str(t) for t in (doc.get("tags") or [])]
    if fm_tags and _normalize_tags(fm_tags) != _normalize_tags(indexed_tags):
        issues.append(LintIssue(
            "warn", "tag-index-mismatch", path,
            f"frontmatter tags {fm_tags} 与索引 tags {indexed_tags} 不一致",
        ))
    return issues


def _lint_footnotes(path: str, content: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    def_ids = [fid for fid, _ in _FOOTNOTE_DEF_RE.findall(content)]
    used_ids = _FOOTNOTE_USE_RE.findall(content)

    for fid in sorted({f for f in def_ids if def_ids.count(f) > 1}):
        issues.append(LintIssue("error", "duplicate-footnote", path, f"脚注 ^{fid} 定义重复"))
    for fid in sorted(set(used_ids) - set(def_ids)):
        issues.append(LintIssue("error", "footnote-without-definition", path, f"脚注 ^{fid} 被引用但未定义"))
    for fid in sorted(set(def_ids) - set(used_ids)):
        issues.append(LintIssue("warn", "unused-footnote-definition", path, f"脚注 ^{fid} 已定义但未被引用"))
    return issues


def _lint_citations(doc: dict, content: str, source_lookup: dict[str, dict]) -> list[LintIssue]:
    path = _doc_path(doc)
    issues: list[LintIssue] = []
    from src.knowledge_base.references import parse_citation_filename

    for fid, raw in _FOOTNOTE_DEF_RE.findall(content):
        filename, _ = parse_citation_filename(raw)
        if filename and not _resolve_source(filename, source_lookup):
            issues.append(LintIssue(
                "error", "unresolved-citation", path,
                f"脚注 ^{fid} 引用 {filename}，但无匹配源文件",
            ))
    return issues


def _lint_wiki_links(doc: dict, content: str, wiki_lookup: dict[str, dict]) -> list[LintIssue]:
    from src.knowledge_base.references import parse_wiki_links

    path = _doc_path(doc)
    current_dir = doc.get("path", "").replace("/wiki/", "", 1) if doc.get("path", "").startswith("/wiki/") else ""
    issues: list[LintIssue] = []
    for link_path in parse_wiki_links(content, current_dir):
        if not _resolve_wiki_link(link_path, wiki_lookup):
            issues.append(LintIssue(
                "error", "dangling-link", path,
                f"wiki 链接 {link_path} 无目标页面",
            ))
    return issues


def _lint_orphan(doc: dict, backlinks: list) -> list[LintIssue]:
    if _is_root_page(doc):
        return []
    if backlinks:
        return []
    return [LintIssue("warn", "orphan-page", _doc_path(doc), "wiki 页无入链/入引")]


def run_all_lint(
    docs: list[dict],
    uncited_sources: list[dict],
    stale_pages: list[dict],
    backlinks_map: dict[str, list[dict]],
) -> dict:
    """运行所有 lint 规则，返回完整报告。

    docs: KB 所有文档（含 content）
    uncited_sources / stale_pages: 来自 graph.find_uncited_sources / find_stale_pages
    backlinks_map: {doc_id: [backlink dict]} 入边（仅用于孤儿页判断，只需有无入边）
    """
    ctx = _build_context(docs)
    issues: list[LintIssue] = []

    for doc in docs:
        if not _is_wiki_page(doc):
            continue
        path = _doc_path(doc)
        content = doc.get("content") or ""
        meta, _ = parse_frontmatter(content)
        doc_id = str(doc.get("id", ""))

        if not _is_ledger_page(doc):
            issues.extend(_lint_frontmatter(doc, meta))
            issues.extend(_lint_footnotes(path, content))
        issues.extend(_lint_citations(doc, content, ctx.source_lookup))
        issues.extend(_lint_wiki_links(doc, content, ctx.wiki_lookup))
        issues.extend(_lint_orphan(doc, backlinks_map.get(doc_id, [])))

    # KB 级检查
    for row in uncited_sources:
        issues.append(LintIssue(
            "warn", "uncited-source",
            f"{row.get('path', '')}{row.get('filename', '')}",
            "源文件未被任何 wiki 页引用",
        ))
    for row in stale_pages:
        issues.append(LintIssue(
            "warn", "stale-page",
            f"{row.get('path', '')}{row.get('filename', '')}",
            f"页面自 {row.get('stale_since', '?')} 起标记为过期",
        ))

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warn"]
    return {
        "total": len(issues),
        "errors": len(errors),
        "warnings": len(warnings),
        "issues": [
            {"severity": i.severity, "code": i.code, "path": i.path, "message": i.message}
            for i in issues[:_MAX_ISSUES_PER_GROUP * 2]
        ],
    }
