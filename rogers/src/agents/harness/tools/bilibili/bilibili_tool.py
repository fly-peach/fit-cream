"""
B 站视频直读工具

Agent 拿到 B 站链接后，读取视频字幕/转写文本用于回答。
- 字幕优先（view → dm/view → subtitle_url），零下载
- 无字幕自动降级 ASR（yt-dlp + faster-whisper）
- 按 max_chars 截断注入上下文，避免超长撑爆
- 本地磁盘缓存（按 source+bvid），二次调用秒回
"""
import logging
from typing import Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.tools._common import error_response
from src.agents.harness.tools.bilibili.asr import ASRConfig, transcribe
from src.agents.harness.tools.bilibili.cache import BilibiliCache
from src.agents.harness.tools.bilibili.fetcher import (
    BilibiliFetcher,
    FetcherConfig,
    resolve_and_fetch,
)
from src.agents.harness.tools.bilibili.subtitle import cues_count, cues_to_text

logger = logging.getLogger("fitcream.bilibili")


class ReadBilibiliVideoInput(BaseModel):
    """读取 B 站视频内容的输入参数"""

    url: str = Field(description="B 站视频链接，支持完整 URL、BV 号、b23.tv 短链")
    mode: Literal["auto", "subtitle", "asr"] = Field(
        default="auto",
        description="auto=字幕优先、无字幕转 ASR；subtitle=仅字幕；asr=强制转写",
    )
    max_chars: int = Field(
        default=4000,
        ge=500,
        le=20000,
        description="注入上下文的文本上限（字符），防止超长内容撑爆上下文",
    )
    need_timestamps: bool = Field(
        default=False,
        description="是否保留字幕时间戳前缀（便于精确引用），仅字幕模式生效",
    )


def _build_message(source: str, title: str, truncated: bool, cues: int) -> str:
    if source == "subtitle":
        base = f"已读取视频《{title}》的字幕内容"
    elif source == "asr":
        base = f"已通过语音转写读取视频《{title}》的内容"
    else:
        base = f"视频《{title}》无可用文本内容"
    if truncated:
        base += "（内容较长，已截断，可再次调用读取更多）"
    if source != "none" and cues:
        base += f"（字幕 {cues} 条）"
    return base


@tool(args_schema=ReadBilibiliVideoInput)
async def read_bilibili_video(
    url: str,
    mode: str = "auto",
    max_chars: int = 4000,
    need_timestamps: bool = False,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    读取 B 站视频的字幕或语音转写文本。

    使用场景：
    - 用户分享 B 站视频链接（BV 号 / 完整 URL / b23.tv 短链），需要了解视频讲什么
    - 用户问"这个视频讲了什么？帮我总结一下"、"视频里的训练动作是什么"
    - 用户需要基于某个 B 站健身/科普视频的内容回答问题时

    自动优先读取视频字幕（快、准）；无字幕时自动降级为语音转写（较慢，分钟级）。
    长视频文本会被截断，如需完整内容可再次调用并调大 max_chars（有缓存，秒回）。

    Returns:
        包含视频元信息与文本内容的字典
    """
    try:
        from app.config import settings

        fetcher_config = FetcherConfig(
            cookie=settings.BILIBILI_COOKIE or "",
            timeout=settings.BILIBILI_REQUEST_TIMEOUT,
            max_retries=settings.BILIBILI_MAX_RETRIES,
        )

        # 1. 解析 URL → 元信息 + 字幕 URL（内部处理短链展开 / BV 号识别）
        info, subtitle_url, bvid = await resolve_and_fetch(url, fetcher_config)

        # 2. 分支：强制 ASR / 字幕优先 / 纯字幕
        if mode == "asr":
            return await _run_asr(info, bvid, max_chars, settings)
        if subtitle_url:
            return await _run_subtitle(info, subtitle_url, bvid, max_chars, need_timestamps, settings)
        if mode == "auto":
            return await _run_asr(info, bvid, max_chars, settings)
        # mode = subtitle 且无字幕
        return {
            "success": True,
            "video": {**info.to_dict(), "source": "none", "sub_lan": None},
            "text": "",
            "truncated": False,
            "full_text_len": 0,
            "cues_count": 0,
            "message": f"视频《{info.title}》无字幕。可尝试用 asr 模式进行语音转写。",
        }
    except Exception as e:  # noqa: BLE001 - 与现有工具一致，统一走 error_response
        return error_response(e)


async def _run_subtitle(
    info,
    subtitle_url: str,
    bvid: str,
    max_chars: int,
    need_timestamps: bool,
    settings,
) -> dict:
    """字幕直读流程（带缓存）。缓存存完整文本，读取时按 max_chars 截断，支持二次读取更大 max_chars。"""
    cache = BilibiliCache(settings.BILIBILI_CACHE_DIR or "")
    cached = cache.get("subtitle", bvid)
    if cached:
        full = str(cached.get("text") or "")
        cues = int(cached.get("cues_count") or 0)
    else:
        fetcher = BilibiliFetcher(FetcherConfig(cookie=settings.BILIBILI_COOKIE or ""))
        body = await fetcher.fetch_subtitle_body(subtitle_url)
        full, _ = cues_to_text(body, need_timestamps=need_timestamps, max_chars=10**9)
        cues = cues_count(body)
        cache.set("subtitle", bvid, {"text": full, "cues_count": cues})
    truncated = len(full) > max_chars
    text = full[:max_chars] if truncated else full
    return {
        "success": True,
        "video": {**info.to_dict(), "source": "subtitle", "sub_lan": "ai-zh"},
        "text": text,
        "truncated": truncated,
        "full_text_len": len(full),
        "cues_count": cues,
        "message": _build_message("subtitle", info.title, truncated, cues),
    }


async def _run_asr(info, bvid: str, max_chars: int, settings) -> dict:
    """ASR 转写流程（带缓存）。缓存存完整文本，读取时按 max_chars 截断。"""
    cache = BilibiliCache(settings.BILIBILI_CACHE_DIR or "")
    cached = cache.get("asr", bvid)
    if cached:
        full = str(cached.get("text") or "")
    else:
        asr_cfg = ASRConfig(
            model=settings.BILIBILI_ASR_MODEL,
            device=settings.BILIBILI_ASR_DEVICE,
            compute_type=settings.BILIBILI_ASR_COMPUTE_TYPE,
            vad_filter=settings.BILIBILI_ASR_VAD,
            enabled=settings.BILIBILI_ASR_ENABLED,
        )
        video_url = f"https://www.bilibili.com/video/{bvid}"
        full = await transcribe(video_url, asr_cfg)
        if not full:
            return {
                "success": True,
                "video": {**info.to_dict(), "source": "none", "sub_lan": None},
                "text": "",
                "truncated": False,
                "full_text_len": 0,
                "cues_count": 0,
                "message": f"视频《{info.title}》转写无有效内容（可能为无声短视频）。",
            }
        cache.set("asr", bvid, {"text": full})
    truncated = len(full) > max_chars
    text = full[:max_chars] if truncated else full
    return {
        "success": True,
        "video": {**info.to_dict(), "source": "asr", "sub_lan": None},
        "text": text,
        "truncated": truncated,
        "full_text_len": len(full),
        "cues_count": 1,
        "message": _build_message("asr", info.title, truncated, 1),
    }