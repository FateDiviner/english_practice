from collections.abc import Mapping
from dataclasses import dataclass

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.exception_handlers import (
    ERROR_CODE_FORBIDDEN,
    ERROR_CODE_UNAUTHENTICATED,
    AppError,
    build_error_response,
)
from app.core.security import TokenDecodeError, decode_access_token
from app.db.session import async_session_factory
from app.models.user import User
from app.services.mcp_token import (
    SCOPE_WRITE,
    TOKEN_PREFIX,
    resolve_token,
    token_is_expired,
    touch_token,
)


@dataclass(frozen=True)
class McpAdmin:
    id: int
    username: str
    role: str
    can_write: bool = True
    token_id: int | None = None


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def client_metadata(headers: Mapping[str, str] | None) -> tuple[str | None, str | None]:
    """从请求头提取客户端名称与来源 IP，仅用于审计。"""
    if not headers:
        return None, None
    client_name = _header(headers, "user-agent")
    forwarded = _header(headers, "x-forwarded-for") or _header(headers, "x-real-ip")
    client_ip = forwarded.split(",")[0].strip() if forwarded else None
    return (client_name[:100] if client_name else None, client_ip[:45] if client_ip else None)


async def authenticate_admin(headers: Mapping[str, str] | None) -> McpAdmin:
    """校验 MCP 请求的 Bearer Token：支持长期客户端令牌与管理员 JWT。"""
    authorization = _header(headers or {}, "authorization")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "MCP 请求缺少访问令牌")

    token = authorization[7:].strip()
    if not token:
        raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "MCP 请求缺少访问令牌")

    if token.startswith(TOKEN_PREFIX):
        return await _authenticate_client_token(token)

    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError, TokenDecodeError) as exc:
        raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "访问令牌无效或已过期") from exc

    async with async_session_factory() as session:
        user = await session.get(User, user_id)

    if user is None or user.status != "active":
        raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "管理员账号不存在或已被禁用")
    if user.role != "admin":
        raise AppError(403, ERROR_CODE_FORBIDDEN, "无管理员权限")

    return McpAdmin(id=user.id, username=user.username, role=user.role, can_write=True)


async def _authenticate_client_token(token: str) -> McpAdmin:
    async with async_session_factory() as session:
        access = await resolve_token(session, token)
        if access is None:
            raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "MCP 客户端令牌无效")
        if access.revoked_at is not None:
            raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "MCP 客户端令牌已被吊销")
        if token_is_expired(access):
            raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "MCP 客户端令牌已过期")

        user = await session.get(User, access.created_by)
        if user is None or user.status != "active":
            raise AppError(401, ERROR_CODE_UNAUTHENTICATED, "令牌创建者账号不存在或已被禁用")
        if user.role != "admin":
            raise AppError(403, ERROR_CODE_FORBIDDEN, "无管理员权限")

        await touch_token(session, access)

    return McpAdmin(
        id=user.id,
        username=user.username,
        role=user.role,
        can_write=access.scopes == SCOPE_WRITE,
        token_id=access.id,
    )


class McpAuthMiddleware:
    """在 MCP 传输层拒绝未携带管理员令牌的 HTTP 请求。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        try:
            await authenticate_admin(headers)
        except AppError as exc:
            response = build_error_response(exc.status_code, exc.code, exc.message)
            response.headers["WWW-Authenticate"] = "Bearer"
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class McpPathRewriteMiddleware:
    """把 /mcp 的尾部斜杠差异抹平，避免 Starlette Mount 返回 307。"""

    def __init__(self, app: ASGIApp, path: str = "/mcp") -> None:
        self.app = app
        self.path = path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == self.path:
            scope = {
                **scope,
                "path": f"{self.path}/",
                "raw_path": f"{self.path}/".encode(),
            }
        await self.app(scope, receive, send)
