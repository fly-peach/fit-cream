"""
认证相关 Schemas

定义注册、登录、刷新 Token 的请求/响应模型。
"""
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """用户注册请求"""

    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """用户登录请求"""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """刷新 Token 请求"""

    refresh_token: str


class TokenPair(BaseModel):
    """Token 对（access + refresh）"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token 有效秒数