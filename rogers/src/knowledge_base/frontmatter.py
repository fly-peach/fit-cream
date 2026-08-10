"""
Markdown frontmatter 助手（纯逻辑，零 DB 依赖）

从 parsers.py 迁移出的轻量工具：解析 YAML frontmatter、提取标题/标签。
文件/多格式解析（unstructured）已移除，本模块仅保留 wiki 文档通用的元数据助手。
"""
from __future__ import annotations

import re

import yaml

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.+?\n)---[ \t]*\n", re.DOTALL)


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