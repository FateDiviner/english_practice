import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import (
    ERROR_CODE_CONFLICT,
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_VALIDATION,
    AppError,
)
from app.models.mcp import McpAccessToken
from app.models.user import User

TOKEN_PREFIX = "mcp_"
SCOPE_READ = "read"
SCOPE_WRITE = "write"
ALLOWED_SCOPES = {SCOPE_READ, SCOPE_WRITE}
DISPLAY_PREFIX_LENGTH = 12


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _generate_token() -> tuple[str, str, str]:
    raw_token = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    return raw_token, hash_token(raw_token), raw_token[:DISPLAY_PREFIX_LENGTH]


async def create_token(
    session: AsyncSession,
    *,
    admin_id: int,
    name: str,
    scopes: str,
    expires_in_days: int | None,
) -> tuple[McpAccessToken, str]:
    """创建长期客户端令牌，明文只在创建响应中返回一次。"""
    clean_name = name.strip()
    if not clean_name:
        raise AppError(422, ERROR_CODE_VALIDATION, "令牌名称不能为空")
    if scopes not in ALLOWED_SCOPES:
        raise AppError(422, ERROR_CODE_VALIDATION, "scopes 只能是 read 或 write")
    if expires_in_days is not None and expires_in_days <= 0:
        raise AppError(422, ERROR_CODE_VALIDATION, "有效期必须大于 0 天")

    raw_token, token_hash, prefix = _generate_token()
    token = McpAccessToken(
        name=clean_name[:100],
        token_prefix=prefix,
        token_hash=token_hash,
        scopes=scopes,
        created_by=admin_id,
        expires_at=(
            _utcnow() + timedelta(days=expires_in_days) if expires_in_days is not None else None
        ),
    )
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return token, raw_token


async def list_tokens(session: AsyncSession) -> list[tuple[McpAccessToken, str]]:
    rows = await session.execute(
        select(McpAccessToken, User.username)
        .join(User, User.id == McpAccessToken.created_by)
        .order_by(McpAccessToken.created_at.desc(), McpAccessToken.id.desc()),
    )
    return [(token, username) for token, username in rows]


async def get_token(session: AsyncSession, token_id: int) -> McpAccessToken:
    token = await session.get(McpAccessToken, token_id)
    if token is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "MCP 令牌不存在")
    return token


async def revoke_token(session: AsyncSession, token_id: int) -> McpAccessToken:
    token = await get_token(session, token_id)
    if token.revoked_at is not None:
        raise AppError(409, ERROR_CODE_CONFLICT, "令牌已吊销")
    token.revoked_at = _utcnow()
    await session.commit()
    await session.refresh(token)
    return token


async def resolve_token(session: AsyncSession, raw_token: str) -> McpAccessToken | None:
    return await session.scalar(
        select(McpAccessToken).where(McpAccessToken.token_hash == hash_token(raw_token)),
    )


def token_is_expired(token: McpAccessToken, now: datetime | None = None) -> bool:
    if token.expires_at is None:
        return False
    return token.expires_at <= (now or _utcnow())


async def touch_token(session: AsyncSession, token: McpAccessToken) -> None:
    token.last_used_at = _utcnow()
    await session.commit()
