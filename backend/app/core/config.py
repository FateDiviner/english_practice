from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 120
    APP_TIMEZONE: str = "Asia/Shanghai"
    FRONTEND_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"
    )
    ADMIN_USERNAME: str | None = None
    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: str | None = None
    AI_PROVIDER_URL: str = ""
    AI_PROVIDER_KEY: str = ""
    AI_PROVIDER: str = "mock"
    AI_MODEL: str = "qwen2.5:7b"
    PROFILE_CACHE_TTL_SECONDS: int = 21600
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_ENDPOINT: str = ""
    LANGSMITH_PROJECT: str = "english-practice"
    LANGSMITH_SAMPLING_RATE: float = 1.0
    LANGSMITH_HIDE_INPUTS: bool = False
    LANGSMITH_HIDE_OUTPUTS: bool = False
    MCP_ENABLED: bool = False
    MCP_CONFIRM_TTL_MINUTES: int = 30

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
