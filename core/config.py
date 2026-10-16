"""应用配置：统一从环境变量 / .env 读取，严禁将凭证硬编码于业务代码。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 共享层同时被 backend 与 admin_api 使用，配置文件的相对基准不能再靠 __file__
# 往上一级猜（那样从 core/ 看是仓库根，backend/.env 会被漏掉，静默回退到
# SQLite 与默认密钥）。这里显式按优先级解析，两条路径都存在时以 backend 为准。
ENV_FILE = next(
    (
        candidate
        for candidate in (
            PROJECT_ROOT / "backend" / ".env",
            PROJECT_ROOT / ".env",
        )
        if candidate.exists()
    ),
    PROJECT_ROOT / "backend" / ".env",
)


class Settings(BaseSettings):
    """全局配置对象。"""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据库
    database_url: str = "sqlite:///./english_practice.db"

    # 认证
    secret_key: str = "dev-secret-key-please-override"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    # 管理员邀请码：留空则退化为「首个管理员」规则（系统里没有管理员时
    # 才允许注册管理员），配置后建管理员必须提供该码
    admin_invite_code: str = ""

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
