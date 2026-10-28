import base64
import binascii
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exception_handlers import (
    ERROR_CODE_BAD_REQUEST,
    ERROR_CODE_CONFLICT,
    ERROR_CODE_FORBIDDEN,
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_VALIDATION,
    AppError,
)
from app.models.mcp import McpChangeRequest, McpImportUpload
from app.models.user import User
from app.schemas.admin_user import UserStatusIn
from app.schemas.import_job import ImportMappingIn
from app.schemas.word import WordCreateIn, WordUpdateIn
from app.schemas.wordbook import WordbookCreateIn, WordbookUpdateIn
from app.services.admin_user import update_user_status
from app.services.import_file import (
    MAX_IMPORT_FILE_BYTES,
    clean_upload_filename,
    ensure_file_size,
)
from app.services.import_job import create_import_job
from app.services.profile.service import get_profile_orchestrator
from app.services.word import create_word, delete_word, update_word
from app.services.wordbook import create_wordbook, delete_wordbook, update_wordbook

PENDING_STATUS = "pending"
MAX_SUMMARY_LENGTH = 255
MAX_REASON_LENGTH = 500


@dataclass(frozen=True)
class ImportExecution:
    import_job_id: int
    file_name: str
    content: bytes
    mapping: dict[str, int | None]


@dataclass(frozen=True)
class ExecutionOutcome:
    result: dict[str, Any]
    background_import: ImportExecution | None = None


@dataclass(frozen=True)
class ActionSpec:
    target_type: str
    prepare: Callable[[dict[str, Any]], tuple[int | None, dict[str, Any]]]
    summarize: Callable[[int | None, dict[str, Any]], str]
    execute: Callable[
        [AsyncSession, int | None, dict[str, Any], User],
        Awaitable[ExecutionOutcome],
    ]


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _validate(schema: type[BaseModel], payload: dict[str, Any]) -> BaseModel:
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        message = str(first.get("msg") or "参数不合法").removeprefix("Value error, ")
        raise AppError(422, ERROR_CODE_VALIDATION, f"参数校验失败：{message}") from exc


def _positive_id(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    try:
        identifier = int(value)
    except (TypeError, ValueError) as exc:
        raise AppError(422, ERROR_CODE_VALIDATION, f"缺少有效的 {key}") from exc
    if identifier <= 0:
        raise AppError(422, ERROR_CODE_VALIDATION, f"缺少有效的 {key}")
    return identifier


def _changed_fields(payload: dict[str, Any]) -> str:
    fields = "、".join(sorted(payload)) or "无"
    return fields[:200]


def _truncate(value: str, length: int) -> str:
    return value if len(value) <= length else f"{value[: length - 3]}..."


def _prepare_wordbook_create(payload: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    data = _validate(WordbookCreateIn, payload).model_dump()
    return None, data


def _prepare_wordbook_update(payload: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    wordbook_id = _positive_id(payload, "wordbook_id")
    data = _validate(WordbookUpdateIn, payload).model_dump(exclude_unset=True)
    data.pop("wordbook_id", None)
    if not data:
        raise AppError(422, ERROR_CODE_VALIDATION, "至少提供一个要更新的字段")
    return wordbook_id, data


def _prepare_wordbook_delete(payload: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    return _positive_id(payload, "wordbook_id"), {}


def _prepare_word_create(payload: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    wordbook_id = _positive_id(payload, "wordbook_id")
    rest = {key: value for key, value in payload.items() if key != "wordbook_id"}
    data = _validate(WordCreateIn, rest).model_dump()
    return wordbook_id, {"wordbook_id": wordbook_id, **data}


def _prepare_word_update(payload: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    word_id = _positive_id(payload, "word_id")
    data = _validate(WordUpdateIn, payload).model_dump(exclude_unset=True)
    data.pop("word_id", None)
    if not data:
        raise AppError(422, ERROR_CODE_VALIDATION, "至少提供一个要更新的字段")
    return word_id, data


def _prepare_word_delete(payload: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    return _positive_id(payload, "word_id"), {}


def _prepare_user_status(payload: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    user_id = _positive_id(payload, "user_id")
    data = _validate(UserStatusIn, payload).model_dump()
    data.pop("user_id", None)
    return user_id, data


def _prepare_profile_refresh(payload: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    return _positive_id(payload, "user_id"), {}


def _prepare_import(payload: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    wordbook_id = _positive_id(payload, "wordbook_id")
    upload_id = _positive_id(payload, "upload_id")
    mapping = _validate(ImportMappingIn, payload.get("mapping") or {}).model_dump()
    file_name = str(payload.get("file_name") or "import.csv")[:255]
    return wordbook_id, {
        "wordbook_id": wordbook_id,
        "upload_id": upload_id,
        "file_name": file_name,
        "mapping": mapping,
    }


async def _execute_wordbook_create(
    session: AsyncSession,
    _target_id: int | None,
    payload: dict[str, Any],
    approver: User,
) -> ExecutionOutcome:
    wordbook = await create_wordbook(session, WordbookCreateIn(**payload), approver.id)
    return ExecutionOutcome(result={"wordbook_id": wordbook.id})


async def _execute_wordbook_update(
    session: AsyncSession,
    target_id: int | None,
    payload: dict[str, Any],
    _approver: User,
) -> ExecutionOutcome:
    if target_id is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "缺少词书 id")
    wordbook = await update_wordbook(session, target_id, WordbookUpdateIn(**payload))
    return ExecutionOutcome(result={"wordbook_id": wordbook.id})


async def _execute_wordbook_delete(
    session: AsyncSession,
    target_id: int | None,
    _payload: dict[str, Any],
    _approver: User,
) -> ExecutionOutcome:
    if target_id is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "缺少词书 id")
    await delete_wordbook(session, target_id)
    return ExecutionOutcome(result={"wordbook_id": target_id, "deleted": True})


async def _execute_word_create(
    session: AsyncSession,
    target_id: int | None,
    payload: dict[str, Any],
    _approver: User,
) -> ExecutionOutcome:
    if target_id is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "缺少词书 id")
    rest = {key: value for key, value in payload.items() if key != "wordbook_id"}
    word = await create_word(session, target_id, WordCreateIn(**rest))
    return ExecutionOutcome(result={"word_id": word.id, "wordbook_id": word.wordbook_id})


async def _execute_word_update(
    session: AsyncSession,
    target_id: int | None,
    payload: dict[str, Any],
    _approver: User,
) -> ExecutionOutcome:
    if target_id is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "缺少单词 id")
    word = await update_word(session, target_id, WordUpdateIn(**payload))
    return ExecutionOutcome(result={"word_id": word.id})


async def _execute_word_delete(
    session: AsyncSession,
    target_id: int | None,
    _payload: dict[str, Any],
    _approver: User,
) -> ExecutionOutcome:
    if target_id is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "缺少单词 id")
    await delete_word(session, target_id)
    return ExecutionOutcome(result={"word_id": target_id, "deleted": True})


async def _execute_user_status(
    session: AsyncSession,
    target_id: int | None,
    payload: dict[str, Any],
    approver: User,
) -> ExecutionOutcome:
    if target_id is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "缺少用户 id")
    user = await update_user_status(session, approver.id, target_id, payload["status"])
    return ExecutionOutcome(result={"user_id": user.id, "status": user.status})


async def _execute_profile_refresh(
    session: AsyncSession,
    target_id: int | None,
    _payload: dict[str, Any],
    _approver: User,
) -> ExecutionOutcome:
    if target_id is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "缺少用户 id")
    await get_profile_orchestrator().analyze(session, target_id)
    return ExecutionOutcome(result={"user_id": target_id})


async def _execute_import(
    session: AsyncSession,
    target_id: int | None,
    payload: dict[str, Any],
    approver: User,
) -> ExecutionOutcome:
    if target_id is None:
        raise AppError(422, ERROR_CODE_VALIDATION, "缺少词书 id")
    upload = await session.get(McpImportUpload, int(payload["upload_id"]))
    if upload is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "导入文件不存在或已清理")
    if upload.consumed_at is not None:
        raise AppError(409, ERROR_CODE_CONFLICT, "导入文件已被使用")

    mapping = ImportMappingIn.model_validate(payload["mapping"]).model_dump()
    job = await create_import_job(session, target_id, approver.id, upload.file_name)
    upload.consumed_at = _utcnow()
    await session.commit()
    return ExecutionOutcome(
        result={"import_job_id": job.id, "wordbook_id": target_id},
        background_import=ImportExecution(
            import_job_id=job.id,
            file_name=upload.file_name,
            content=upload.content,
            mapping=mapping,
        ),
    )


ACTIONS: dict[str, ActionSpec] = {
    "wordbook.create": ActionSpec(
        target_type="wordbook",
        prepare=_prepare_wordbook_create,
        summarize=lambda _target, data: f"创建词书「{data['name']}」",
        execute=_execute_wordbook_create,
    ),
    "wordbook.update": ActionSpec(
        target_type="wordbook",
        prepare=_prepare_wordbook_update,
        summarize=lambda target, data: f"更新词书 #{target}：{_changed_fields(data)}",
        execute=_execute_wordbook_update,
    ),
    "wordbook.delete": ActionSpec(
        target_type="wordbook",
        prepare=_prepare_wordbook_delete,
        summarize=lambda target, _data: f"删除词书 #{target}",
        execute=_execute_wordbook_delete,
    ),
    "word.create": ActionSpec(
        target_type="wordbook",
        prepare=_prepare_word_create,
        summarize=lambda _target, data: (
            f"在词书 #{data['wordbook_id']} 新增单词「{data['spelling']}」"
        ),
        execute=_execute_word_create,
    ),
    "word.update": ActionSpec(
        target_type="word",
        prepare=_prepare_word_update,
        summarize=lambda target, data: f"更新单词 #{target}：{_changed_fields(data)}",
        execute=_execute_word_update,
    ),
    "word.delete": ActionSpec(
        target_type="word",
        prepare=_prepare_word_delete,
        summarize=lambda target, _data: f"删除单词 #{target}",
        execute=_execute_word_delete,
    ),
    "user.status": ActionSpec(
        target_type="user",
        prepare=_prepare_user_status,
        summarize=lambda target, data: f"将用户 #{target} 状态改为 {data['status']}",
        execute=_execute_user_status,
    ),
    "user.profile_refresh": ActionSpec(
        target_type="user",
        prepare=_prepare_profile_refresh,
        summarize=lambda target, _data: f"重新生成用户 #{target} 的学情画像",
        execute=_execute_profile_refresh,
    ),
    "word.import": ActionSpec(
        target_type="wordbook",
        prepare=_prepare_import,
        summarize=lambda _target, data: (
            f"向词书 #{data['wordbook_id']} 导入文件「{data['file_name']}」"
        ),
        execute=_execute_import,
    ),
}


def decode_import_file(file_base64: str) -> bytes:
    """解码 MCP 传入的 base64 文件内容，并在解码前粗估体积。"""
    if not file_base64:
        raise AppError(422, ERROR_CODE_VALIDATION, "导入文件为空")
    if len(file_base64) > (MAX_IMPORT_FILE_BYTES * 4) // 3 + 16:
        raise AppError(422, ERROR_CODE_VALIDATION, "导入文件不能超过 10MB")
    try:
        content = base64.b64decode(file_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AppError(422, ERROR_CODE_VALIDATION, "文件内容不是有效的 base64") from exc
    ensure_file_size(content)
    return content


async def store_import_upload(
    session: AsyncSession,
    *,
    admin_id: int,
    file_name: str,
    content: bytes,
) -> McpImportUpload:
    upload = McpImportUpload(
        file_name=clean_upload_filename(file_name),
        content=content,
        size=len(content),
        uploaded_by=admin_id,
    )
    session.add(upload)
    await session.commit()
    await session.refresh(upload)
    return upload


async def create_change_request(
    session: AsyncSession,
    *,
    admin_id: int,
    action_type: str,
    payload: dict[str, Any],
    reason: str | None = None,
    client_name: str | None = None,
    client_ip: str | None = None,
) -> McpChangeRequest:
    """校验写参数并生成待审批申请；此步骤不会改动业务数据。"""
    spec = ACTIONS.get(action_type)
    if spec is None:
        raise AppError(400, ERROR_CODE_BAD_REQUEST, f"不支持的变更类型：{action_type}")

    target_id, normalized = spec.prepare(dict(payload))
    summary = _truncate(spec.summarize(target_id, normalized), MAX_SUMMARY_LENGTH)
    request = McpChangeRequest(
        action_type=action_type,
        target_type=spec.target_type,
        target_id=target_id,
        payload=normalized,
        summary=summary,
        reason=_truncate(reason, MAX_REASON_LENGTH) if reason else None,
        status=PENDING_STATUS,
        requested_by=admin_id,
        client_name=(client_name or None) and client_name[:100],
        client_ip=(client_ip or None) and client_ip[:45],
        expires_at=_utcnow() + timedelta(minutes=get_settings().MCP_CONFIRM_TTL_MINUTES),
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def expire_stale(session: AsyncSession) -> int:
    """把过期的待审批申请标记为 expired。"""
    result = await session.execute(
        update(McpChangeRequest)
        .where(
            McpChangeRequest.status == PENDING_STATUS,
            McpChangeRequest.expires_at <= _utcnow(),
        )
        .values(status="expired"),
    )
    await session.commit()
    return int(result.rowcount or 0)


async def list_change_requests(
    session: AsyncSession,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[McpChangeRequest, str]], int]:
    await expire_stale(session)
    conditions = []
    if status:
        conditions.append(McpChangeRequest.status == status)

    rows = await session.execute(
        select(McpChangeRequest, User.username)
        .join(User, User.id == McpChangeRequest.requested_by)
        .where(*conditions)
        .order_by(McpChangeRequest.created_at.desc(), McpChangeRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size),
    )
    total = (
        await session.scalar(
            select(func.count(McpChangeRequest.id)).where(*conditions),
        )
        or 0
    )
    return [(request, username) for request, username in rows], int(total)


async def get_change_request(
    session: AsyncSession,
    request_id: int,
) -> tuple[McpChangeRequest, str]:
    row = await session.execute(
        select(McpChangeRequest, User.username)
        .join(User, User.id == McpChangeRequest.requested_by)
        .where(McpChangeRequest.id == request_id),
    )
    found = row.one_or_none()
    if found is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "变更申请不存在")
    return found[0], found[1]


async def _mark_failed(
    session: AsyncSession,
    request: McpChangeRequest,
    message: str,
) -> None:
    request.status = "failed"
    request.error_message = _truncate(message, 500)
    await session.commit()


async def approve_change_request(
    session: AsyncSession,
    *,
    request_id: int,
    approver: User,
) -> tuple[McpChangeRequest, ExecutionOutcome]:
    """管理员审批通过后执行变更；状态流转用条件更新防止并发重复执行。"""
    now = _utcnow()
    claimed = await session.execute(
        update(McpChangeRequest)
        .where(
            McpChangeRequest.id == request_id,
            McpChangeRequest.status == PENDING_STATUS,
            McpChangeRequest.expires_at > now,
        )
        .values(status="approved", approved_by=approver.id, approved_at=now),
    )
    claimed_rows = int(claimed.rowcount or 0)
    await session.commit()

    request = await session.get(McpChangeRequest, request_id)
    if request is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "变更申请不存在")

    if claimed_rows != 1:
        if request.status == PENDING_STATUS and request.expires_at <= now:
            request.status = "expired"
            await session.commit()
            raise AppError(409, ERROR_CODE_CONFLICT, "变更申请已过期")
        raise AppError(409, ERROR_CODE_CONFLICT, "该申请已被处理")

    spec = ACTIONS.get(request.action_type)
    if spec is None:
        await _mark_failed(session, request, "不支持的变更类型")
        raise AppError(400, ERROR_CODE_BAD_REQUEST, "不支持的变更类型")

    try:
        outcome = await spec.execute(session, request.target_id, request.payload, approver)
    except AppError as exc:
        await _mark_failed(session, request, exc.message)
        raise
    except Exception:
        await _mark_failed(session, request, "执行失败，请查看服务端日志")
        raise

    request.status = "executed"
    request.result = outcome.result
    request.error_message = None
    request.executed_at = _utcnow()
    await session.commit()
    await session.refresh(request)
    return request, outcome


async def reject_change_request(
    session: AsyncSession,
    *,
    request_id: int,
    approver: User,
    reason: str | None,
) -> McpChangeRequest:
    now = _utcnow()
    result = await session.execute(
        update(McpChangeRequest)
        .where(
            McpChangeRequest.id == request_id,
            McpChangeRequest.status == PENDING_STATUS,
        )
        .values(
            status="rejected",
            approved_by=approver.id,
            approved_at=now,
            error_message=_truncate(reason, MAX_REASON_LENGTH) if reason else None,
        ),
    )
    await session.commit()
    if result.rowcount != 1:
        request = await session.get(McpChangeRequest, request_id)
        if request is None:
            raise AppError(404, ERROR_CODE_NOT_FOUND, "变更申请不存在")
        raise AppError(409, ERROR_CODE_CONFLICT, "该申请已被处理")
    return (await get_change_request(session, request_id))[0]


async def cancel_change_request(
    session: AsyncSession,
    *,
    request_id: int,
    requester: User,
) -> McpChangeRequest:
    result = await session.execute(
        update(McpChangeRequest)
        .where(
            McpChangeRequest.id == request_id,
            McpChangeRequest.status == PENDING_STATUS,
            McpChangeRequest.requested_by == requester.id,
        )
        .values(status="cancelled", executed_at=_utcnow(), error_message="发起人已取消"),
    )
    await session.commit()
    if result.rowcount != 1:
        request = await session.get(McpChangeRequest, request_id)
        if request is None:
            raise AppError(404, ERROR_CODE_NOT_FOUND, "变更申请不存在")
        if request.requested_by != requester.id:
            raise AppError(403, ERROR_CODE_FORBIDDEN, "只能取消自己发起的申请")
        raise AppError(409, ERROR_CODE_CONFLICT, "该申请已被处理")
    return (await get_change_request(session, request_id))[0]
