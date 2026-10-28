from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import ERROR_CODE_NOT_FOUND, AppError
from app.db.session import async_session_factory
from app.mcp import auth
from app.models.wordbook import Wordbook
from app.services.import_file import clean_upload_filename, parse_import_file
from app.services.mcp_audit import log_mcp_event
from app.services.mcp_change import (
    create_change_request,
    decode_import_file,
    store_import_upload,
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


async def _require_wordbook(session: AsyncSession, wordbook_id: int) -> None:
    if await session.get(Wordbook, wordbook_id) is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "词书不存在")


def register_import_tools(server: MCPServer) -> None:
    @server.tool(
        name="preview_import",
        description=(
            "解析 base64 编码的 CSV/TSV/TXT/XLSX 文件，返回表头和前若干行，供提交导入申请前确认。"
            "不会写入任何数据。"
        ),
    )
    async def preview_import_tool(
        ctx: Context,
        wordbook_id: int,
        file_name: str,
        file_base64: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise ToolError("limit 必须在 1 到 100 之间")

        admin = await auth.authenticate_admin(ctx.headers)
        client_name, client_ip = auth.client_metadata(ctx.headers)
        async with async_session_factory() as session:
            try:
                safe_name = clean_upload_filename(file_name)
                content = decode_import_file(file_base64)
                await _require_wordbook(session, wordbook_id)
                parsed = parse_import_file(safe_name, content)
            except AppError as exc:
                await log_mcp_event(
                    session,
                    admin_id=admin.id,
                    tool_name="preview_import",
                    outcome="error",
                    params={"wordbook_id": wordbook_id, "file_name": file_name},
                    error_code=exc.code,
                    client_name=client_name,
                    client_ip=client_ip,
                )
                raise ToolError(exc.message) from exc

            await log_mcp_event(
                session,
                admin_id=admin.id,
                tool_name="preview_import",
                outcome="success",
                target_type="wordbook",
                target_id=wordbook_id,
                params={
                    "wordbook_id": wordbook_id,
                    "file_name": safe_name,
                    "file_size": len(content),
                    "total_rows": len(parsed.rows),
                },
                client_name=client_name,
                client_ip=client_ip,
            )
            return {
                "file_name": safe_name,
                "sheet_name": parsed.sheet_name,
                "headers": parsed.headers,
                "rows": parsed.rows[:limit],
                "total_rows": len(parsed.rows),
            }

    @server.tool(
        name="propose_import",
        description=(
            "提交「批量导入单词」申请：上传 base64 文件与列映射，管理员审批后才创建导入任务。"
            "文件最大 10MB。"
        ),
    )
    async def propose_import_tool(
        ctx: Context,
        wordbook_id: int,
        file_name: str,
        file_base64: str,
        mapping: dict[str, int | None],
        reason: str = "",
    ) -> dict[str, Any]:
        admin = await auth.authenticate_admin(ctx.headers)
        if not admin.can_write:
            raise ToolError("该 MCP 令牌只有只读权限，不能提交导入申请")
        client_name, client_ip = auth.client_metadata(ctx.headers)
        async with async_session_factory() as session:
            try:
                safe_name = clean_upload_filename(file_name)
                content = decode_import_file(file_base64)
                await _require_wordbook(session, wordbook_id)
                parse_import_file(safe_name, content)
                upload = await store_import_upload(
                    session,
                    admin_id=admin.id,
                    file_name=safe_name,
                    content=content,
                )
                request = await create_change_request(
                    session,
                    admin_id=admin.id,
                    action_type="word.import",
                    payload={
                        "wordbook_id": wordbook_id,
                        "upload_id": upload.id,
                        "file_name": safe_name,
                        "mapping": mapping,
                    },
                    reason=reason or None,
                    client_name=client_name,
                    client_ip=client_ip,
                )
            except AppError as exc:
                await log_mcp_event(
                    session,
                    admin_id=admin.id,
                    tool_name="propose_import",
                    outcome="error",
                    action_type="word.import",
                    params={"wordbook_id": wordbook_id, "file_name": file_name},
                    error_code=exc.code,
                    client_name=client_name,
                    client_ip=client_ip,
                )
                raise ToolError(exc.message) from exc

            await log_mcp_event(
                session,
                admin_id=admin.id,
                tool_name="propose_import",
                outcome="proposed",
                action_type="word.import",
                target_type="wordbook",
                target_id=wordbook_id,
                params={
                    "wordbook_id": wordbook_id,
                    "file_name": safe_name,
                    "file_size": len(content),
                },
                client_name=client_name,
                client_ip=client_ip,
            )
            return {
                **_request_payload(request),
                "message": "导入申请已提交，请管理员在管理端「MCP 审批」页面确认后才会执行。",
            }
