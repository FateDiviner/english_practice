from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import require_admin
from app.db.session import get_session
from app.models.mcp import McpAccessToken
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.mcp import (
    McpConnectionOut,
    McpTokenCreatedOut,
    McpTokenCreateIn,
    McpTokenListOut,
    McpTokenOut,
)
from app.services.mcp_audit import log_mcp_event
from app.services.mcp_token import create_token, list_tokens, revoke_token

router = APIRouter(
    prefix="/admin/mcp-tokens",
    tags=["admin-mcp"],
    dependencies=[Depends(require_admin)],
)


def _to_out(token: McpAccessToken, username: str | None = None) -> McpTokenOut:
    return McpTokenOut(
        id=token.id,
        name=token.name,
        token_prefix=token.token_prefix,
        scopes=token.scopes,
        created_by=token.created_by,
        created_by_username=username,
        created_at=token.created_at,
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        revoked_at=token.revoked_at,
    )


def _endpoint() -> str:
    return get_settings().MCP_PUBLIC_URL


@router.get("/connection", response_model=ApiResponse[McpConnectionOut])
async def get_connection_endpoint() -> ApiResponse[McpConnectionOut]:
    """返回 MCP 服务开关、对外端点与默认令牌有效期。"""
    settings = get_settings()
    return ApiResponse[McpConnectionOut](
        code=0,
        message="ok",
        data=McpConnectionOut(
            enabled=settings.MCP_ENABLED,
            endpoint=settings.MCP_PUBLIC_URL,
            default_expires_in_days=settings.MCP_TOKEN_DEFAULT_DAYS,
        ),
    )


@router.get("", response_model=ApiResponse[McpTokenListOut])
async def list_tokens_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[McpTokenListOut]:
    """列出全部 MCP 客户端令牌，不返回明文。"""
    rows = await list_tokens(session)
    return ApiResponse[McpTokenListOut](
        code=0,
        message="ok",
        data=McpTokenListOut(
            items=[_to_out(token, username) for token, username in rows],
        ),
    )


@router.post(
    "",
    response_model=ApiResponse[McpTokenCreatedOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_token_endpoint(
    payload: McpTokenCreateIn,
    current_admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[McpTokenCreatedOut]:
    """创建长期客户端令牌，明文只在本响应返回一次。"""
    token, raw_token = await create_token(
        session,
        admin_id=current_admin.id,
        name=payload.name,
        scopes=payload.scopes,
        expires_in_days=payload.expires_in_days,
    )
    await log_mcp_event(
        session,
        admin_id=current_admin.id,
        tool_name="admin_create_mcp_token",
        outcome="success",
        params={
            "token_id": token.id,
            "name": token.name,
            "scopes": token.scopes,
        },
    )
    return ApiResponse[McpTokenCreatedOut](
        code=0,
        message="ok",
        data=McpTokenCreatedOut(
            **_to_out(token, current_admin.username).model_dump(),
            token=raw_token,
            endpoint=_endpoint(),
        ),
    )


@router.post("/{token_id}/revoke", response_model=ApiResponse[McpTokenOut])
async def revoke_token_endpoint(
    token_id: int,
    current_admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[McpTokenOut]:
    """吊销客户端令牌，已发出的令牌立即失效。"""
    token = await revoke_token(session, token_id)
    await log_mcp_event(
        session,
        admin_id=current_admin.id,
        tool_name="admin_revoke_mcp_token",
        outcome="success",
        params={"token_id": token.id, "name": token.name},
    )
    return ApiResponse[McpTokenOut](
        code=0,
        message="ok",
        data=_to_out(token, current_admin.username),
    )
