"""
应用配置

基于 pydantic-settings 从项目根目录 .env 文件加载配置。
所有配置项通过 Settings 类集中管理，字段名与 .env 键一一对应（大小写敏感）。
使用 get_settings() 获取缓存单例，或直接导入 settings 变量。
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env 位于项目根目录（rogers/ 的上一级）
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """全局配置项，字段名与 .env 中的键一一对应（大小写敏感）"""

    # ---------- 应用配置 ----------
    APP_NAME: str = "FitCream"
    DEBUG: bool = False
    API_PREFIX: str = "/api"
    # 是否开放 Swagger UI / OpenAPI（默认关闭，需后端显式开启）
    API_DOCS_ENABLED: bool = False

    # ---------- 数据库 ----------
    DATABASE_URL: str = "postgresql+asyncpg://fitcream:fitcream@localhost:5432/fitcream"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ---------- JWT 认证 ----------
    JWT_SECRET: str = "your-super-secret-key-change-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 7 * 24 * 60  # access token 7 天
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # refresh token 30 天

    # ---------- httpOnly Cookie 认证 ----------
    # token 写入 httpOnly Cookie，避免前端 localStorage 暴露给 XSS
    COOKIE_ACCESS_NAME: str = "fitcream_access"
    COOKIE_REFRESH_NAME: str = "fitcream_refresh"
    # 生产走 HTTPS 时须设为 True（浏览器仅在安全连接下携带 Secure Cookie）
    COOKIE_SECURE: bool = False

    # ---------- 阿里云（SMS 与 OSS 共用同一对 AccessKey） ----------
    ALIBABA_CLOUD_ACCESS_KEY_ID: str = ""
    ALIBABA_CLOUD_ACCESS_KEY_SECRET: str = ""
    ALIBABA_CLOUD_SMS_SIGN_NAME: str = ""
    ALIBABA_CLOUD_SMS_TEMPLATE_CODE: str = ""

    # ---------- 阿里云 OSS 对象存储 ----------
    OSS_ENDPOINT: str = "oss-cn-hangzhou.aliyuncs.com"
    OSS_BUCKET_NAME: str = ""
    # 签名 URL 有效期（秒）。默认 15 天，兼顾跨天对话图片可见与泄露风险
    OSS_SIGN_URL_EXPIRES: int = 1296000

    # ---------- 安全策略 ----------
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15
    VERIFICATION_CODE_LENGTH: int = 4
    VERIFICATION_CODE_EXPIRE_MINUTES: int = 5
    VERIFICATION_CODE_COOLDOWN: int = 60
    VERIFICATION_CODE_MAX_PER_HOUR: int = 5
    VERIFICATION_CODE_MAX_PER_IP_HOUR: int = 10

    # ---------- 种子管理员（首次启动自动创建） ----------
    SEED_ADMIN_PHONE: str = ""
    SEED_ADMIN_PASSWORD: str = ""

    # ---------- DashScope (通义千问) ----------
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_MODEL: str = "qwen3.5-flash"
    DASHSCOPE_VISION_MODEL: str = "qwen3-vl-flash"  # 视觉模型（图片识别）
    DASHSCOPE_TEMPERATURE: float = 1.2
    DASHSCOPE_ENABLE_THINKING: bool = True

    # ---------- CORS ----------
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]

    # ---------- 限流 ----------
    AGENT_RATE_LIMIT: int = 10

    # ---------- 日志 ----------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"
    LOG_DIR: str = "logs"
    ACCESS_LOG_ENABLED: bool = True
    LOG_RETENTION_DAYS: int = 30

    # ---------- MCP ----------
    MCP_ENABLED: bool = True
    MCP_USER_MOUNT_PATH: str = "/mcp/user"
    MCP_ADMIN_MOUNT_PATH: str = "/mcp/admin"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """缓存单例配置"""
    return Settings()


settings = get_settings()
