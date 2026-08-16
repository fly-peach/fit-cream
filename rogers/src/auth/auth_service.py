"""
认证服务

处理用户注册、登录、Token 刷新、密码管理、验证码、审计日志。
"""
import logging
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from src.agents.models.conversation import Conversation
from src.agents.models.thread_meta import ThreadMeta
from src.agents.models.thread_usage import ThreadUsage
from src.fitme.models.user import User
from src.fitme.models.user_settings import UserSettings
from src.fitme.models.user_goals import UserGoals
from src.fitme.models.auth_models import (
    LoginAttempt,
    RefreshTokenBlacklist,
    UserAuditLog,
    VerificationCode,
)
from src.auth.auth import SmsLoginResult, TokenPair
from src.fitme.services.sms_service import SmsService
from utils.exceptions import BusinessException, ErrorCode
from utils.security import (
    create_access_token,
    create_password_setup_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_password_setup_token,
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

        if not user:
            await AuthService._record_failed_attempt(db, None, phone, ip)
            raise BusinessException(ErrorCode.USER_NOT_FOUND, "该手机号尚未注册，请先注册")

        if not verify_password(password, user.password_hash):
            await AuthService._record_failed_attempt(db, user.id, phone, ip)
            raise BusinessException(ErrorCode.INVALID_CREDENTIALS, "密码错误，请重试")

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
    ) -> SmsLoginResult:
        """短信验证码登录：已注册手机号验证成功后直接登录。

        未注册手机号：验证码通过后不自动建号，返回「需设置密码」引导
        （setup_token 绑定手机号），由 setup_password 建号并发 token。
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
            return SmsLoginResult(
                requires_password_setup=True,
                setup_token=create_password_setup_token(phone),
                phone=phone,
            )

        await AuthService._finalize_login(
            db, user, phone, ip, user_agent, action="login_sms", mark_verified=True
        )

        tokens = AuthService._generate_tokens(user.id)
        return SmsLoginResult(
            requires_password_setup=False, user=user, tokens=tokens
        )

    @staticmethod
    async def setup_password(
        db: AsyncSession,
        setup_token: str,
        password: str,
        name: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, TokenPair]:
        """验证码登录未注册用户「设置密码」：校验 setup_token 后建号并发 token。"""
        phone = verify_password_setup_token(setup_token)
        if not phone:
            raise BusinessException(ErrorCode.INVALID_TOKEN, "设置密码凭证无效或已过期")

        result = await db.execute(select(User).where(User.phone == phone))
        if result.scalar_one_or_none():
            raise BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS, "该手机号已注册，请直接登录")

        user = await AuthService._create_user(
            db,
            phone,
            hash_password(password),
            name or f"用户{phone[-4:]}",
            is_verified=True,
            ip=ip,
            user_agent=user_agent,
            audit_action="register_sms",
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

        if not user.is_active:
            raise BusinessException(ErrorCode.FORBIDDEN, "账号已被禁用")

        if user.deleted_at:
            raise BusinessException(ErrorCode.USER_NOT_FOUND, "用户不存在")

        return AuthService._generate_tokens(user.id)

    @staticmethod
    async def change_phone(
        db: AsyncSession,
        user: User,
        new_phone: str,
        code: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """换绑手机号：验证码验证新号后替换旧号（新号须未被占用）。"""
        existing = await db.execute(select(User).where(User.phone == new_phone))
        if existing.scalar_one_or_none():
            raise BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS, "该手机号已被注册")

        await AuthService.verify_code(db, new_phone, code, "change_phone")

        user.phone = new_phone
        await db.flush()
        await AuthService._log_audit(db, user.id, "change_phone", ip, user_agent)
        return user

    @staticmethod
    async def admin_reset_password(db: AsyncSession, user: User) -> str:
        """管理员重置密码：生成随机临时密码并返回明文一次（不校验旧密码）。"""
        temp = secrets.token_urlsafe(9)
        user.password_hash = hash_password(temp)
        await db.flush()
        await AuthService._log_audit(db, user.id, "admin_reset_password")
        return temp

    @staticmethod
    async def confirm_deactivate(
        db: AsyncSession,
        user: User,
        password: str | None = None,
        verification_code: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """本人注销：密码或短信验证码（deactivate）二选一校验后注销。"""
        if password is not None:
            if not verify_password(password, user.password_hash):
                raise BusinessException(ErrorCode.INVALID_CREDENTIALS, "密码错误")
        elif verification_code is not None:
            await AuthService.verify_code(db, user.phone, verification_code, "deactivate")
        else:
            raise BusinessException(ErrorCode.BAD_REQUEST, "请提供密码或短信验证码")

        await AuthService.deactivate_user(db, user, ip=ip, user_agent=user_agent)

    @staticmethod
    async def deactivate_user(
        db: AsyncSession,
        user: User,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """注销用户（软删）：置 deleted_at 并清理关联数据（best-effort）。"""
        if user.deleted_at:
            raise BusinessException(ErrorCode.USER_NOT_FOUND, "用户不存在")

        user.deleted_at = datetime.utcnow()
        user.is_active = False
        await db.flush()

        await AuthService._cleanup_user_data(db, user.id)
        await AuthService._log_audit(db, user.id, "deactivate", ip, user_agent)

    @staticmethod
    async def _cleanup_user_data(db: AsyncSession, user_id: UUID) -> None:
        """注销后清理对话/线程用量/记忆/checkpoint（单点失败仅告警不阻断注销）。"""
        thread_ids: set[str] = set()

        conv_rows = (await db.execute(
            select(Conversation.thread_id).where(
                Conversation.user_id == user_id,
                Conversation.thread_id.isnot(None),
            )
        )).scalars().all()
        thread_ids.update(t for t in conv_rows if t)
        usage_rows = (await db.execute(
            select(ThreadUsage.thread_id).where(ThreadUsage.user_id == user_id)
        )).scalars().all()
        thread_ids.update(t for t in usage_rows if t)
        meta_rows = (await db.execute(
            select(ThreadMeta.thread_id).where(ThreadMeta.user_id == user_id)
        )).scalars().all()
        thread_ids.update(t for t in meta_rows if t)

        try:
            await db.execute(delete(Conversation).where(Conversation.user_id == user_id))
            await db.execute(delete(ThreadUsage).where(ThreadUsage.user_id == user_id))
            await db.execute(delete(ThreadMeta).where(ThreadMeta.user_id == user_id))
            await db.commit()
        except Exception as e:
            logger.warning(f"deactivate: 清空对话/线程数据失败: {e}")

        try:
            from src.agents.harness.runtime.memory.store import get_memory_store
            await get_memory_store().delete_all_user(str(user_id))
        except Exception as e:
            logger.warning(f"deactivate: 清空记忆数据失败: {e}")

        try:
            from src.agents.agent_graph import delete_user_checkpoints
            await delete_user_checkpoints(list(thread_ids))
        except Exception as e:
            logger.warning(f"deactivate: 清理 checkpoint 失败: {e}")

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
        await AuthService._log_audit(db, user.id, "change_password", ip, user_agent)

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

        # N 位数字验证码（secrets 均匀分布，避免 uuid4 首位仅 1-3 的弱熵）
        length = settings.VERIFICATION_CODE_LENGTH
        code = f"{secrets.randbelow(10**length):0{length}d}"
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
        db.add(UserGoals(user_id=user.id))
        await db.flush()

        await AuthService._log_audit(db, user.id, audit_action, ip, user_agent)
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

        await AuthService._log_login_attempt(db, user.id, phone, True, ip)
        await AuthService._log_audit(db, user.id, action, ip, user_agent)

    @staticmethod
    async def _record_failed_attempt(
        db: AsyncSession,
        user_id: UUID | None,
        phone: str,
        ip: str | None = None,
    ) -> None:
        """记录失败登录并立即提交，确保锁定机制可见（异常会回滚事务，须单独提交）。"""
        await AuthService._log_login_attempt(db, user_id, phone, False, ip)
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
                LoginAttempt.success.is_(False),
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
