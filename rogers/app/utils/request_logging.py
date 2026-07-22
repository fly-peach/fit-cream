"""
HTTP 请求日志中间件

记录每次请求的：时间、方法、路径、状态码、耗时、客户端 IP、User-Agent。
输出到 access.log 文件和控制台。

日志格式（text）:
    2026-07-22 13:37:28 | INFO  | POST /api/chat/send | 200 | 1234ms | 127.0.0.1 | Mozilla/5.0...

日志格式（json）:
    {"time":"2026-07-22 13:37:28","method":"POST","path":"/api/chat/send","status":200,"duration_ms":1234,"client_ip":"127.0.0.1","user_agent":"..."}
"""
import json
import logging
import time
from datetime import datetime

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.utils.logger import get_access_logger

# 不记录日志的路径前缀（静态资源等）
_SKIP_PREFIXES = ("/assets/", "/favicon.ico", "/robots.txt")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录每次 HTTP 请求的中间件"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 跳过静态资源
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        # 提取客户端 IP（支持反向代理 X-Forwarded-For）
        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not client_ip and request.client:
            client_ip = request.client.host

        user_agent = request.headers.get("user-agent", "")
        status_code = response.status_code
        method = request.method
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        access_logger = get_access_logger()

        if settings.LOG_FORMAT == "json":
            log_entry = json.dumps({
                "time": timestamp,
                "method": method,
                "path": path,
                "query": str(request.url.query) if request.url.query else None,
                "status": status_code,
                "duration_ms": round(duration_ms, 1),
                "client_ip": client_ip,
                "user_agent": user_agent[:120],
            }, ensure_ascii=False)
            access_logger.info(log_entry)
        else:
            # 根据状态码选择日志级别
            level = logging.WARNING if status_code >= 400 else logging.INFO
            access_logger.log(
                level,
                f"{timestamp} | {method:6s} | {path:40s} | {status_code} | "
                f"{duration_ms:8.1f}ms | {client_ip or '-'} | {user_agent[:60]}",
            )

        return response
