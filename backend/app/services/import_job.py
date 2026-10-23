from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exception_handlers import ERROR_CODE_NOT_FOUND, AppError
from app.models.import_job import ImportJob
from app.models.wordbook import Wordbook


async def create_import_job(
    session: AsyncSession,
    wordbook_id: int,
    admin_id: int,
    file_name: str,
) -> ImportJob:
    """校验词书后创建 pending 状态的导入任务。"""
    wordbook = await session.get(Wordbook, wordbook_id)
    if wordbook is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "词书不存在")
    job = ImportJob(
        wordbook_id=wordbook_id,
        admin_id=admin_id,
        file_name=file_name,
        status="pending",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_import_job(session: AsyncSession, import_job_id: int) -> ImportJob:
    """按主键读取导入任务。"""
    job = await session.get(ImportJob, import_job_id)
    if job is None:
        raise AppError(404, ERROR_CODE_NOT_FOUND, "导入任务不存在")
    return job
