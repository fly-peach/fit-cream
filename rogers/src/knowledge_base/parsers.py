"""
文档解析器（纯逻辑，零 DB 依赖）

基于 unstructured 库实现多格式文档解析：
- PDF / Word / PPT / HTML / CSV / Markdown / 纯文本 -> 结构化元素（Title/NarrativeText/ListItem/Table...）
- Markdown 额外解析 YAML frontmatter（unstructured 不处理 frontmatter，由本模块负责）

设计：
- parse_document(): 统一入口，按 content_type 调用 unstructured.partition.auto
- 元素保留页码/类型信息，供 chunker 做元素感知分块
- 元素可重建为 Markdown（content 字段），兼顾全文存储与人类可读

参考 LLM Wiki 的 converter 架构（PDF/Office 文本抽取层）。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Optional

import yaml

logger = logging.getLogger("fitcream")

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.+?\n)---[ \t]*\n", re.DOTALL)
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# 文件扩展名 -> unstructured content_type
CONTENT_TYPE_MAP: dict[str, str] = {
    ".md": "text/plain",
    ".markdown": "text/plain",
    ".txt": "text/plain",
    ".rst": "text/plain",
    ".html": "text/html",
    ".htm": "text/html",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "application/xml",
    ".eml": "message/rfc822",
    ".epub": "application/epub+zip",
}

# 视为 Markdown 的扩展名（需 frontmatter 预处理）
_MARKDOWN_EXTS = {".md", ".markdown"}


@dataclass
class ParsedElement:
    """结构化文档元素（unstructured Element 的精简表示）"""
    type: str  # Title / NarrativeText / ListItem / Table / Header / Footer / Image ...
    text: str
    page: Optional[int] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """解析后的文档（含 Markdown 重建 + 结构化元素）"""
    title: str
    content: str  # Markdown 文本（供存储 + 全文搜索）
    elements: list[ParsedElement] = field(default_factory=list)
    page_count: int = 0
    metadata: dict = field(default_factory=dict)


# ============================================================
# Markdown frontmatter 解析（unstructured 不处理 frontmatter，本模块负责）
# ============================================================


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 Markdown 开头的 YAML frontmatter。

    返回 (metadata, content_without_frontmatter)。
    无 frontmatter 时 metadata={}, content=原文。
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1))
    except Exception:
        return {}, text
    if not isinstance(meta, dict):
        return {}, text
    return meta, text[m.end():]


def extract_title(metadata: dict, content: str, filename: str = "") -> str:
    """提取标题，优先级: frontmatter.title > 第一个 # 标题 > 文件名"""
    if metadata.get("title"):
        return str(metadata["title"]).strip()

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()

    if filename:
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        return stem.replace("-", " ").replace("_", " ").strip()

    return "未命名文档"


def extract_tags(metadata: dict) -> list[str]:
    """从 frontmatter 提取 tags 列表"""
    tags = metadata.get("tags", [])
    if isinstance(tags, list):
        return [str(t) for t in tags if t is not None]
    if isinstance(tags, str):
        return [tags]
    return []


# ============================================================
# unstructured 多格式文档解析
# ============================================================


def detect_content_type(filename: str) -> str:
    """根据文件扩展名推断 unstructured content_type"""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return CONTENT_TYPE_MAP.get(ext, "text/plain")


def _strip_frontmatter_if_markdown(content_bytes: bytes, filename: str) -> tuple[bytes, dict]:
    """若是 Markdown，先剥离 frontmatter，返回 (body_bytes, frontmatter_meta)"""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _MARKDOWN_EXTS:
        return content_bytes, {}

    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return content_bytes, {}

    meta, body = parse_frontmatter(text)
    if meta:
        return body.encode("utf-8"), meta
    return content_bytes, {}


# 未默认安装 extras 的格式 -> 报错时提示安装
_HEAVY_EXTRAS: dict[str, str] = {
    "application/pdf": 'unstructured[pdf]',
    "application/msword": 'unstructured[doc]',
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": 'unstructured[docx]',
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": 'unstructured[pptx]',
    "application/vnd.ms-powerpoint": 'unstructured[ppt]',
}


class UnsupportedFormatError(Exception):
    """上传了未安装解析依赖的格式（如 PDF/Word/PPT）。"""

    def __init__(self, content_type: str):
        extra = _HEAVY_EXTRAS.get(content_type, "对应 extras")
        super().__init__(
            f"暂不支持解析 {content_type}，请先安装依赖：pip install \"{extra}\""
        )
        self.content_type = content_type


def _partition(content_bytes: bytes, content_type: str,
               languages: Optional[list[str]] = None, strategy: str = "auto") -> list:
    """调用 unstructured.partition.auto 解析文档元素。

    已声明依赖：md / xlsx / csv / html / 纯文本（开箱即用）。
    PDF / Word / PPT 未默认安装 extras，也可能缺系统依赖（poppler/LibreOffice），
    对这类「重格式」尝试解析时捕获任意失败，转为清晰的 UnsupportedFormatError。
    """
    from unstructured.partition import auto

    kwargs: dict = {"strategy": strategy}
    if languages:
        kwargs["languages"] = languages

    is_heavy = content_type in _HEAVY_EXTRAS
    try:
        return auto.partition(
            file=BytesIO(content_bytes),
            content_type=content_type,
            **kwargs,
        )
    except ImportError:
        raise UnsupportedFormatError(content_type)
    except Exception:
        if is_heavy:
            raise UnsupportedFormatError(content_type)
        raise


def _to_parsed_elements(raw_elements: list) -> list[ParsedElement]:
    """把 unstructured Element 列表转为 ParsedElement 列表"""
    result = []
    for e in raw_elements:
        text = (e.text or "").strip()
        if not text:
            continue
        page = getattr(e.metadata, "page_number", None)
        meta = {}
        for attr in ("category_depth", "link_urls", "image_path", "detection_class_prob"):
            val = getattr(e.metadata, attr, None)
            if val is not None:
                meta[attr] = val
        result.append(ParsedElement(
            type=type(e).__name__,
            text=text,
            page=page,
            metadata=meta,
        ))
    return result


def _title_from_elements(elements: list[ParsedElement], filename: str = "") -> str:
    """从首个 Title 元素提取标题"""
    for e in elements:
        if e.type == "Title" and e.text.strip():
            text = e.text.strip()
            # Markdown 文本被解析时可能保留 # 前缀
            m = _HEADER_RE.match(text)
            if m:
                return m.group(2).strip()
            return text
    if filename:
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        return stem.replace("-", " ").replace("_", " ").strip()
    return "未命名文档"


def elements_to_markdown(elements: list[ParsedElement]) -> str:
    """将 ParsedElement 列表重建为 Markdown 文本（供存储 + 全文搜索）"""
    lines: list[str] = []
    for e in elements:
        text = e.text
        if e.type == "Title":
            m = _HEADER_RE.match(text)
            lines.append(text if m else f"# {text}")
        elif e.type == "ListItem":
            lines.append(f"- {text}")
        elif e.type == "Table":
            lines.append(f"```\n{text}\n```")
        elif e.type in ("Header", "Footer", "PageBreak", "PageNumber"):
            continue
        else:
            lines.append(text)
        lines.append("")
    return "\n".join(lines).strip()


def parse_document(
    content: bytes | str,
    filename: str,
    content_type: Optional[str] = None,
    languages: Optional[list[str]] = None,
    strategy: str = "auto",
) -> ParsedDocument:
    """使用 unstructured 解析任意格式文档为结构化元素。

    流程:
    1. content_type 推断（显式 > 扩展名映射）
    2. Markdown 先剥离 frontmatter
    3. unstructured.partition.auto 提取元素（缺失依赖降级 text/plain）
    4. 转 ParsedElement + 重建 Markdown + 提取标题

    Args:
        content: 文档字节或文本
        filename: 文件名（用于扩展名推断 + 标题兜底）
        content_type: 显式 MIME 类型，不填则按扩展名推断
        languages: 语言提示（如 ["zh","en"]），影响分词/OCR
        strategy: unstructured 解析策略（auto/fast/hi_res）

    Returns:
        ParsedDocument（title + content + elements + page_count）
    """
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content

    ct = content_type or detect_content_type(filename)
    fm_meta, body_bytes = {}, content_bytes

    # Markdown：先剥离 frontmatter
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _MARKDOWN_EXTS:
        body_bytes, fm_meta = _strip_frontmatter_if_markdown(content_bytes, filename)
        ct = "text/plain"

    raw_elements = _partition(body_bytes, ct, languages, strategy)
    elements = _to_parsed_elements(raw_elements)

    # 标题：frontmatter > 首个 Title 元素 > 文件名
    title = ""
    if fm_meta.get("title"):
        title = str(fm_meta["title"]).strip()
    else:
        title = _title_from_elements(elements, filename)

    # 页码统计
    page_count = max(
        (e.page for e in elements if e.page is not None), default=0
    )

    # 重建 Markdown（Markdown 原文优先保留 frontmatter）
    if ext in _MARKDOWN_EXTS:
        try:
            content_md = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content_md = elements_to_markdown(elements)
    else:
        content_md = elements_to_markdown(elements)

    return ParsedDocument(
        title=title,
        content=content_md,
        elements=elements,
        page_count=page_count,
        metadata=fm_meta,
    )
