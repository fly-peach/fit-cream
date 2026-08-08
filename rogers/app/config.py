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
    # 文本向量化模型（记忆系统 + 动作库语义检索共用）
    DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIMENSION: int = 1024

    # ---------- 知识库语义检索（rerank） ----------
    RERANK_ENABLED: bool = True
    RERANK_MODEL: str = "gte-rerank-v2"
    RERANK_TOP_N: int = 20
    # 知识库语义向量整体开关（关闭后检索/摄入退化为纯全文）
    KB_EMBEDDING_ENABLED: bool = True

    # ---------- 计划设计专用模型 ----------
    # 「为我设计健身计划」会话全程使用该模型（经同一 DashScope endpoint/API key）。
    # 非 Qwen 模型须 PLAN_DESIGN_ENABLE_THINKING=false（避免发送 Qwen 专有 enable_thinking extra_body）。
    PLAN_DESIGN_MODEL: str = "deepseek-v4-flash"
    PLAN_DESIGN_ENABLE_THINKING: bool = False
    PLAN_DESIGN_TEMPERATURE: float = 0.7

    # ---------- 记忆容量上限 ----------
    # 每用户各类记忆的上限条数，超过上限时按淘汰策略删除多余记录
    MEMORY_EPISODIC_MAX: int = 200
    MEMORY_PROCEDURAL_MAX: int = 50

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
    # 慢请求阈值（毫秒）：超过则 access log 以 WARNING 高亮并标记 slow
    SLOW_REQUEST_MS: int = 3000

    # ---------- MCP ----------
    MCP_ENABLED: bool = True
    MCP_USER_MOUNT_PATH: str = "/mcp/user"
    MCP_ADMIN_MOUNT_PATH: str = "/mcp/admin"

    # ---------- B 站视频直读 ----------
    # 缓存目录（Docker volume 挂载），留空则禁用缓存
    BILIBILI_CACHE_DIR: str = ""
    # 可选持久化 cookie（应对风控），走环境变量，不硬编码
    BILIBILI_COOKIE: str = ""
    BILIBILI_REQUEST_TIMEOUT: float = 15.0
    BILIBILI_MAX_RETRIES: int = 4
    # ASR 兜底
    BILIBILI_ASR_ENABLED: bool = True
    BILIBILI_ASR_MODEL: str = "small"
    BILIBILI_ASR_DEVICE: str = "cpu"
    BILIBILI_ASR_COMPUTE_TYPE: str = "int8"
    BILIBILI_ASR_VAD: bool = True

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
