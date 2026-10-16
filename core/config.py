"""应用配置：统一从环境变量 / .env 读取，严禁将凭证硬编码于业务代码。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """全局配置对象。"""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据库
    database_url: str = "sqlite:///./english_practice.db"

    # 认证
    secret_key: str = "dev-secret-key-please-override"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # AI 伴学（OpenAI 兼容协议）
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: float = 60.0

    # 跨域
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的跨域配置解析为列表。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def ai_enabled(self) -> bool:
        """三项 AI 配置齐全时才走真实模型，否则降级 Mock。"""
        return bool(self.ai_base_url and self.ai_api_key and self.ai_model)


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。"""
    return Settings()
