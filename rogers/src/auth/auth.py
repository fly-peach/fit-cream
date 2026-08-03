"""
认证相关 Schemas

定义注册、登录、刷新 Token 的请求/响应模型。
"""
from pydantic import BaseModel, Field


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
    code_type: str = Field(default="register", pattern="^(register|login|reset_password)$")


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