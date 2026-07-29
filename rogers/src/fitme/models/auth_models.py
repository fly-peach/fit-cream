"""
认证相关模型

- RefreshTokenBlacklist: 已注销的 refresh token 黑名单（jti + expires_at + revoked_at）
- LoginAttempt: 登录尝试记录（失败计数/锁定检查）
- UserAuditLog: 用户操作审计日志
- VerificationCode: 短信/邮箱验证码（user_id + code + type + expires_at）
"""
from datetime import datetime
from typing import Optional
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RefreshTokenBlacklist(Base):
    __tablename__ = "refresh_token_blacklist"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reason: Mapped[Optional[str]] = mapped_column(String(200))


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ip: Mapped[Optional[str]] = mapped_column(String(50))
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserAuditLog(Base):
    __tablename__ = "user_audit_logs"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    ip: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    detail: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    phone: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    ip: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    code_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
