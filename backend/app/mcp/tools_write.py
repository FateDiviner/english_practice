from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import AppError
from app.db.session import async_session_factory
from app.mcp import auth
from app.models.user import User
from app.services.mcp_audit import log_mcp_event
from app.services.mcp_change import (
    cancel_change_request,
    create_change_request,
    get_change_request,
    list_change_requests,
)


def _request_payload(request: Any) -> dict[str, Any]:
    return {
        "request_id": request.id,
        "status": request.status,
        "action_type": request.action_type,
        "target_type": request.target_type,
        "target_id": request.target_id,
        "summary": request.summary,
        "expires_at": request.expires_at.isoformat() if request.expires_at else None,
    }


def _filled(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


async def _propose(
    ctx: Context,
    tool_name: str,
    action_type: str,
    payload: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    admin = await auth.authenticate_admin(ctx.headers)
    if not admin.can_write:
        raise ToolError("该 MCP 令牌只有只读权限，不能提交变更申请")
    client_name, client_ip = auth.client_metadata(ctx.headers)
    async with async_session_factory() as session:
        try:
            request = await create_change_request(
                session,
                admin_id=admin.id,
                action_type=action_type,
                payload=payload,
                reason=reason or None,
                client_name=client_name,
                client_ip=client_ip,
            )
        except AppError as exc:
            await log_mcp_event(
                session,
                admin_id=admin.id,
                tool_name=tool_name,
                outcome="error",
                action_type=action_type,
                params=payload,
                error_code=exc.code,
                client_name=client_name,
                client_ip=client_ip,
            )
            raise ToolError(exc.message) from exc

        await log_mcp_event(
            session,
            admin_id=admin.id,
            tool_name=tool_name,
            outcome="proposed",
            action_type=action_type,
            target_type=request.target_type,
            target_id=request.target_id,
            params=payload,
            client_name=client_name,
            client_ip=client_ip,
        )
        return {
            **_request_payload(request),
            "message": "变更申请已提交，请管理员在管理端「MCP 审批」页面确认后才会执行。",
        }


async def _with_session(
    ctx: Context,
    tool_name: str,
    params: dict[str, Any],
    handler: Any,
    *,
    require_write: bool = False,
) -> dict[str, Any]:
    admin = await auth.authenticate_admin(ctx.headers)
    if require_write and not admin.can_write:
        raise ToolError("该 MCP 令牌只有只读权限，不能执行此操作")
    client_name, client_ip = auth.client_metadata(ctx.headers)
    async with async_session_factory() as session:
        try:
            data = await handler(session, admin.id)
        except AppError as exc:
            await log_mcp_event(
                session,
                admin_id=admin.id,
                tool_name=tool_name,
                outcome="error",
                params=params,
                error_code=exc.code,
                client_name=client_name,
                client_ip=client_ip,
            )
            raise ToolError(exc.message) from exc
        await log_mcp_event(
            session,
            admin_id=admin.id,
            tool_name=tool_name,
            outcome="success",
            params=params,
            client_name=client_name,
            client_ip=client_ip,
        )
        return data


def register_write_tools(server: MCPServer) -> None:
    @server.tool(
        name="propose_wordbook_create",
        description="提交「创建词书」申请，管理员审批后生效。不会立即写入数据。",
    )
    async def propose_wordbook_create_tool(
        ctx: Context,
        name: str,
        description: str | None = None,
        level: str | None = None,
        status: str = "draft",
        reason: str = "",
    ) -> dict[str, Any]:
        payload = _filled(
            {
                "name": name,
                "description": description,
                "level": level,
                "status": status,
            },
        )
        return await _propose(ctx, "propose_wordbook_create", "wordbook.create", payload, reason)

    @server.tool(
        name="propose_wordbook_update",
        description=(
            "提交「更新词书」申请。只提交非空字段；清空字段请使用原后台页面。"
            "管理员审批后生效。"
        ),
    )
    async def propose_wordbook_update_tool(
        ctx: Context,
        wordbook_id: int,
        name: str | None = None,
        description: str | None = None,
        level: str | None = None,
        status: str | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        payload = _filled(
            {
                "wordbook_id": wordbook_id,
                "name": name,
                "description": description,
                "level": level,
                "status": status,
            },
        )
        return await _propose(ctx, "propose_wordbook_update", "wordbook.update", payload, reason)

    @server.tool(
        name="propose_wordbook_delete",
        description="提交「删除词书」申请，管理员审批后生效。非空词书会被拒绝。",
    )
    async def propose_wordbook_delete_tool(
        ctx: Context,
        wordbook_id: int,
        reason: str = "",
    ) -> dict[str, Any]:
        return await _propose(
            ctx,
            "propose_wordbook_delete",
            "wordbook.delete",
            {"wordbook_id": wordbook_id},
            reason,
        )

    @server.tool(
        name="propose_word_create",
        description="提交「在词书中新增单词」申请，管理员审批后生效。不会立即写入数据。",
    )
    async def propose_word_create_tool(
        ctx: Context,
        wordbook_id: int,
        spelling: str,
        phonetic_uk: str | None = None,
        phonetic_us: str | None = None,
        meaning_cn: str | None = None,
        part_of_speech: str | None = None,
        example_en: str | None = None,
        example_cn: str | None = None,
        audio_url: str | None = None,
        sort_order: int = 0,
        reason: str = "",
    ) -> dict[str, Any]:
        payload = _filled(
            {
                "wordbook_id": wordbook_id,
                "spelling": spelling,
                "phonetic_uk": phonetic_uk,
                "phonetic_us": phonetic_us,
                "meaning_cn": meaning_cn,
                "part_of_speech": part_of_speech,
                "example_en": example_en,
                "example_cn": example_cn,
                "audio_url": audio_url,
                "sort_order": sort_order,
            },
        )
        return await _propose(ctx, "propose_word_create", "word.create", payload, reason)

    @server.tool(
        name="propose_word_update",
        description=(
            "提交「更新单词」申请。只提交非空字段；清空字段请使用原后台页面。"
            "管理员审批后生效。"
        ),
    )
    async def propose_word_update_tool(
        ctx: Context,
        word_id: int,
        spelling: str | None = None,
        phonetic_uk: str | None = None,
        phonetic_us: str | None = None,
        meaning_cn: str | None = None,
        part_of_speech: str | None = None,
        example_en: str | None = None,
        example_cn: str | None = None,
        audio_url: str | None = None,
        sort_order: int | None = None,
        reason: str = "",
    ) -> dict[str, Any]:
        payload = _filled(
            {
                "word_id": word_id,
                "spelling": spelling,
                "phonetic_uk": phonetic_uk,
                "phonetic_us": phonetic_us,
                "meaning_cn": meaning_cn,
                "part_of_speech": part_of_speech,
                "example_en": example_en,
                "example_cn": example_cn,
                "audio_url": audio_url,
                "sort_order": sort_order,
            },
        )
        return await _propose(ctx, "propose_word_update", "word.update", payload, reason)

    @server.tool(
        name="propose_word_delete",
        description="提交「删除单词」申请，管理员审批后生效。",
    )
    async def propose_word_delete_tool(
        ctx: Context,
        word_id: int,
        reason: str = "",
    ) -> dict[str, Any]:
        return await _propose(
            ctx,
            "propose_word_delete",
            "word.delete",
            {"word_id": word_id},
            reason,
        )

    @server.tool(
        name="propose_user_status",
        description="提交「启用/禁用用户」申请，status 只能是 active 或 disabled。",
    )
    async def propose_user_status_tool(
        ctx: Context,
        user_id: int,
        status: str,
        reason: str = "",
    ) -> dict[str, Any]:
        if status not in ("active", "disabled"):
            raise ToolError("status 只能是 active 或 disabled")
        return await _propose(
            ctx,
            "propose_user_status",
            "user.status",
            {"user_id": user_id, "status": status},
            reason,
        )

    @server.tool(
        name="propose_profile_refresh",
        description="提交「重新生成用户学情画像」申请，管理员审批后执行分析。",
    )
    async def propose_profile_refresh_tool(
        ctx: Context,
        user_id: int,
        reason: str = "",
    ) -> dict[str, Any]:
        return await _propose(
            ctx,
            "propose_profile_refresh",
            "user.profile_refresh",
            {"user_id": user_id},
            reason,
        )

    @server.tool(name="get_change_request", description="查询某条变更申请的审批状态与执行结果。")
    async def get_change_request_tool(ctx: Context, request_id: int) -> dict[str, Any]:
        async def handler(session: AsyncSession, _admin_id: int) -> dict[str, Any]:
            request, username = await get_change_request(session, request_id)
            return {
                **_request_payload(request),
                "requested_by": request.requested_by,
                "requested_by_username": username,
                "reason": request.reason,
                "result": request.result,
                "error_message": request.error_message,
            }

        return await _with_session(
            ctx,
            "get_change_request",
            {"request_id": request_id},
            handler,
        )

    @server.tool(
        name="list_change_requests",
        description="分页查询变更申请，可按 pending/executed/rejected 等状态筛选。",
    )
    async def list_change_requests_tool(
        ctx: Context,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ToolError("分页参数不合法")

        async def handler(session: AsyncSession, _admin_id: int) -> dict[str, Any]:
            rows, total = await list_change_requests(
                session,
                status=status,
                page=page,
                page_size=page_size,
            )
            return {
                "items": [
                    {
                        **_request_payload(request),
                        "requested_by": request.requested_by,
                        "requested_by_username": username,
                        "created_at": request.created_at.isoformat()
                        if request.created_at
                        else None,
                    }
                    for request, username in rows
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        return await _with_session(
            ctx,
            "list_change_requests",
            {"status": status, "page": page, "page_size": page_size},
            handler,
        )

    @server.tool(name="cancel_change_request", description="发起人取消尚未审批的变更申请。")
    async def cancel_change_request_tool(ctx: Context, request_id: int) -> dict[str, Any]:
        async def handler(session: AsyncSession, admin_id: int) -> dict[str, Any]:
            requester = await session.get(User, admin_id)
            if requester is None:
                raise AppError(401, 40101, "管理员账号不存在")
            request = await cancel_change_request(
                session,
                request_id=request_id,
                requester=requester,
            )
            return _request_payload(request)

        return await _with_session(
            ctx,
            "cancel_change_request",
            {"request_id": request_id},
            handler,
            require_write=True,
        )
