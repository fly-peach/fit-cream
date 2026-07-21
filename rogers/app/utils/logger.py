"""
日志配置模块

根据 settings.LOG_FORMAT 选择输出格式：
- "text": 人类可读的文本格式（开发环境）
- "json": 结构化 JSON 格式（生产环境，便于日志采集）

在 FastAPI lifespan startup 中调用 setup_logging() 初始化。
"""
import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """配置日志"""
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
        if settings.LOG_FORMAT == "text"
        else '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "line": %(lineno)d, "message": "%(message)s"}'
    )

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # 降低第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)