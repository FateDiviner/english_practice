from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import AppError
from app.db.session import async_session_factory
from app.mcp import auth
from app.services.admin_stats import get_admin_overview
from app.services.admin_user import get_user_stats, list_users
from app.services.import_job import get_import_job
from app.services.mcp_audit import log_mcp_event
from app.services.word import list_words
from app.services.wordbook import list_wordbooks

ReadHandler = Callable[[AsyncSession], Awaitable[dict[str, Any]]]


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _pagination(page: int, page_size: int) -> tuple[int, int]:
    if page < 1:
        raise ToolError("page 必须大于等于 1")
    if page_size < 1 or page_size > 100:
        raise ToolError("page_size 必须在 1 到 100 之间")
    return page, page_size


async def _run_read(
    ctx: Context,
    tool_name: str,
    params: dict[str, Any],
    handler: ReadHandler,
) -> dict[str, Any]:
    admin = await auth.authenticate_admin(ctx.headers)
    client_name, client_ip = auth.client_metadata(ctx.headers)
    async with async_session_factory() as session:
        try:
            data = await handler(session)
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


def register_read_tools(server: MCPServer) -> None:
    @server.tool(name="admin_overview", description="返回后台概览：用户数、词书数、今日练习量等。")
    async def admin_overview_tool(ctx: Context) -> dict[str, Any]:
        return await _run_read(
            ctx,
            "admin_overview",
            {},
            lambda session: get_admin_overview(session),
        )

    @server.tool(
        name="list_users",
        description="分页查询用户，支持按用户名/邮箱关键词和状态（active/disabled）筛选。",
    )
    async def list_users_tool(
        ctx: Context,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        page, page_size = _pagination(page, page_size)
        if status not in (None, "active", "disabled"):
            raise ToolError("status 只能是 active 或 disabled")
        params = {
            "page": page,
            "page_size": page_size,
            "keyword": keyword,
            "status": status,
        }

        async def handler(session: AsyncSession) -> dict[str, Any]:
            rows, total = await list_users(
                session,
                page=page,
                page_size=page_size,
                keyword=keyword.strip() if keyword else None,
                status=status,
            )
            return {
                "items": [
                    {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                        "status": user.status,
                        "created_at": _iso(user.created_at),
                        "total_practiced": total_practiced,
                    }
                    for user, total_practiced in rows
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        return await _run_read(ctx, "list_users", params, handler)

    @server.tool(name="get_user_stats", description="返回指定用户的学习概览统计。")
    async def get_user_stats_tool(ctx: Context, user_id: int) -> dict[str, Any]:
        async def handler(session: AsyncSession) -> dict[str, Any]:
            stats = await get_user_stats(session, user_id)
            return {
                "user_id": user_id,
                "total_practiced": stats.total_practiced,
                "accuracy": stats.accuracy,
                "streak_days": stats.streak_days,
                "mastered_words": stats.mastered_words,
                "wrong_words_count": stats.wrong_words_count,
            }

        return await _run_read(ctx, "get_user_stats", {"user_id": user_id}, handler)

    @server.tool(name="list_wordbooks", description="分页查询词书及其单词数量。")
    async def list_wordbooks_tool(
        ctx: Context,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        page, page_size = _pagination(page, page_size)
        params = {"page": page, "page_size": page_size}

        async def handler(session: AsyncSession) -> dict[str, Any]:
            rows, total = await list_wordbooks(session, page, page_size)
            return {
                "items": [
                    {
                        "id": wordbook.id,
                        "name": wordbook.name,
                        "description": wordbook.description,
                        "level": wordbook.level,
                        "status": wordbook.status,
                        "word_count": word_count,
                        "created_at": _iso(wordbook.created_at),
                    }
                    for wordbook, word_count in rows
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        return await _run_read(ctx, "list_wordbooks", params, handler)

    @server.tool(name="list_words", description="分页查询指定词书内的单词。")
    async def list_words_tool(
        ctx: Context,
        wordbook_id: int,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> dict[str, Any]:
        page, page_size = _pagination(page, page_size)
        params = {
            "wordbook_id": wordbook_id,
            "page": page,
            "page_size": page_size,
            "keyword": keyword,
        }

        async def handler(session: AsyncSession) -> dict[str, Any]:
            words, total = await list_words(
                session,
                wordbook_id,
                page,
                page_size,
                keyword=keyword.strip() if keyword else None,
            )
            return {
                "items": [
                    {
                        "id": word.id,
                        "spelling": word.spelling,
                        "phonetic_uk": word.phonetic_uk,
                        "phonetic_us": word.phonetic_us,
                        "meaning_cn": word.meaning_cn,
                        "part_of_speech": word.part_of_speech,
                        "sort_order": word.sort_order,
                    }
                    for word in words
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        return await _run_read(ctx, "list_words", params, handler)

    @server.tool(name="get_import_job", description="查询导入任务的进度与失败行明细。")
    async def get_import_job_tool(ctx: Context, import_job_id: int) -> dict[str, Any]:
        async def handler(session: AsyncSession) -> dict[str, Any]:
            job = await get_import_job(session, import_job_id)
            return {
                "id": job.id,
                "wordbook_id": job.wordbook_id,
                "file_name": job.file_name,
                "status": job.status,
                "total_rows": job.total_rows,
                "success_rows": job.success_rows,
                "failed_rows": job.failed_rows,
                "errors": job.error_detail or [],
            }

        return await _run_read(
            ctx,
            "get_import_job",
            {"import_job_id": import_job_id},
            handler,
        )
