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
import re
import time
import uuid
from datetime import datetime
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from utils.logger import get_access_logger, reset_request_id, set_request_id

# 不记录日志的路径前缀（静态资源等）
_SKIP_PREFIXES = ("/assets/", "/favicon.ico", "/robots.txt")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录每次 HTTP 请求的中间件。

    职责：
    - 生成/透传 request_id（FR-1）：优先取请求头 X-Request-ID，否则生成 uuid 短串；
      写入 request.state 与响应头，并通过 ContextVar 贯穿该请求所有日志。
    - 慢请求高亮（FR-4）：耗时超过 SLOW_REQUEST_MS 时以 WARNING 输出并标记 slow。
    - access log 携带 user_id（FR-5）：从 request.state.user_id 读取（路由层注入）。
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 跳过静态资源
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        # FR-1: request_id 生成/透传（上游网关可经 X-Request-ID 传入）
        # 仅接受安全字符集，防止日志注入；非法值回退到生成的随机 id
        header_request_id = request.headers.get("x-request-id") or ""
        request_id = (
            header_request_id
            if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", header_request_id)
            else uuid.uuid4().hex[:12]
        )
        request.state.request_id = request_id
        rid_token = set_request_id(request_id)

        start_time = time.perf_counter()
        status_code = 500
        response: Optional[Response] = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_access(request, status_code, duration_ms, request_id)
            reset_request_id(rid_token)

    @staticmethod
    def _log_access(
        request: Request, status_code: int, duration_ms: float, request_id: str
    ) -> None:
        access_logger = get_access_logger()

        # 提取客户端 IP（支持反向代理 X-Forwarded-For）
        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not client_ip and request.client:
            client_ip = request.client.host

        user_agent = request.headers.get("user-agent", "")
        method = request.method
        path = request.url.path
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # FR-5: user_id 由路由层写入 request.state（认证后可知）
        user_id = getattr(request.state, "user_id", None)
        # FR-4: 慢请求判定
        slow = duration_ms >= settings.SLOW_REQUEST_MS

        if settings.LOG_FORMAT == "json":
            entry = {
                "time": timestamp,
                "request_id": request_id,
                "method": method,
                "path": path,
                "query": str(request.url.query) if request.url.query else None,
                "status": status_code,
                "duration_ms": round(duration_ms, 1),
                "client_ip": client_ip,
                "user_agent": user_agent[:120],
            }
            if user_id:
                entry["user_id"] = user_id
            if slow:
                entry["slow"] = True
            line = json.dumps(entry, ensure_ascii=False)
            if slow:
                access_logger.warning(line)
            else:
                access_logger.info(line)
        else:
            # 状态码 >= 400 或慢请求均以 WARNING 高亮
            level = logging.WARNING if (status_code >= 400 or slow) else logging.INFO
            user_tag = f" | user={user_id[:8]}" if user_id else ""
            slow_tag = " | SLOW" if slow else ""
            access_logger.log(
                level,
                f"{timestamp} | {method:6s} | {path:40s} | {status_code} | "
                f"{duration_ms:8.1f}ms | {client_ip or '-'} | {user_agent[:60]}"
                f" | req={request_id}{user_tag}{slow_tag}",
            )
