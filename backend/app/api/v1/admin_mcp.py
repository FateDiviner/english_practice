from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.db.session import get_session
from app.models.mcp import McpChangeRequest
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.mcp import McpChangeListOut, McpChangeOut, RejectChangeIn
from app.services.import_worker import process_import_job
from app.services.mcp_audit import log_mcp_event
from app.services.mcp_change import (
    approve_change_request,
    get_change_request,
    list_change_requests,
    reject_change_request,
)

router = APIRouter(
    prefix="/admin/mcp-changes",
    tags=["admin-mcp"],
    dependencies=[Depends(require_admin)],
)

ChangeStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "executed",
    "failed",
    "expired",
    "cancelled",
]


def _to_out(request: McpChangeRequest, username: str | None = None) -> McpChangeOut:
    return McpChangeOut(
        id=request.id,
        action_type=request.action_type,
        target_type=request.target_type,
        target_id=request.target_id,
        payload=request.payload or {},
        summary=request.summary,
        reason=request.reason,
        status=request.status,
        requested_by=request.requested_by,
        requested_by_username=username,
        approved_by=request.approved_by,
        client_name=request.client_name,
        result=request.result,
        error_message=request.error_message,
        created_at=request.created_at,
        expires_at=request.expires_at,
        approved_at=request.approved_at,
        executed_at=request.executed_at,
    )


@router.get("", response_model=ApiResponse[McpChangeListOut])
async def list_change_requests_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[ChangeStatus | None, Query()] = None,
) -> ApiResponse[McpChangeListOut]:
    """分页返回 MCP 变更申请，可按状态筛选。"""
    rows, total = await list_change_requests(
        session,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ApiResponse[McpChangeListOut](
        code=0,
        message="ok",
        data=McpChangeListOut(
            items=[_to_out(request, username) for request, username in rows],
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


@router.get("/{request_id}", response_model=ApiResponse[McpChangeOut])
async def get_change_request_endpoint(
    request_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[McpChangeOut]:
    """返回单条变更申请及执行结果。"""
    request, username = await get_change_request(session, request_id)
    return ApiResponse[McpChangeOut](code=0, message="ok", data=_to_out(request, username))


@router.post("/{request_id}/approve", response_model=ApiResponse[McpChangeOut])
async def approve_change_request_endpoint(
    request_id: int,
    background_tasks: BackgroundTasks,
    current_admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[McpChangeOut]:
    """管理员确认后执行业务变更；导入任务转入后台处理。"""
    request, outcome = await approve_change_request(
        session,
        request_id=request_id,
        approver=current_admin,
    )
    if outcome.background_import is not None:
        background = outcome.background_import
        background_tasks.add_task(
            process_import_job,
            background.import_job_id,
            background.file_name,
            background.content,
            background.mapping,
        )
    detail, username = await get_change_request(session, request.id)
    await log_mcp_event(
        session,
        admin_id=current_admin.id,
        tool_name="admin_approve_change",
        outcome="approved",
        action_type=detail.action_type,
        target_type=detail.target_type,
        target_id=detail.target_id,
        params={"request_id": request_id},
    )
    return ApiResponse[McpChangeOut](code=0, message="ok", data=_to_out(detail, username))


@router.post("/{request_id}/reject", response_model=ApiResponse[McpChangeOut])
async def reject_change_request_endpoint(
    request_id: int,
    payload: RejectChangeIn,
    current_admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[McpChangeOut]:
    """驳回变更申请，可记录原因。"""
    await reject_change_request(
        session,
        request_id=request_id,
        approver=current_admin,
        reason=payload.reason,
    )
    request, username = await get_change_request(session, request_id)
    await log_mcp_event(
        session,
        admin_id=current_admin.id,
        tool_name="admin_reject_change",
        outcome="rejected",
        action_type=request.action_type,
        target_type=request.target_type,
        target_id=request.target_id,
        params={"request_id": request_id},
    )
    return ApiResponse[McpChangeOut](code=0, message="ok", data=_to_out(request, username))
