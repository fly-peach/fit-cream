"""
安全工具模块

提供 JWT Token 的生成与验证，以及 bcrypt 密码哈希功能。

- access token: 默认 7 天，用于 API 鉴权
- refresh token: 默认 30 天，用于无感刷新 access token
- 密码哈希: bcrypt 12 轮，不可逆
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    """密码哈希（bcrypt 12 轮）"""
    # bcrypt 限制密码最长 72 字节
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    pwd_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))


def mask_phone(phone: str) -> str:
    """手机号脱敏：保留前 3 位与后 4 位，用于日志输出。

    如 13800138000 -> 138****8000。
    """
    if not phone:
        return ""
    return f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 8 else "****"


def create_access_token(user_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(user_id),
        "jti": str(uuid4()),
        "iat": datetime.utcnow(),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: UUID) -> str:
    """创建刷新令牌"""
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "jti": str(uuid4()),
        "iat": datetime.utcnow(),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_access_token(token: str) -> Optional[dict]:
    """验证访问令牌"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def verify_refresh_token(token: str) -> Optional[dict]:
    """验证刷新令牌"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None


def create_password_setup_token(phone: str, expires_minutes: int = 10) -> str:
    """创建「设置密码」短时令牌（绑定手机号，用于验证码登录未注册时的建号引导）。

    此时用户尚未建号，无法用 user_id 作为 sub，故以 phone 为 sub，
    并由 type 与 access/refresh 区分，禁止其通过 get_current_user 鉴权。
    """
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {
        "sub": phone,
        "jti": str(uuid4()),
        "iat": datetime.utcnow(),
        "exp": expire,
        "type": "password_setup",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_password_setup_token(token: str) -> Optional[str]:
    """验证「设置密码」令牌，返回绑定的手机号；无效/过期/类型不符返回 None。"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "password_setup":
            return None
        return payload.get("sub")
    except JWTError:
        return None