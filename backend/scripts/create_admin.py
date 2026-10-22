import asyncio
import logging
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.user import User
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AdminSeedConfigError(Exception):
    """管理员 seed 所需配置缺失或无效。"""


@dataclass(frozen=True)
class AdminSeedResult:
    action: str
    user_id: int
    username: str


def load_admin_credentials(settings: Settings | None = None) -> tuple[str, str, str]:
    """从 Settings 读取并校验 ADMIN_* 配置，绝不回退到默认凭据。"""
    current_settings = settings or get_settings()
    values = {
        "ADMIN_USERNAME": current_settings.ADMIN_USERNAME,
        "ADMIN_EMAIL": current_settings.ADMIN_EMAIL,
        "ADMIN_PASSWORD": current_settings.ADMIN_PASSWORD,
    }
    missing = [
        key
        for key, value in values.items()
        if not value or (key != "ADMIN_PASSWORD" and not value.strip())
    ]

    if missing:
        raise AdminSeedConfigError(
            "缺少管理员环境变量，请在 backend/.env 中配置: " + ", ".join(missing),
        )

    username = values["ADMIN_USERNAME"].strip()
    email = values["ADMIN_EMAIL"].strip().lower()
    password = values["ADMIN_PASSWORD"]
    return username, email, password


async def seed_admin(
    session: AsyncSession,
    username: str,
    email: str,
    password: str,
) -> AdminSeedResult:
    """创建管理员、升级普通用户或更新已有管理员密码。"""
    user = await session.scalar(
        select(User).where(or_(User.username == username, User.email == email)),
    )

    if user is None:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role="admin",
            status="active",
        )
        session.add(user)
        action = "created"
    elif user.role == "user":
        user.role = "admin"
        action = "upgraded_to_admin"
    else:
        user.password_hash = hash_password(password)
        action = "password_updated"

    await session.commit()
    await session.refresh(user)

    return AdminSeedResult(
        action=action,
        user_id=user.id,
        username=user.username,
    )


async def main() -> None:
    """读取 .env 配置并执行幂等的管理员 seed。"""
    try:
        username, email, password = load_admin_credentials()
    except AdminSeedConfigError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc

    async with async_session_factory() as session:
        result = await seed_admin(session, username, email, password)

    logger.info(
        "管理员 seed 完成: action=%s user_id=%s username=%s",
        result.action,
        result.user_id,
        result.username,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(main())
