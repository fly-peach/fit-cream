"""
自定义异常 + 全局异常处理器

业务异常体系：
- BusinessException: 所有业务异常基类，携带 code + message
- NotFoundException / UnauthorizedException / ForbiddenException / BadRequestException: 常用子类

全局异常处理器：
- BusinessException → HTTP 200 + 业务错误码（前端根据 code 判断）
- RequestValidationError → HTTP 422 + 参数校验详情
- Exception → HTTP 500 + 通用错误（隐藏内部细节）
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorCode:
    # 通用
    SUCCESS = 0
    UNKNOWN_ERROR = 50000

    # 认证 401xx
    UNAUTHORIZED = 40100
    INVALID_TOKEN = 40101
    TOKEN_EXPIRED = 40102
    INVALID_CREDENTIALS = 40103

    # 权限 403xx
    FORBIDDEN = 40300
    RESOURCE_NOT_OWNED = 40301

    # 资源 404xx
    NOT_FOUND = 40400
    USER_NOT_FOUND = 40401
    PLAN_NOT_FOUND = 40402
    CHECKIN_NOT_FOUND = 40403
    KB_NOT_FOUND = 40404
    KB_DOCUMENT_NOT_FOUND = 40405

    # 业务 400xx
    BAD_REQUEST = 40000
    EMAIL_ALREADY_EXISTS = 40001
    CHECKIN_ALREADY_EXISTS = 40002
    INVALID_DATE = 40003
    INVALID_MOOD_RANGE = 40004
    UNSUPPORTED_FORMAT = 40005

    # Agent 500xx
    AGENT_ERROR = 50001
    TOOL_EXECUTION_ERROR = 50002
    LLM_ERROR = 50003


class BusinessException(Exception):
    """业务异常基类"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundException(BusinessException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(ErrorCode.NOT_FOUND, message)


class UnauthorizedException(BusinessException):
    def __init__(self, message: str = "未授权"):
        super().__init__(ErrorCode.UNAUTHORIZED, message)


class ForbiddenException(BusinessException):
    def __init__(self, message: str = "无权限"):
        super().__init__(ErrorCode.FORBIDDEN, message)


class BadRequestException(BusinessException):
    def __init__(self, message: str = "请求参数错误", code: int = ErrorCode.BAD_REQUEST):
        super().__init__(code, message)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""

    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        return JSONResponse(
            status_code=200,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # 仅保留可安全 JSON 序列化的字段：model_validator 抛出的 ValueError 会进入
        # ctx，直接透传 exc.errors() 会让 422 处理器自身崩溃成 500
        safe_errors = [
            {
                "loc": list(err.get("loc", [])),
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "code": ErrorCode.BAD_REQUEST,
                "message": "参数校验失败",
                "data": {"errors": safe_errors},
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "code": ErrorCode.UNKNOWN_ERROR,
                "message": "服务器内部错误",
                "data": None,
            },
        )