"""
本地缓存模块

按 (mode, bvid) 缓存完整文本 + 元信息 + source，避免重复抓取触发风控、
避免重复转写烧 CPU。TTL：字幕 30 天，ASR 7 天。
"""
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("fitcream.bilibili")

_SUBTITLE_TTL = 30 * 24 * 3600   # 30 天
_ASR_TTL = 7 * 24 * 3600         # 7 天


def _ttl_for(source: str) -> int:
    return _ASR_TTL if source == "asr" else _SUBTITLE_TTL


class BilibiliCache:
    """磁盘 JSON 缓存，key = <source>_<bvid>.json"""

    def __init__(self, cache_dir: str = ""):
        self.dir = Path(cache_dir) if cache_dir else None

    def _ensure_dir(self) -> None:
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, source: str, bvid: str) -> Path:
        return self.dir / f"{source}_{bvid}.json"

    def get(self, source: str, bvid: str) -> dict | None:
        """命中且未过期返回缓存 dict，否则 None。"""
        if not self.dir:
            return None
        path = self._path(source, bvid)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            logger.warning("读取缓存失败，忽略: %s (%s)", path, e)
            return None
        if time.time() - data.get("cached_at", 0) > _ttl_for(source):
            return None
        return data

    def set(self, source: str, bvid: str, data: dict) -> None:
        """写入缓存，带 cached_at 时间戳。"""
        if not self.dir:
            return
        try:
            self._ensure_dir()
            payload = dict(data)
            payload["cached_at"] = time.time()
            with open(self._path(source, bvid), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except OSError as e:
            logger.warning("写入缓存失败: %s (%s)", self._path(source, bvid), e)


def cache_dir_from_settings(cache_dir: str | None) -> str | None:
    """根据配置返回缓存目录（空则禁用缓存）。"""
    if not cache_dir:
        return None
    return cache_dir