"""
认证路由 /api/auth/*

提供注册、登录、刷新Token、密码管理、验证码端点。

认证方式：access/refresh token 写入 httpOnly Cookie（SameSite=Lax），
前端不接触 token 明文，降低 XSS 窃取风险；同时兼容 Authorization
Bearer（API 客户端）。响应体不再返回 token。
"""
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from src.auth.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResetPasswordRequest,
    SendVerificationCodeRequest,
    SmsLoginRequest,
    TokenPair,
    VerifyCodeRequest,
)
from src.fitme.schemas.common import ResponseModel
from src.fitme.schemas.user import UserOut
from src.fitme.models.user import User
from src.auth.auth_service import AuthService
from utils.exceptions import BusinessException

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _set_auth_cookies(response: Response, tokens: TokenPair) -> None:
    """将 access/refresh token 写入 httpOnly Cookie（SameSite=Lax 防跨站携带）。"""
    response.set_cookie(
        key=settings.COOKIE_ACCESS_NAME,
        value=tokens.access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=settings.COOKIE_REFRESH_NAME,
        value=tokens.refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    for name in (settings.COOKIE_ACCESS_NAME, settings.COOKIE_REFRESH_NAME):
        response.delete_cookie(key=name, path="/")


def _get_refresh_token(request: Request, body_token: str | None) -> str | None:
    """优先取 httpOnly Cookie 中的 refresh token，其次兼容请求体（API 客户端）。"""
    return request.cookies.get(settings.COOKIE_REFRESH_NAME) or body_token


@router.post("/register", response_model=ResponseModel[UserOut])
async def register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user, tokens = await AuthService.register(
        db, data.phone, data.password, data.name,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        verification_code=data.verification_code,
    )
    await db.commit()
    _set_auth_cookies(response, tokens)
    return ResponseModel(data=UserOut.model_validate(user))


@router.post("/login", response_model=ResponseModel[UserOut])
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user, tokens = await AuthService.login(
        db, data.phone, data.password,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    _set_auth_cookies(response, tokens)
    return ResponseModel(data=UserOut.model_validate(user))


@router.post("/sms-login", response_model=ResponseModel[UserOut])
async def sms_login(
    data: SmsLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user, tokens = await AuthService.sms_login(
        db, data.phone, data.code,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    _set_auth_cookies(response, tokens)
    return ResponseModel(data=UserOut.model_validate(user))


@router.post("/refresh", response_model=ResponseModel[None])
async def refresh(
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    refresh_token = _get_refresh_token(request, data.refresh_token if data else None)
    if not refresh_token:
        raise BusinessException(40101, "缺少刷新令牌")
    tokens = await AuthService.refresh_token(db, refresh_token)
    _set_auth_cookies(response, tokens)
    await db.commit()
    return ResponseModel(message="刷新成功")


@router.get("/me", response_model=ResponseModel[UserOut])
async def me(user: User = Depends(get_current_user)):
    """返回当前登录用户（前端启动时探测会话用）。"""
    return ResponseModel(data=UserOut.model_validate(user))


@router.post("/change-password", response_model=ResponseModel[None])
async def change_password(
    data: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await AuthService.change_password(
        db, user, data.old_password, data.new_password,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return ResponseModel(message="密码修改成功")


@router.post("/logout", response_model=ResponseModel[None])
async def logout(
    request: Request,
    response: Response,
    data: LogoutRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    # 从 Cookie 取 refresh token 加入黑名单；无效或缺失时仍照常清理 Cookie
    refresh_token = _get_refresh_token(request, data.refresh_token if data else None)
    if refresh_token:
        try:
            await AuthService.logout(db, refresh_token)
        except BusinessException:
            pass
    _clear_auth_cookies(response)
    await db.commit()
    return ResponseModel(message="登出成功")


@router.post("/send-verification-code", response_model=ResponseModel[None])
async def send_verification_code(
    data: SendVerificationCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await AuthService.send_verification_code(
        db, data.phone, data.code_type, ip=_get_client_ip(request)
    )
    await db.commit()
    return ResponseModel(message="验证码已发送")


@router.post("/verify-code", response_model=ResponseModel[None])
async def verify_code(
    data: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    await AuthService.verify_code(db, data.phone, data.code, data.code_type)
    await db.commit()
    return ResponseModel(message="验证成功")


@router.post("/request-password-reset", response_model=ResponseModel[None])
async def request_password_reset(
    data: RequestPasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await AuthService.request_password_reset(
        db, data.phone, ip=_get_client_ip(request)
    )
    await db.commit()
    return ResponseModel(message="验证码已发送至您的手机")


@router.post("/reset-password", response_model=ResponseModel[None])
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await AuthService.reset_password(db, data.phone, data.code, data.new_password)
    await db.commit()
    return ResponseModel(message="密码重置成功")
