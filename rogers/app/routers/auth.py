"""
认证路由 /api/auth/*

提供用户注册、登录、刷新 Token 三个端点。
注册和登录成功后返回 JWT Token 对（access + refresh）。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from src.auth.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from src.fitme.schemas.common import ResponseModel
from src.fitme.schemas.user import UserOut
from src.auth.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthResponseData(BaseModel):
    user: UserOut
    tokens: TokenPair


@router.post("/register", response_model=ResponseModel[AuthResponseData])
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """注册新用户"""
    user, tokens = await AuthService.register(
        db, data.phone, data.password, data.name
    )
    return ResponseModel(
        data=AuthResponseData(
            user=UserOut.model_validate(user),
            tokens=tokens,
        )
    )


@router.post("/login", response_model=ResponseModel[AuthResponseData])
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户登录"""
    user, tokens = await AuthService.login(db, data.phone, data.password)
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
    """刷新 access token"""
    tokens = await AuthService.refresh_token(db, data.refresh_token)
    return ResponseModel(data=tokens)