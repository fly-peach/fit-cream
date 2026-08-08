"""
B 站 API 抓取模块

封装 B 站开放接口（view / dm/view / subtitle_url），负责：
- URL / BV 号解析（含 b23.tv 短链重定向展开）
- 视频元信息抓取（view API）
- 字幕轨获取（dm/view 返回 ai-zh subtitle_url）
- 字幕 JSON 拉取

所有请求带 User-Agent + Referer，并对 -412/-799 风控码做指数退避重试。
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field

import httpx
from utils.exceptions import BusinessException

logger = logging.getLogger("fitcream.bilibili")

# b23.tv 短链 / 完整视频 URL / 裸 BV 号
_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_SHORT_URL_RE = re.compile(r"(?:https?://)?b23\.tv/[0-9A-Za-z]+")
_VIDEO_URL_RE = re.compile(r"(?:https?://)?(?:www\.|m\.)?bilibili\.com/video/(BV[0-9A-Za-z]{10})")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}

# B 站风控响应码：请求频控/风控，等待后重试
_RISK_CODES = {-412, -799, -352}
_DEFAULT_TIMEOUT = 15.0
_MAX_RETRIES = 4


def parse_bvid(url: str) -> str | None:
    """从 URL / 裸 BV 号 / 短链文本中提取 BV 号。无法解析返回 None。"""
    if not url:
        return None
    url = url.strip()
    m = _BV_RE.search(url)
    return m.group(1) if m else None


def is_short_link(url: str) -> bool:
    return bool(_SHORT_URL_RE.match(url.strip()))


@dataclass
class VideoInfo:
    """视频元信息（view API 子集）"""
    bvid: str
    cid: int
    title: str
    duration: int
    play: int

    def to_dict(self) -> dict:
        return {
            "bvid": self.bvid,
            "title": self.title,
            "duration": self.duration,
            "play": self.play,
            "url": f"https://www.bilibili.com/video/{self.bvid}",
        }


@dataclass
class FetcherConfig:
    cookie: str = ""
    timeout: float = _DEFAULT_TIMEOUT
    max_retries: int = _MAX_RETRIES
    risk_wait: float = 2.0
    _retry_count: int = field(default=0, init=False, repr=False)


class BilibiliFetcher:
    """B 站抓取器：带 UA/Referer/cookie 与风控退避重试。"""

    def __init__(self, config: FetcherConfig | None = None):
        self.config = config or FetcherConfig()

    def _headers(self) -> dict:
        headers = dict(_HEADERS)
        if self.config.cookie:
            headers["Cookie"] = self.config.cookie
        return headers

    async def _request_json(self, client: httpx.AsyncClient, url: str) -> dict:
        """GET JSON，处理伪造响应与风控重试。"""
        for attempt in range(self.config.max_retries):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                payload = resp.json()
            except (httpx.HTTPError, ValueError) as e:
                logger.warning("B站请求失败(第%s次): %s %s", attempt + 1, url, e)
                await self._backoff(attempt)
                continue

            code = payload.get("code", 0)
            if code == 0:
                return payload
            if code in _RISK_CODES:
                logger.warning("B站风控(code=%s) 第%s次，等待后重试: %s", code, attempt + 1, url)
                await self._backoff(attempt + 1)
                continue
            # 其余业务码（如 -404 视频不存在）直接抛业务异常
            raise BusinessException(message=f"B站接口返回错误：{payload.get('message', code)}", code=str(code))

        raise BusinessException(
            message=f"B站接口请求失败（已重试{self.config.max_retries}次）",
            code="BILI_FETCH_TIMEOUT",
        )

    async def _backoff(self, attempt: int) -> None:
        # 指数退避：base * 2^(attempt-1)，封顶 30 秒
        wait = min(self.config.risk_wait * (2 ** (attempt - 1)), 30.0)
        await asyncio.sleep(wait)

    async def resolve_url(self, url: str) -> str:
        """解析输入成标准视频 URL（b23.tv 短链跟随重定向）。"""
        if not is_short_link(url):
            # 已是完整 URL 或裸 BV 号，无需展开
            return url
        async with httpx.AsyncClient(follow_redirects=True, timeout=self.config.timeout) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return str(resp.url)

    async def get_video_info(self, bvid: str) -> VideoInfo:
        """view API：元信息 + cid。"""
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            payload = await self._request_json(client, url)
        data = payload.get("data") or {}
        stat = data.get("stat") or {}
        title = data.get("title") or ""
        cid = data.get("cid")
        if not cid:
            raise BusinessException(message=f"视频《{title or bvid}》无法获取 cid（可能不存在或仅限会员）", code="BILI_NO_CID")
        return VideoInfo(
            bvid=bvid,
            cid=int(cid),
            title=title,
            duration=int(data.get("duration") or 0),
            play=int(stat.get("view") or 0),
        )

    async def get_subtitle_url(self, cid: int) -> str | None:
        """dm/view API：返回字幕轨 subtitle_url；无字幕返回 None。"""
        url = f"https://api.bilibili.com/x/v2/dm/view?oid={cid}&type=1"
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            payload = await self._request_json(client, url)
        sub = (payload.get("data") or {}).get("subtitle") or {}
        subtitle_url = sub.get("subtitle_url")
        if not subtitle_url:
            return None
        if subtitle_url.startswith("//"):
            subtitle_url = "https:" + subtitle_url
        return subtitle_url

    async def fetch_subtitle_body(self, subtitle_url: str) -> list[dict]:
        """拉取字幕 JSON，返回 cues 数组（每项含 from/to/content）。"""
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            resp = await client.get(subtitle_url, headers=self._headers())
            resp.raise_for_status()
            payload = resp.json()
        body = payload.get("body") or []
        return body


def pick_subtitle_lan(subtitle_url: str, lan: str | None = None) -> str:
    """返回字幕语言标识（用于输出 source 相关展示）。"""
    return lan or "ai-zh"


async def resolve_and_fetch(url: str, config: FetcherConfig | None = None) -> tuple[VideoInfo, str | None, str]:
    """一站式：解析 URL → 元信息 → 字幕 URL → 返回 (info, subtitle_url, resolved_url)。

    Args:
        url: 用户提供的链接/BV 号/短链
        config: 抓取配置

    Returns:
        (VideoInfo, subtitle_url_or_None, 展开后的标准 URL)
    """
    fetcher = BilibiliFetcher(config)
    resolved = await fetcher.resolve_url(url)
    bvid = parse_bvid(resolved)
    if not bvid:
        raise BusinessException(message="无法解析 B 站视频链接，请提供有效的 BV 号或视频 URL", code="BILI_BAD_URL")
    info = await fetcher.get_video_info(bvid)
    subtitle_url = await fetcher.get_subtitle_url(info.cid)
    return info, subtitle_url, bvid