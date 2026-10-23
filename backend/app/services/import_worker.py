import logging
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.import_job import ImportJob
from app.models.word import Word
from app.services.import_file import (
    ImportRowError,
    ParsedWordRow,
    parse_import_file,
    parse_word_row,
    row_content_preview,
)

logger = logging.getLogger(__name__)


async def _insert_word(
    session: AsyncSession,
    wordbook_id: int,
    parsed_row: ParsedWordRow,
) -> str | None:
    """在保存点中插入一行，数据库冲突时只影响当前行。"""
    try:
        async with session.begin_nested():
            session.add(Word(wordbook_id=wordbook_id, **asdict(parsed_row)))
            await session.flush()
        return None
    except IntegrityError:
        return "同词书内 spelling 已存在"


async def _load_existing_spellings(session: AsyncSession, wordbook_id: int) -> set[str]:
    values = await session.scalars(select(Word.spelling).where(Word.wordbook_id == wordbook_id))
    return {str(value).casefold() for value in values}


async def _process_rows(
    session: AsyncSession,
    job: ImportJob,
    file_name: str,
    content: bytes,
    mapping: dict,
) -> None:
    parsed_file = parse_import_file(file_name, content)
    job.total_rows = len(parsed_file.rows)
    await session.commit()

    existing = await _load_existing_spellings(session, job.wordbook_id)
    seen: set[str] = set()
    errors: list[dict] = []
    success_rows = 0

    for row_number, row in enumerate(parsed_file.rows, start=2):
        try:
            parsed_row = parse_word_row(row, mapping)
        except ImportRowError as exc:
            errors.append(
                {
                    "row": row_number,
                    "content": row_content_preview(row),
                    "reason": str(exc),
                }
            )
            continue

        key = parsed_row.spelling.casefold()
        if key in existing or key in seen:
            errors.append(
                {
                    "row": row_number,
                    "content": row_content_preview(row),
                    "reason": "同词书内 spelling 已存在",
                }
            )
            continue

        insert_error = await _insert_word(session, job.wordbook_id, parsed_row)
        if insert_error:
            errors.append(
                {
                    "row": row_number,
                    "content": row_content_preview(row),
                    "reason": insert_error,
                }
            )
            continue
        seen.add(key)
        success_rows += 1

    job.success_rows = success_rows
    job.failed_rows = len(errors)
    job.error_detail = errors or None
    job.status = "done"
    await session.commit()


async def process_import_job(
    job_id: int,
    file_name: str,
    content: bytes,
    mapping: dict[str, int | None],
) -> None:
    """后台解析文件并逐行导入，失败行写入 JSON 明细。"""
    async with async_session_factory() as session:
        job = await session.get(ImportJob, job_id)
        if job is None:
            return
        try:
            job.status = "processing"
            await session.commit()
            await _process_rows(session, job, file_name, content, mapping)
        except Exception:
            await session.rollback()
            logger.exception("Import job %s failed", job_id)
            job = await session.get(ImportJob, job_id)
            if job is None:
                return
            job.status = "failed"
            job.error_detail = [
                {
                    "row": 0,
                    "content": file_name,
                    "reason": "文件处理失败，请检查文件格式与列映射",
                }
            ]
            await session.commit()
