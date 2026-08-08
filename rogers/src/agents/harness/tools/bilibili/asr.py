"""
ASR 兜底模块

无字幕视频走 yt-dlp 只下音频 + faster-whisper 转写。
依赖（yt_dlp / faster_whisper / ffmpeg）按需惰性导入，未安装时返回明确错误。
"""
import asyncio
import logging
import os
import tempfile

from utils.exceptions import BusinessException

logger = logging.getLogger("fitcream.bilibili")


class ASRConfig:
    def __init__(
        self,
        model: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        vad_filter: bool = True,
        enabled: bool = True,
    ):
        self.model = model
        self.device = device
        self.compute_type = compute_type
        self.vad_filter = vad_filter
        self.enabled = enabled


def _check_deps() -> None:
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        raise BusinessException(
            message="ASR 转写依赖未安装（yt-dlp），请在服务器安装后重试",
            code="BILI_ASR_DEPS",
        )
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        raise BusinessException(
            message="ASR 转写依赖未安装（faster-whisper），请在服务器安装后重试",
            code="BILI_ASR_DEPS",
        )


async def download_audio(url: str, timeout: int = 600) -> str:
    """用 yt-dlp 只下载音频（优先 m4a），返回本地文件路径。"""
    import yt_dlp

    tmpdir = tempfile.mkdtemp(prefix="bili_asr_")
    outtmpl = os.path.join(tmpdir, "audio.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": timeout,
        "retries": 3,
        "http_headers": {"Referer": "https://www.bilibili.com/"},
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        # 找到下载的音频文件
        for root, _dirs, files in os.walk(tmpdir):
            for fn in files:
                if fn.startswith("audio."):
                    return os.path.join(root, fn)
        raise BusinessException(message="yt-dlp 未下载到音频文件", code="BILI_ASR_NO_AUDIO")
    except BusinessException:
        raise
    except Exception as e:
        logger.exception("yt-dlp 下载失败")
        raise BusinessException(message=f"音频下载失败：{e}", code="BILI_ASR_DOWNLOAD")


def _transcribe_sync(audio_path: str, config: ASRConfig) -> str:
    """同步转写（封装 faster-whisper，避免阻塞理解其 API）。"""
    from faster_whisper import WhisperModel

    model = WhisperModel(config.model, device=config.device, compute_type=config.compute_type)
    segments, _info = model.transcribe(
        audio_path,
        vad_filter=config.vad_filter,
        language=None,  # 自动检测（B 站多为中文）
    )
    texts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
    return "\n".join(texts)


async def transcribe(url: str, config: ASRConfig | None = None) -> str:
    """下载音频并转写，返回文本。"""
    config = config or ASRConfig()
    if not config.enabled:
        raise BusinessException(
            message="ASR 转写已关闭（BILIBILI_ASR_ENABLED=false），无法转写无字幕视频",
            code="BILI_ASR_DISABLED",
        )
    _check_deps()
    audio_path = await download_audio(url)
    try:
        text = await asyncio.to_thread(_transcribe_sync, audio_path, config)
    finally:
        # 清理临时目录
        tmpdir = os.path.dirname(audio_path)
        try:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)
        except OSError as e:
            logger.warning("清理 ASR 临时目录失败: %s", e)
    return text.strip()