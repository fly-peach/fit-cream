"""
认证相关 Schemas

定义注册、登录、刷新 Token 的请求/响应模型。
"""
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from src.fitme.schemas.user import UserOut


class RegisterRequest(BaseModel):
    """用户注册请求"""

    phone: str = Field(min_length=11, max_length=20, description="手机号码")
    password: str = Field(min_length=6, max_length=128)
    name: str | None = Field(default=None, max_length=100)
    verification_code: str | None = Field(default=None, min_length=4, max_length=10, description="短信验证码")


class LoginRequest(BaseModel):
    """用户登录请求"""

    phone: str = Field(min_length=11, max_length=20, description="手机号码")
    password: str


class RefreshRequest(BaseModel):
    """刷新 Token 请求（body 可选：优先使用 httpOnly Cookie 中的 refresh token）"""

    refresh_token: str | None = None


class TokenPair(BaseModel):
    """Token 对（access + refresh）"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token 有效秒数


class SmsLoginRequest(BaseModel):
    """短信验证码登录请求（未注册手机号自动注册）"""
    phone: str = Field(min_length=11, max_length=20)
    code: str = Field(min_length=4, max_length=10)


class SendVerificationCodeRequest(BaseModel):
    """发送验证码请求"""
    phone: str = Field(min_length=11, max_length=20)
    code_type: str = Field(default="register", pattern="^(register|login|reset_password|change_phone_old|change_phone_new|deactivate)$")


class VerifyCodeRequest(BaseModel):
    """验证验证码请求"""
    phone: str = Field(min_length=11, max_length=20)
    code: str = Field(min_length=4, max_length=10)
    code_type: str = Field(default="register")


class RequestPasswordResetRequest(BaseModel):
    """请求密码重置"""
    phone: str = Field(min_length=11, max_length=20)


class ResetPasswordRequest(BaseModel):
    """重置密码"""
    phone: str = Field(min_length=11, max_length=20)
    code: str = Field(min_length=4, max_length=10)
    new_password: str = Field(min_length=6, max_length=128)


class ChangePasswordRequest(BaseModel):
    """修改密码"""
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class LogoutRequest(BaseModel):
    """登出请求（body 可选：优先使用 httpOnly Cookie 中的 refresh token）"""

    refresh_token: str | None = None


class SmsLoginOut(BaseModel):
    """短信验证码登录响应

    已注册：requires_password_setup=False，返回 user（token 走 Cookie）。
    未注册：requires_password_setup=True，返回 setup_token + phone，需先设置密码。
    """

    requires_password_setup: bool = False
    setup_token: str | None = None
    phone: str | None = None
    user: UserOut | None = None


class PasswordSetupRequest(BaseModel):
    """设置密码请求（验证码登录未注册手机号建号）"""

    setup_token: str
    password: str = Field(min_length=6, max_length=128)
    name: str | None = Field(default=None, max_length=100)


@dataclass
class SmsLoginResult:
    """sms_login 服务的中间返回结构

    已注册：requires_password_setup=False + user + tokens。
    未注册：requires_password_setup=True + setup_token + phone。
    """

    requires_password_setup: bool
    user: Any | None = None
    tokens: TokenPair | None = None
    setup_token: str | None = None
    phone: str | None = None


class ChangePhoneRequest(BaseModel):
    """换绑手机号请求（双验证：旧号 + 新号验证码）"""

    new_phone: str = Field(min_length=11, max_length=20)
    old_code: str = Field(min_length=4, max_length=10, description="旧手机号验证码")
    new_code: str = Field(min_length=4, max_length=10, description="新手机号验证码")


class DeactivateRequest(BaseModel):
    """注销账号请求（双因素确认不可逆操作：密码 + 短信验证码均必填）"""

    password: str = Field(min_length=1, max_length=128)
    verification_code: str = Field(min_length=4, max_length=10)