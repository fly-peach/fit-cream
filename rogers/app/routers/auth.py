"""
认证路由 /api/auth/*

提供注册、登录、刷新Token、密码管理、验证码端点。
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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
    TokenPair,
    VerifyCodeRequest,
)
from src.fitme.schemas.common import ResponseModel
from src.fitme.schemas.user import UserOut
from src.fitme.models.user import User
from src.auth.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthResponseData(BaseModel):
    user: UserOut
    tokens: TokenPair


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/register", response_model=ResponseModel[AuthResponseData])
async def register(
    data: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user, tokens = await AuthService.register(
        db, data.phone, data.password, data.name,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        verification_code=data.verification_code,
    )
    await db.commit()
    return ResponseModel(
        data=AuthResponseData(
            user=UserOut.model_validate(user),
            tokens=tokens,
        )
    )


@router.post("/login", response_model=ResponseModel[AuthResponseData])
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user, tokens = await AuthService.login(
        db, data.phone, data.password,
        ip=_get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    return ResponseModel(
        data=AuthResponseData(
            user=UserOut.model_validate(user),
            tokens=tokens,
        )
    )


@router.post("/refresh", response_model=ResponseModel[TokenPair])
async def refresh(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    tokens = await AuthService.refresh_token(db, data.refresh_token)
    return ResponseModel(data=tokens)


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
    data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    await AuthService.logout(db, data.refresh_token)
    await db.commit()
    return ResponseModel(message="登出成功")


@router.post("/send-verification-code", response_model=ResponseModel[None])
async def send_verification_code(
    data: SendVerificationCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    await AuthService.send_verification_code(db, data.phone, data.code_type)
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
    db: AsyncSession = Depends(get_db),
):
    await AuthService.request_password_reset(db, data.phone)
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
