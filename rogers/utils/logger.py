"""
日志配置模块

功能：
- 控制台输出（始终启用）
- 文件输出（按天轮转，保留 N 天，目录由 LOG_DIR 配置）
- 应用日志 → app.log（业务 + Agent 日志）
- 请求日志 → access.log（每次 HTTP 请求一行）
- 错误日志 → error.log（仅 ERROR 及以上）

在 FastAPI lifespan startup 中调用 setup_logging() 初始化。
"""
import contextvars
import json
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from app.config import settings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ============================================================
# 请求链路上下文（ContextVar）
# ------------------------------------------------------------
# request_id 在 HTTP 中间件层设置（dispatch 在 call_next 之前 set，context 经
# task 拷贝透传到路由与 Agent 日志）。user_id / thread_id 在路由层设置（认证
# 之后才可知）。三者均「存在则注入，不存在静默降级」--后台/定时任务无上下文
# 时日志不报错。
# ============================================================
_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "fitcream_request_id", default=None
)
_user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "fitcream_user_id", default=None
)
_thread_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "fitcream_thread_id", default=None
)


def get_request_id() -> Optional[str]:
    return _request_id_var.get()


def set_request_id(request_id: str):
    return _request_id_var.set(request_id)


def reset_request_id(token) -> None:
    _request_id_var.reset(token)


def set_user_context(
    *, user_id: Optional[str] = None, thread_id: Optional[str] = None
):
    """设置当前请求的用户/线程上下文，返回 reset token 元组。"""
    t_u = _user_id_var.set(user_id) if user_id is not None else None
    t_t = _thread_id_var.set(thread_id) if thread_id is not None else None
    return (t_u, t_t)


def reset_user_context(tokens) -> None:
    t_u, t_t = tokens
    if t_u is not None:
        _user_id_var.reset(t_u)
    if t_t is not None:
        _thread_id_var.reset(t_t)


def _context_prefix() -> str:
    """构造 text 格式的上下文前缀片段（如 [req=xxx] [user=xxx] [thread=xxx]）。"""
    parts = []
    rid = _request_id_var.get()
    if rid:
        parts.append(f"[req={rid}]")
    uid = _user_id_var.get()
    if uid:
        parts.append(f"[user={uid[:8]}]")
    tid = _thread_id_var.get()
    if tid:
        parts.append(f"[thread={tid[:8]}]")
    return " ".join(parts)


def _resolve_log_dir() -> Optional[Path]:
    if not settings.LOG_DIR:
        return None
    log_dir = _PROJECT_ROOT / settings.LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _make_text_formatter() -> logging.Formatter:
    class TextFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            base = super().format(record)
            prefix = _context_prefix()
            return f"{prefix} {base}" if prefix else base

    return TextFormatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _make_json_formatter() -> logging.Formatter:
    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_obj = {
                "time": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "line": record.lineno,
                "message": record.getMessage(),
            }
            rid = _request_id_var.get()
            if rid:
                log_obj["request_id"] = rid
            uid = _user_id_var.get()
            if uid:
                log_obj["user_id"] = uid
            tid = _thread_id_var.get()
            if tid:
                log_obj["thread_id"] = tid
            if record.exc_info and record.exc_info[0]:
                log_obj["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_obj, ensure_ascii=False)
    return JsonFormatter()


def _make_rotating_handler(
    log_dir: Path,
    filename: str,
    level: int = logging.DEBUG,
) -> TimedRotatingFileHandler:
    handler = TimedRotatingFileHandler(
        filename=str(log_dir / filename),
        when="midnight",
        interval=1,
        backupCount=settings.LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.suffix = "%Y-%m-%d.log"
    return handler


def setup_logging() -> None:
    """配置日志系统：控制台 + 文件（按天轮转）"""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # 清除已有 handler（防止重复初始化）
    root_logger.handlers.clear()

    formatter = _make_text_formatter() if settings.LOG_FORMAT == "text" else _make_json_formatter()

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件 handler
    log_dir = _resolve_log_dir()
    if log_dir:
        # 应用日志（全量）
        app_handler = _make_rotating_handler(log_dir, "app.log")
        app_handler.setFormatter(formatter)
        root_logger.addHandler(app_handler)

        # 错误日志（仅 ERROR+）
        error_handler = _make_rotating_handler(log_dir, "error.log", level=logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)

        logging.getLogger("fitcream").info(
            f"日志文件输出到: {log_dir} (保留 {settings.LOG_RETENTION_DAYS} 天)"
        )

    # 请求日志单独 logger → access.log
    access_logger = logging.getLogger("fitcream.access")
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False  # 不向 root 传播，避免重复
    if log_dir:
        access_handler = _make_rotating_handler(log_dir, "access.log")
        access_handler.setFormatter(logging.Formatter("%(message)s"))
        access_logger.addHandler(access_handler)
    # access log 也输出到控制台
    access_console = logging.StreamHandler(sys.stdout)
    access_console.setLevel(logging.INFO)
    access_console.setFormatter(logging.Formatter("%(message)s"))
    access_logger.addHandler(access_console)

    # 降低第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_access_logger() -> logging.Logger:
    return logging.getLogger("fitcream.access")
