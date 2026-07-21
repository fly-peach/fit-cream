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

    # ---------- 数据库 ----------
    DATABASE_URL: str = "postgresql+asyncpg://fitcream:fitcream@localhost:5432/fitcream"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ---------- JWT 认证 ----------
    JWT_SECRET: str = "your-super-secret-key-change-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---------- LLM / Agent (OpenAI 兼容) ----------
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    AGENT_MODEL: str = "gpt-4o-mini"
    AGENT_TEMPERATURE: float = 0.7
    AGENT_MAX_TOKENS: int = 2000

    # ---------- DashScope (通义千问) ----------
    DASHSCOPE_API_KEY: str = ""

    # ---------- CORS ----------
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ---------- 限流 ----------
    AGENT_RATE_LIMIT: int = 10  # requests per minute

    # ---------- 日志 ----------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text

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