"""
认证服务

处理用户注册、登录、Token 刷新、密码管理、验证码、审计日志。
"""
import logging
import secrets
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from src.fitme.models.user import User
from src.fitme.models.user_settings import UserSettings
from src.fitme.models.auth_models import (
    LoginAttempt,
    RefreshTokenBlacklist,
    UserAuditLog,
    VerificationCode,
)
from src.auth.auth import TokenPair
from src.fitme.services.sms_service import SmsService
from utils.exceptions import BusinessException, ErrorCode
from utils.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)

logger = logging.getLogger(__name__)


class AuthService:
    @staticmethod
    async def register(
        db: AsyncSession,
        phone: str,
        password: str,
        name: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        verification_code: str | None = None,
    ) -> tuple[User, TokenPair]:
        result = await db.execute(select(User).where(User.phone == phone))
        if result.scalar_one_or_none():
            raise BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS, "手机号已注册")

        # 可选：短信验证码校验（当阿里云 SMS 已配置且传入验证码时）
        if verification_code and settings.ALIBABA_CLOUD_ACCESS_KEY_ID:
            await AuthService.verify_code(db, phone, verification_code, "register")

        user = await AuthService._create_user(
            db,
            phone,
            hash_password(password),
            name,
            is_verified=bool(verification_code),
            ip=ip,
            user_agent=user_agent,
            audit_action="register",
        )
        tokens = AuthService._generate_tokens(user.id)
        return user, tokens

    @staticmethod
    async def login(
        db: AsyncSession,
        phone: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, TokenPair]:
        # 检查登录失败锁定
        await AuthService._check_login_lock(db, phone)

        result = await db.execute(select(User).where(User.phone == phone))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            await AuthService._record_failed_attempt(db, user.id if user else None, phone, ip)
            raise BusinessException(ErrorCode.INVALID_CREDENTIALS, "手机号或密码错误")

        await AuthService._finalize_login(db, user, phone, ip, user_agent, action="login")
        tokens = AuthService._generate_tokens(user.id)
        return user, tokens

    @staticmethod
    async def sms_login(
        db: AsyncSession,
        phone: str,
        code: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, TokenPair]:
        """短信验证码登录：验证码校验通过后，未注册手机号自动注册。

        与密码登录一致地复用登录失败锁定，防止验证码被暴力破解。
        """
        # 检查登录失败锁定（防验证码暴力破解）
        await AuthService._check_login_lock(db, phone)

        try:
            user = await AuthService.verify_code(db, phone, code, "login")
        except BusinessException:
            # 验证码错误/过期：记录失败 attempt（单独提交，供锁定机制计数）
            await AuthService._record_failed_attempt(db, None, phone, ip)
            raise

        if not user:
            user = await AuthService._create_user(
                db,
                phone,
                hash_password(uuid4().hex),
                f"用户{phone[-4:]}",
                is_verified=True,
                ip=ip,
                user_agent=user_agent,
                audit_action="register_sms",
            )
        else:
            await AuthService._finalize_login(
                db, user, phone, ip, user_agent, action="login_sms", mark_verified=True
            )

        tokens = AuthService._generate_tokens(user.id)
        return user, tokens

    @staticmethod
    async def refresh_token(db: AsyncSession, refresh_token: str) -> TokenPair:
        payload = verify_refresh_token(refresh_token)
        if not payload:
            raise BusinessException(ErrorCode.INVALID_TOKEN, "无效的刷新令牌")

        # 检查黑名单
        jti = payload.get("jti")
        if jti:
            blacklisted = await db.execute(
                select(RefreshTokenBlacklist).where(
                    RefreshTokenBlacklist.jti == jti
                )
            )
            if blacklisted.scalar_one_or_none():
                raise BusinessException(ErrorCode.INVALID_TOKEN, "令牌已注销")

        user_id = UUID(payload.get("sub"))
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise BusinessException(ErrorCode.USER_NOT_FOUND, "用户不存在")

        return AuthService._generate_tokens(user.id)

    @staticmethod
    async def change_password(
        db: AsyncSession,
        user: User,
        old_password: str,
        new_password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if not verify_password(old_password, user.password_hash):
            raise BusinessException(ErrorCode.INVALID_CREDENTIALS, "原密码错误")

        user.password_hash = hash_password(new_password)
        await db.flush()
        AuthService._log_audit(db, user.id, "change_password", ip, user_agent)

    @staticmethod
    async def logout(
        db: AsyncSession,
        refresh_token: str,
    ) -> None:
        payload = verify_refresh_token(refresh_token)
        if not payload:
            raise BusinessException(ErrorCode.INVALID_TOKEN, "无效的刷新令牌")

        jti = payload.get("jti", "")
        expires_at = datetime.utcfromtimestamp(payload.get("exp", 0))
        user_id = UUID(payload.get("sub"))

        blacklist = RefreshTokenBlacklist(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            reason="user_logout",
        )
        db.add(blacklist)
        await db.flush()

    @staticmethod
    async def send_verification_code(
        db: AsyncSession,
        phone: str,
        code_type: str = "register",
        ip: str | None = None,
    ) -> None:
        # 检查冷却期
        cooldown_time = datetime.utcnow() - timedelta(
            seconds=settings.VERIFICATION_CODE_COOLDOWN
        )
        recent = await db.execute(
            select(VerificationCode).where(
                VerificationCode.phone == phone,
                VerificationCode.created_at >= cooldown_time,
            )
        )
        if recent.scalar_one_or_none():
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                f"发送过于频繁，请{settings.VERIFICATION_CODE_COOLDOWN}秒后重试",
            )

        # 检查每手机号每小时上限
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        hourly_count = await db.execute(
            select(func.count()).select_from(VerificationCode).where(
                VerificationCode.phone == phone,
                VerificationCode.created_at >= hour_ago,
            )
        )
        if (hourly_count.scalar() or 0) >= settings.VERIFICATION_CODE_MAX_PER_HOUR:
            raise BusinessException(
                ErrorCode.BAD_REQUEST, "发送次数已达每小时上限"
            )

        # 检查每 IP 每小时上限（防遍历手机号批量触发短信 / 薅短信费用）
        if ip:
            ip_count = await db.execute(
                select(func.count()).select_from(VerificationCode).where(
                    VerificationCode.ip == ip,
                    VerificationCode.created_at >= hour_ago,
                )
            )
            if (ip_count.scalar() or 0) >= settings.VERIFICATION_CODE_MAX_PER_IP_HOUR:
                raise BusinessException(
                    ErrorCode.BAD_REQUEST, "操作过于频繁，请稍后再试"
                )

        # 6 位数字验证码（secrets 均匀分布，避免 uuid4 首位仅 1-3 的弱熵）
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = datetime.utcnow() + timedelta(
            minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES
        )

        vc = VerificationCode(
            phone=phone,
            code=code,
            code_type=code_type,
            expires_at=expires_at,
            ip=ip,
        )
        db.add(vc)
        await db.flush()

        await SmsService.send_code(phone, code)

    @staticmethod
    async def verify_code(
        db: AsyncSession,
        phone: str,
        code: str,
        code_type: str = "register",
    ) -> User | None:
        # 原子消费：UPDATE ... WHERE used_at IS NULL，以 rowcount 判定成功，
        # 避免并发下"读取-置位"两步操作导致同一验证码被重复使用。
        result = await db.execute(
            update(VerificationCode)
            .where(
                VerificationCode.phone == phone,
                VerificationCode.code == code,
                VerificationCode.code_type == code_type,
                VerificationCode.used_at.is_(None),
                VerificationCode.expires_at > datetime.utcnow(),
            )
            .values(used_at=datetime.utcnow())
        )
        if result.rowcount == 0:
            raise BusinessException(ErrorCode.BAD_REQUEST, "验证码无效或已过期")

        user_result = await db.execute(
            select(User).where(User.phone == phone)
        )
        return user_result.scalar_one_or_none()

    @staticmethod
    async def request_password_reset(
        db: AsyncSession,
        phone: str,
        ip: str | None = None,
    ) -> None:
        result = await db.execute(select(User).where(User.phone == phone))
        if not result.scalar_one_or_none():
            raise BusinessException(ErrorCode.USER_NOT_FOUND, "该手机号未注册")

        await AuthService.send_verification_code(db, phone, "reset_password", ip)

    @staticmethod
    async def reset_password(
        db: AsyncSession,
        phone: str,
        code: str,
        new_password: str,
    ) -> None:
        await AuthService.verify_code(db, phone, code, "reset_password")

        result = await db.execute(select(User).where(User.phone == phone))
        user = result.scalar_one_or_none()
        if not user:
            raise BusinessException(ErrorCode.USER_NOT_FOUND, "用户不存在")

        user.password_hash = hash_password(new_password)
        await db.flush()

    @staticmethod
    async def _create_user(
        db: AsyncSession,
        phone: str,
        password_hash: str,
        name: str | None,
        is_verified: bool,
        ip: str | None = None,
        user_agent: str | None = None,
        audit_action: str = "register",
    ) -> User:
        """创建用户 + 默认设置 + 审计日志（register 与 sms 自动注册共用，避免漂移）。"""
        user = User(
            phone=phone,
            password_hash=password_hash,
            name=name,
            is_active=True,
            is_verified=is_verified,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

        db.add(UserSettings(user_id=user.id))
        await db.flush()

        AuthService._log_audit(db, user.id, audit_action, ip, user_agent)
        return user

    @staticmethod
    async def _finalize_login(
        db: AsyncSession,
        user: User,
        phone: str,
        ip: str | None = None,
        user_agent: str | None = None,
        action: str = "login",
        mark_verified: bool = False,
    ) -> None:
        """登录成功收尾：状态校验 + 更新登录信息 + 审计（login 与 sms_login 共用，避免漂移）。"""
        if not user.is_active:
            raise BusinessException(ErrorCode.FORBIDDEN, "账号已被禁用")

        if user.deleted_at:
            raise BusinessException(ErrorCode.USER_NOT_FOUND, "用户不存在")

        if mark_verified:
            user.is_verified = True
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = ip
        await db.flush()

        AuthService._log_login_attempt(db, user.id, phone, True, ip)
        AuthService._log_audit(db, user.id, action, ip, user_agent)

    @staticmethod
    async def _record_failed_attempt(
        db: AsyncSession,
        user_id: UUID | None,
        phone: str,
        ip: str | None = None,
    ) -> None:
        """记录失败登录并立即提交，确保锁定机制可见（异常会回滚事务，须单独提交）。"""
        AuthService._log_login_attempt(db, user_id, phone, False, ip)
        await db.commit()

    @staticmethod
    def _generate_tokens(user_id: UUID) -> TokenPair:
        return TokenPair(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    async def _check_login_lock(db: AsyncSession, phone: str) -> None:
        lock_time = datetime.utcnow() - timedelta(
            minutes=settings.LOGIN_LOCK_MINUTES
        )
        failed_result = await db.execute(
            select(func.count()).select_from(LoginAttempt).where(
                LoginAttempt.phone == phone,
                LoginAttempt.success == False,
                LoginAttempt.attempted_at >= lock_time,
            )
        )
        failed_count = failed_result.scalar() or 0
        if failed_count >= settings.LOGIN_MAX_ATTEMPTS:
            raise BusinessException(
                ErrorCode.FORBIDDEN,
                f"登录失败次数过多，请{settings.LOGIN_LOCK_MINUTES}分钟后再试",
            )

    @staticmethod
    async def _log_login_attempt(
        db: AsyncSession,
        user_id: UUID | None,
        phone: str,
        success: bool,
        ip: str | None = None,
    ) -> None:
        attempt = LoginAttempt(
            user_id=user_id,
            phone=phone,
            ip=ip,
            success=success,
        )
        db.add(attempt)

    @staticmethod
    async def _log_audit(
        db: AsyncSession,
        user_id: UUID,
        action: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        log_entry = UserAuditLog(
            user_id=user_id,
            action=action,
            ip=ip,
            user_agent=user_agent,
        )
        db.add(log_entry)
