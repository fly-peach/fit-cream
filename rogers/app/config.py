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
    # Agent 时间上下文与打卡/饮食默认日期的时区（默认国内用户 UTC+8）
    APP_TZ: str = "Asia/Shanghai"

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
    # 默认统一为 qwen3.8-flash（多模态，兼容文本+图片），不再区分文本/视觉模型切换
    DASHSCOPE_MODEL: str = "qwen3.8-flash"
    DASHSCOPE_VISION_MODEL: str = "qwen3-vl-flash"  # 视觉模型（图片识别，兜底备选）
    DASHSCOPE_TEMPERATURE: float = 0.7
    DASHSCOPE_ENABLE_THINKING: bool = True
    # 文本向量化模型（记忆系统 + 动作库语义检索共用）
    DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIMENSION: int = 1024

    # ---------- 知识库语义检索（rerank） ----------
    RERANK_ENABLED: bool = True
    RERANK_MODEL: str = "qwen3-rerank"
    RERANK_TOP_N: int = 20
    # 知识库语义向量整体开关（关闭后检索/摄入退化为纯全文）
    KB_EMBEDDING_ENABLED: bool = True
    # rerank 精排阶段是否把用户画像拼进 query 侧做排序参考（关闭后个性化静默失效）
    KB_RERANK_PROFILE_ENABLED: bool = True
    # 动作库混合检索 rerank 开关（关闭后 exercise hybrid_search 退化为纯向量序）
    EXERCISE_RERANK_ENABLED: bool = True

    # ---------- DeepSeek 官方 API（视觉模型） ----------
    # deepseek-v4-flash-vision-exp 仅在 DeepSeek 官方端点提供：DashScope 未托管该模型，
    # 且 DashScope 上的 deepseek 文本模型收到 image_url 块会静默丢弃（不报错也不识图）。
    # DEEPSEEK_API_KEY 为我方兜底环境 key；BYOK 用户 key（仅存前端 localStorage）优先。
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_VISION_MODEL: str = "deepseek-v4-flash-vision-exp"
    DEEPSEEK_TEMPERATURE: float = 0.7

    # ---------- 记忆容量上限 ----------
    # 每用户各类记忆的上限条数，超过上限时按淘汰策略删除多余记录
    MEMORY_EPISODIC_MAX: int = 200
    MEMORY_PROCEDURAL_MAX: int = 50

    # ---------- CORS ----------
    # https://localhost / http://localhost 为 Capacitor App（本地 WebView）origin
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "https://localhost",
        "http://localhost",
    ]

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
