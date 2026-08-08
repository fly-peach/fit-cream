"""
字幕解析模块

把 B 站字幕 JSON 的 cues 数组转成可读文本。
支持时间戳（HH:MM:SS）与纯文本两种模式。
"""


def _fmt_ts(seconds: float) -> str:
    """字幕时间戳 -> HH:MM:SS"""
    secs = int(seconds)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def cues_to_text(
    cues: list[dict],
    need_timestamps: bool = False,
    max_chars: int = 4000,
) -> tuple[str, int]:
    """把 cues 数组转成文本。

    Args:
        cues: 字幕条目列表（每项含 from/to/content）
        need_timestamps: 是否保留时间戳前缀
        max_chars: 截断上限（字符）

    Returns:
        (文本, 完整文本长度)
    """
    lines: list[str] = []
    full_len = 0
    for cue in cues:
        content = str(cue.get("content") or "").strip()
        if not content:
            continue
        if need_timestamps:
            ts = _fmt_ts(float(cue.get("from") or 0))
            line = f"[{ts}] {content}"
        else:
            line = content
        lines.append(line)
        full_len += len(line) + 1  # +1 换行

    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[:max_chars], len(text)
    return text, len(text)


def cues_count(cues: list[dict]) -> int:
    return len(cues)