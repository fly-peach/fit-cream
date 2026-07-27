"""
引用解析器（纯逻辑，零 DB 依赖）

参考 LLM Wiki api/services/references.py，从 wiki 页面 Markdown 提取跨文档引用：
- 脚注引用 [^N]: filename.pdf, p.3 -> cites（wiki -> raw）
- 内部链接 [文本](page.md) -> links_to（wiki -> wiki）

构建 3 层查找映射确保匹配鲁棒性，并做相对路径解析（./ ../ /wiki/ 裸名）。
"""
from __future__ import annotations

import re

_CITATION_RE = re.compile(r"\[\^\d+\]:\s*(.+)$", re.MULTILINE)
_WIKI_LINK_RE = re.compile(r"(?<!!)\[(?:[^\]]*)\]\(([^)]+)\)")
_SOURCE_EXT_RE = re.compile(
    r"\.(pdf|docx?|pptx?|xlsx?|csv|html?|md|txt)$", re.IGNORECASE
)


def parse_citation_filename(raw: str) -> tuple[str, int | None]:
    """从脚注提取文件名 + 页码，如 'paper.pdf, p.3' -> ('paper.pdf', 3)"""
    raw = raw.strip().lstrip("*").rstrip("*")

    link_match = re.match(r"\[([^\]]+)\]\([^)]*\)(.*)$", raw)
    if link_match:
        raw = f"{link_match.group(1)}{link_match.group(2)}"

    raw = re.split(r"\s+[-–-]\s+", raw, maxsplit=1)[0].strip()

    page_match = re.search(r",\s*p\.?\s*(\d+)\b", raw)
    if page_match:
        filename = raw[:page_match.start()].strip()
        page = int(page_match.group(1))
    else:
        filename = raw
        page = None
    return filename, page


def parse_wiki_links(content: str, current_dir: str) -> list[str]:
    """提取内部 wiki 链接路径，按 current_dir 做相对路径解析。

    排除：外部(http/#/mailto:/data:)、图片(.png/.jpg 等)、图片语法 ![...](...)
    解析规则（参考 LLM Wiki parse_wiki_links）：
    - /wiki/xxx -> xxx
    - ./xxx -> current_dir + xxx
    - ../xxx -> 逐级 pop 父目录
    - 裸名 xxx -> current_dir + xxx
    """
    paths: list[str] = []
    for match in _WIKI_LINK_RE.finditer(content):
        href = match.group(1)
        if href.startswith(("http", "#", "mailto:", "data:")):
            continue
        if re.search(r"\.(png|jpg|jpeg|gif|webp|svg)$", href, re.IGNORECASE):
            continue

        if href.startswith("/wiki/"):
            resolved = href.replace("/wiki/", "", 1)
        elif href.startswith("./"):
            resolved = (current_dir + href[2:]) if current_dir else href[2:]
        elif href.startswith("../"):
            parts = (current_dir.rstrip("/") + "/" + href).split("/")
            resolved_parts: list[str] = []
            for p in parts:
                if p == "..":
                    if resolved_parts:
                        resolved_parts.pop()
                elif p and p != ".":
                    resolved_parts.append(p)
            resolved = "/".join(resolved_parts)
        elif "/" not in href:
            resolved = (current_dir + href) if current_dir else href
        else:
            resolved = href

        if resolved:
            paths.append(resolved)
    return paths


def build_lookup_maps(
    all_docs: list[dict],
) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    """构建 3 层查找映射：filename(+title) / basename(去扩展名) / wiki 相对路径。

    setdefault 保证首个胜出（避免后入覆盖）。
    """
    filename_to_doc: dict[str, dict] = {}
    base_to_doc: dict[str, dict] = {}
    wiki_path_to_doc: dict[str, dict] = {}

    for doc in all_docs:
        fn_lower = doc["filename"].lower()
        filename_to_doc.setdefault(fn_lower, doc)
        if doc.get("title"):
            title_lower = doc["title"].lower()
            filename_to_doc.setdefault(title_lower, doc)

        base = _SOURCE_EXT_RE.sub("", fn_lower)
        base_to_doc.setdefault(base, doc)

        path = doc.get("path", "")
        if path.startswith("/wiki/"):
            relative = (path + doc["filename"]).replace("/wiki/", "", 1)
            wiki_path_to_doc.setdefault(relative.lower(), doc)

    return filename_to_doc, base_to_doc, wiki_path_to_doc


def extract_references(
    content: str,
    doc_id: str,
    wiki_dir: str,
    filename_to_doc: dict[str, dict],
    base_to_doc: dict[str, dict],
    wiki_path_to_doc: dict[str, dict],
) -> list[dict]:
    """解析内容，返回引用边列表。

    每条边: {"target_id": str, "type": "cites"|"links_to", "page": int|None}
    排除自引用 + 去重（seen set）。
    """
    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()

    # 脚注引用 -> cites
    for match in _CITATION_RE.finditer(content):
        filename, page = parse_citation_filename(match.group(1))
        fn_lower = filename.lower()
        target = filename_to_doc.get(fn_lower)
        if not target:
            base = _SOURCE_EXT_RE.sub("", fn_lower)
            target = base_to_doc.get(base)
        if target and str(target["id"]) != str(doc_id):
            key = (str(target["id"]), "cites")
            if key not in seen:
                seen.add(key)
                edges.append({"target_id": str(target["id"]), "type": "cites", "page": page})

    # wiki 交叉链接 -> links_to
    for link_path in parse_wiki_links(content, wiki_dir):
        target = wiki_path_to_doc.get(link_path.lower())
        if not target:
            target = wiki_path_to_doc.get(link_path.lower() + ".md")
        if not target:
            basename = link_path.split("/")[-1].lower()
            target = wiki_path_to_doc.get(basename)
        if target and str(target["id"]) != str(doc_id):
            key = (str(target["id"]), "links_to")
            if key not in seen:
                seen.add(key)
                edges.append({"target_id": str(target["id"]), "type": "links_to", "page": None})

    return edges
