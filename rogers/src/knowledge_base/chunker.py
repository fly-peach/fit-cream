"""
文本分块器（纯逻辑，零 DB 依赖）

参考 LLM Wiki api/services/chunker.py，将文档按语义边界切分为适合搜索的块。
改进：CJK 感知的 token 估算（中文 ~1.5 字/token，英文 ~4 字符/token）。

两种分块模式：
- chunk_text(content): 按纯文本/Markdown 的标题段落边界分块
- chunk_elements(elements): 按 unstructured 结构化元素分块，保留页码 + 元素类型面包屑
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


CHUNK_SIZE = 512
CHUNK_OVERLAP = 128
MIN_CHUNK_TOKENS = 32
MAX_CHUNK_CHARS = 10_000  # 与 DB CHECK 约束对齐

SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+")
HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# unstructured 元素类型 -> 是否为标题（用于构建面包屑）
_TITLE_TYPES = frozenset({"Title", "Header", "SectionHeader"})
# 忽略的元素类型（不进入分块内容）
_SKIP_TYPES = frozenset({"Footer", "PageBreak", "PageNumber"})


@dataclass
class ChunkConfig:
    chunk_size_tokens: int = CHUNK_SIZE
    chunk_overlap_tokens: int = CHUNK_OVERLAP
    min_chunk_tokens: int = MIN_CHUNK_TOKENS
    max_chunk_chars: int = MAX_CHUNK_CHARS


@dataclass
class Chunk:
    index: int
    content: str
    start_char: int = 0
    token_count: int = 1
    header_breadcrumb: str = ""
    page: int | None = None


def estimate_tokens(text: str) -> int:
    """CJK 感知的 token 估算。

    中文 ~1.5 字/token，英文 ~4 字符/token。
    优于 LLM Wiki 源码的 len//4（仅适用英文）。
    """
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other = len(text) - cjk
    return max(1, round(cjk / 1.5) + other // 4)


def chunk_text(content: str, config: ChunkConfig | None = None) -> list[Chunk]:
    """将文本按标题/段落边界分块。

    流程：按双换行分段 -> 追踪 header 栈构建面包屑
         -> 累积到目标大小后切分（块级重叠）-> 超长兜底拆分。
    """
    if not content or not content.strip():
        return []

    cfg = config or ChunkConfig()
    paragraphs = _split_paragraphs(content)

    header_stack: list[tuple[int, str]] = []
    chunks: list[Chunk] = []
    current_blocks: list[str] = []
    current_tokens = 0
    current_start = 0
    char_pos = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        header_match = HEADER_RE.match(para)
        if header_match:
            level = len(header_match.group(1))
            heading = header_match.group(2).strip()
            header_stack = [(l, t) for l, t in header_stack if l < level]
            header_stack.append((level, heading))

        if current_tokens + para_tokens > cfg.chunk_size_tokens and current_blocks:
            chunk_str = "\n\n".join(current_blocks)
            if estimate_tokens(chunk_str) >= cfg.min_chunk_tokens:
                breadcrumb = " > ".join(t for _, t in header_stack)
                chunks.append(Chunk(
                    index=len(chunks),
                    content=chunk_str,
                    start_char=current_start,
                    token_count=estimate_tokens(chunk_str),
                    header_breadcrumb=breadcrumb,
                ))

            overlap_blocks, overlap_tokens = _get_overlap(
                current_blocks, cfg.chunk_overlap_tokens
            )
            current_blocks = overlap_blocks
            current_tokens = overlap_tokens
            current_start = char_pos - sum(len(b) + 2 for b in overlap_blocks)

        current_blocks.append(para)
        current_tokens += para_tokens
        char_pos += len(para) + 2

    if current_blocks:
        chunk_str = "\n\n".join(current_blocks)
        if estimate_tokens(chunk_str) >= cfg.min_chunk_tokens:
            breadcrumb = " > ".join(t for _, t in header_stack)
            chunks.append(Chunk(
                index=len(chunks),
                content=chunk_str,
                start_char=current_start,
                token_count=estimate_tokens(chunk_str),
                header_breadcrumb=breadcrumb,
            ))

    return _enforce_max_chars(chunks, cfg)


def chunk_elements(
    elements: list[dict] | list, config: ChunkConfig | None = None
) -> list[Chunk]:
    """按 unstructured 结构化元素分块，保留页码 + 标题面包屑。

    elements 为 ParsedElement 字典列表（含 type/text/page）或 ParsedElement 对象。
    流程：标题元素更新面包屑栈 -> 非忽略元素累积
         -> 达到目标大小切分（块级重叠）-> 超长兜底拆分。
    """
    if not elements:
        return []

    cfg = config or ChunkConfig()
    header_stack: list[str] = []
    chunks: list[Chunk] = []
    current_blocks: list[str] = []
    current_tokens = 0
    current_page: int | None = None

    def _get(el, key, default=None):
        return el[key] if isinstance(el, dict) else getattr(el, key, default)

    def _flush(start_index_offset: int = 0):
        if not current_blocks:
            return
        text = "\n\n".join(current_blocks)
        if estimate_tokens(text) >= cfg.min_chunk_tokens:
            breadcrumb = " > ".join(header_stack)
            chunks.append(Chunk(
                index=len(chunks),
                content=text,
                start_char=start_index_offset,
                token_count=estimate_tokens(text),
                header_breadcrumb=breadcrumb,
                page=current_page,
            ))

    char_offset = 0
    for el in elements:
        etype = _get(el, "type", "")
        etext = _get(el, "text", "")
        epage = _get(el, "page", None)

        if etype in _SKIP_TYPES or not etext or not etext.strip():
            char_offset += len(etext) + 2
            continue

        # 标题元素：更新面包屑栈（不进块内容，或作为块内首行）
        if etype in _TITLE_TYPES:
            heading = etext.lstrip("#").strip()
            if heading:
                header_stack = [h for h in header_stack]
                header_stack.append(heading)
            # 标题行也加入块内容（保持上下文）
            block = etext if etext.startswith("#") else f"# {etext}"
        else:
            block = etext

        block_tokens = estimate_tokens(block)

        if current_tokens + block_tokens > cfg.chunk_size_tokens and current_blocks:
            _flush(char_offset - sum(len(b) + 2 for b in current_blocks))
            overlap_blocks, overlap_tokens = _get_overlap(
                current_blocks, cfg.chunk_overlap_tokens
            )
            current_blocks = overlap_blocks
            current_tokens = overlap_tokens

        current_blocks.append(block)
        current_tokens += block_tokens
        if epage is not None:
            current_page = epage
        char_offset += len(block) + 2

    _flush(char_offset - sum(len(b) + 2 for b in current_blocks) if current_blocks else 0)
    return _enforce_max_chars(chunks, cfg)


def _enforce_max_chars(chunks: list[Chunk], cfg: ChunkConfig) -> list[Chunk]:
    """拆分超过 max_chunk_chars 的块（句子边界 -> 硬截断兜底）"""
    if not any(len(c.content) > cfg.max_chunk_chars for c in chunks):
        return chunks

    result: list[Chunk] = []
    for c in chunks:
        if len(c.content) <= cfg.max_chunk_chars:
            result.append(Chunk(
                index=len(result), content=c.content,
                start_char=c.start_char, token_count=c.token_count,
                header_breadcrumb=c.header_breadcrumb, page=c.page,
            ))
            continue
        base = c.start_char or 0
        offset = 0
        for piece in _split_oversized(c.content, cfg.max_chunk_chars):
            result.append(Chunk(
                index=len(result), content=piece,
                start_char=base + offset,
                token_count=estimate_tokens(piece),
                header_breadcrumb=c.header_breadcrumb, page=c.page,
            ))
            offset += len(piece)
    return result


def _split_oversized(text: str, max_chars: int) -> list[str]:
    """按句子边界拆分超长段，无句子边界则硬截断"""
    parts = SENTENCE_RE.split(text)
    pieces: list[str] = []
    current = ""
    for part in parts:
        candidate = (current + " " + part).strip() if current else part
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                pieces.append(current)
            if len(part) <= max_chars:
                current = part
            else:
                for i in range(0, len(part), max_chars):
                    pieces.append(part[i:i + max_chars])
                current = ""
    if current:
        pieces.append(current)
    return pieces


def _split_paragraphs(text: str) -> list[str]:
    """按双换行拆分，保留段落结构"""
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def _get_overlap(blocks: list[str], target_tokens: int) -> tuple[list[str], int]:
    """取尾部块作为重叠（块级，非字符级）"""
    result: list[str] = []
    tokens = 0
    for block in reversed(blocks):
        block_tokens = estimate_tokens(block)
        if tokens + block_tokens > target_tokens:
            break
        result.insert(0, block)
        tokens += block_tokens
    return result, tokens
