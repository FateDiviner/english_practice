from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.core.exception_handlers import (
    ERROR_CODE_NOT_FOUND,
    ERROR_CODE_VALIDATION,
    AppError,
)
from app.db.session import get_session
from app.models.user import User
from app.models.wordbook import Wordbook
from app.schemas.common import ApiResponse
from app.schemas.import_job import (
    ImportJobCreateOut,
    ImportJobErrorOut,
    ImportJobOut,
    ImportMappingIn,
    ImportPreviewOut,
)
from app.services.import_file import (
    MAX_IMPORT_FILE_BYTES,
    clean_upload_filename,
    ensure_file_size,
    parse_import_file,
)
from app.services.import_job import create_import_job, get_import_job
from app.services.import_worker import process_import_job

router = APIRouter(
    prefix="/admin",
    tags=["admin-import"],
    dependencies=[Depends(require_admin)],
)


async def _read_upload(upload: UploadFile) -> tuple[str, bytes]:
    filename = clean_upload_filename(upload.filename)
    content = await upload.read(MAX_IMPORT_FILE_BYTES + 1)
    await upload.close()
    ensure_file_size(content)
    if len(content) > MAX_IMPORT_FILE_BYTES:
        raise AppError(422, ERROR_CODE_VALIDATION, "导入文件不能超过 10MB")
    return filename, content


def _parse_mapping(raw_mapping: str) -> ImportMappingIn:
    try:
        return ImportMappingIn.model_validate_json(raw_mapping)
    except ValidationError as exc:
        raise AppError(422, ERROR_CODE_VALIDATION, "列映射格式不正确") from exc


async def _require_wordbook(session: AsyncSession, wordbook_id: int) -> None:
    if await session.get(Wordbook, wordbook_id) is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "词书不存在")


@router.post(
    "/wordbooks/{wordbook_id}/import/preview",
    response_model=ApiResponse[ImportPreviewOut],
)
async def preview_import_endpoint(
    wordbook_id: int,
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[ImportPreviewOut]:
    """解析上传文件并返回表头和前 20 行预览。"""
    filename, content = await _read_upload(file)
    await _require_wordbook(session, wordbook_id)
    parsed = parse_import_file(filename, content)
    return ApiResponse[ImportPreviewOut](
        code=0,
        message="ok",
        data=ImportPreviewOut(
            file_name=filename,
            sheet_name=parsed.sheet_name,
            headers=parsed.headers,
            rows=parsed.rows[:20],
            total_rows=len(parsed.rows),
        ),
    )


@router.post(
    "/wordbooks/{wordbook_id}/import",
    response_model=ApiResponse[ImportJobCreateOut],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_import_endpoint(
    wordbook_id: int,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    mapping: Annotated[str, Form()],
    current_admin: Annotated[User, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[ImportJobCreateOut]:
    """创建导入任务并交由后台任务处理。"""
    parsed_mapping = _parse_mapping(mapping)
    filename, content = await _read_upload(file)
    job = await create_import_job(session, wordbook_id, current_admin.id, filename)
    background_tasks.add_task(
        process_import_job,
        job.id,
        filename,
        content,
        parsed_mapping.model_dump(),
    )
    return ApiResponse[ImportJobCreateOut](
        code=0,
        message="ok",
        data=ImportJobCreateOut(import_job_id=job.id),
    )


@router.get("/import-jobs/{import_job_id}", response_model=ApiResponse[ImportJobOut])
async def get_import_job_endpoint(
    import_job_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[ImportJobOut]:
    """返回导入任务状态、计数和失败行明细。"""
    job = await get_import_job(session, import_job_id)
    errors = [ImportJobErrorOut(**error) for error in (job.error_detail or [])]
    return ApiResponse[ImportJobOut](
        code=0,
        message="ok",
        data=ImportJobOut(
            id=job.id,
            status=job.status,
            total_rows=job.total_rows,
            success_rows=job.success_rows,
            failed_rows=job.failed_rows,
            errors=errors,
        ),
    )
