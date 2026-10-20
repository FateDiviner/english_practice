"""学习数据备份：导出与导入。

导出文件刻意不含任何账号标识（无 user_id / username / password_hash），
只用 wordbook.code + word 两个业务键定位，这样文件才能在账号之间搬运：
换设备、误清缓存、换号注册都能把进度找回来。

导入是**合并**而非覆盖，合并规则与游客转正的 migrate_guest_data 保持一致，
全项目只存在这一套语义。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage
from app.models.record import UserWordRecord
from app.models.session import PracticeSessionRecord
from app.models.user import User
from app.models.word import Word
from app.models.wordbook import WordBook
from app.schemas.backup import (
    BACKUP_FORMAT,
    BACKUP_VERSION,
    BackupFile,
    ImportResult,
)
from app.services import stats_service

MAX_MESSAGES_ON_EXPORT = 200

# 记忆状态强弱：错题 > 已掌握 > 学习中，合并时取更强的一档
_STATUS_RANK = {"learning": 1, "mastered": 2, "wrong": 3}


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        return None
    # 库里是无时区的 DATETIME，导出原样搬运，导入时不要带上时区
    return value.replace(tzinfo=None) if value.tzinfo else value


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _stronger(left: str, right: str) -> str:
    return left if _STATUS_RANK.get(left, 0) >= _STATUS_RANK.get(right, 0) else right


def export_backup(db: Session, user: User) -> BackupFile:
    """导出当前用户的全部学习数据。"""
    books = {book.id: book.code for book in db.scalars(select(WordBook)).all()}

    records = list(
        db.scalars(
            select(UserWordRecord)
            .where(UserWordRecord.user_id == user.id)
            .order_by(UserWordRecord.id)
        ).all()
    )
    # word_id -> (wordbook_id, word)：导出用 wordbook.code 而非 id，
    # 这样文件才能跨账号、跨库搬运
    word_meta = {
        word.id: (word.wordbook_id, word.word)
        for word in db.scalars(select(Word)).all()
    }
    word_records = [
        {
            "wordbook": books.get(word_meta[record.word_id][0], ""),
            "word": word_meta[record.word_id][1],
            "status": record.status,
            "wrong_count": record.wrong_count or 0,
            "right_count": record.right_count or 0,
            "ease_stage": record.ease_stage or 0,
            "last_practiced": (
                record.last_practiced.isoformat() if record.last_practiced else None
            ),
            "next_review_at": (
                record.next_review_at.isoformat() if record.next_review_at else None
            ),
        }
        for record in records
        if record.word_id in word_meta and books.get(word_meta[record.word_id][0])
    ]

    sessions = list(
        db.scalars(
            select(PracticeSessionRecord)
            .where(PracticeSessionRecord.user_id == user.id)
            .order_by(PracticeSessionRecord.id)
        ).all()
    )
    session_rows = [
        {
            "wordbook": books.get(session.wordbook_id, ""),
            "mode": session.mode,
            "total": session.total,
            "correct": session.correct_count,
            "wrong": session.wrong_count,
            "duration_ms": session.duration_ms,
            "practiced_on": session.practiced_on.isoformat(),
        }
        for session in sessions
    ]

    messages = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.user_id == user.id)
            .order_by(ChatMessage.id.desc())
            .limit(MAX_MESSAGES_ON_EXPORT)
        ).all()
    )
    chat_rows = [
        {
            "role": message.role,
            "content": message.content,
            # 原样搬运 JSON 字符串，绝不二次序列化
            "feedback": message.feedback,
            "metadata": message.agent_metadata,
            "created_at": message.created_at.isoformat(),
        }
        for message in reversed(messages)
    ]

    active_code = None
    if user.active_wordbook_id:
        active_code = books.get(user.active_wordbook_id)

    return BackupFile(
        format=BACKUP_FORMAT,
        version=BACKUP_VERSION,
        exported_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        summary={
            "words": len(word_records),
            "sessions": len(session_rows),
            "messages": len(chat_rows),
            "consecutive_days": user.consecutive_days or 0,
        },
        word_records=word_records,
        sessions=session_rows,
        chat_messages=chat_rows,
        consecutive_days=user.consecutive_days or 0,
        last_checkin_date=user.last_checkin_date,
        active_wordbook=active_code,
    )


def import_backup(db: Session, user: User, payload: BackupFile) -> ImportResult:
    """把备份合并进当前账号，全部成功才提交。"""
    if payload.format != BACKUP_FORMAT:
        raise ValueError("format")
    if payload.version != BACKUP_VERSION:
        raise ValueError("version")

    books = {book.code: book.id for book in db.scalars(select(WordBook)).all()}
    word_ids = {
        (word.wordbook_id, word.word): word.id for word in db.scalars(select(Word)).all()
    }

    existing_records = {
        record.word_id: record
        for record in db.scalars(
            select(UserWordRecord).where(UserWordRecord.user_id == user.id)
        ).all()
    }

    records_new = 0
    records_merged = 0
    words_unmatched = 0

    for item in payload.word_records:
        book_id = books.get(item.wordbook)
        word_id = word_ids.get((book_id, item.word)) if book_id is not None else None
        if word_id is None:
            # 词书被删过或词库版本不同，跳过并计数，绝不因此让整个导入失败
            words_unmatched += 1
            continue

        last_practiced = _parse_dt(item.last_practiced)
        next_review_at = _parse_dt(item.next_review_at)
        current = existing_records.get(word_id)
        if current is None:
            record = UserWordRecord(
                user_id=user.id,
                word_id=word_id,
                status=item.status,
                wrong_count=item.wrong_count,
                right_count=item.right_count,
                ease_stage=item.ease_stage,
                last_practiced=last_practiced,
                next_review_at=next_review_at,
            )
            db.add(record)
            existing_records[word_id] = record
            records_new += 1
            continue

        records_merged += 1
        current.wrong_count = max(current.wrong_count or 0, item.wrong_count)
        current.right_count = max(current.right_count or 0, item.right_count)
        current.ease_stage = max(current.ease_stage or 0, item.ease_stage)
        current.status = _stronger(current.status, item.status)
        if last_practiced and (current.last_practiced is None or last_practiced > current.last_practiced):
            current.last_practiced = last_practiced
        if next_review_at and (current.next_review_at is None or next_review_at < current.next_review_at):
            current.next_review_at = next_review_at

    existing_sessions = {
        (
            session.wordbook_id,
            session.mode,
            session.total,
            session.correct_count,
            session.wrong_count,
            session.duration_ms,
            session.practiced_on,
        )
        for session in db.scalars(
            select(PracticeSessionRecord).where(PracticeSessionRecord.user_id == user.id)
        ).all()
    }
    sessions_added = 0
    sessions_skipped = 0
    for item in payload.sessions:
        book_id = books.get(item.wordbook)
        practiced_on = _parse_date(item.practiced_on)
        if book_id is None or practiced_on is None:
            sessions_skipped += 1
            continue
        key = (book_id, item.mode, item.total, item.correct, item.wrong,
               item.duration_ms, practiced_on)
        if key in existing_sessions:
            # practice_sessions 没有自然唯一键，用全字段元组做近似去重，
            # 重复导入同一份备份不会把会话翻倍
            sessions_skipped += 1
            continue
        existing_sessions.add(key)
        db.add(
            PracticeSessionRecord(
                user_id=user.id,
                wordbook_id=book_id,
                mode=item.mode,
                total=item.total,
                correct_count=item.correct,
                wrong_count=item.wrong,
                duration_ms=item.duration_ms,
                practiced_on=practiced_on,
            )
        )
        sessions_added += 1

    existing_messages = {
        (row.role, row.content, row.feedback, row.agent_metadata, row.created_at)
        for row in db.scalars(
            select(ChatMessage).where(ChatMessage.user_id == user.id)
        ).all()
    }
    messages_added = 0
    messages_skipped = 0
    for item in payload.chat_messages:
        created_at = _parse_dt(item.created_at)
        if created_at is None:
            messages_skipped += 1
            continue
        key = (item.role, item.content, item.feedback, item.metadata, created_at)
        if key in existing_messages:
            messages_skipped += 1
            continue
        existing_messages.add(key)
        db.add(
            ChatMessage(
                user_id=user.id,
                role=item.role,
                content=item.content,
                feedback=item.feedback,
                agent_metadata=item.metadata,
                created_at=created_at,
            )
        )
        messages_added += 1

    # 激活词书：当前用户的选择优先，只在尚未选择时用备份补上
    if payload.active_wordbook and user.active_wordbook_id is None:
        book_id = books.get(payload.active_wordbook)
        if book_id is not None:
            user.active_wordbook_id = book_id

    # 连续天数不照搬计数器，按合并后的会话日期重算，与游客转正同一条路径
    db.flush()
    streak, last_on = stats_service.recompute_streak(db, user.id)
    if last_on is not None:
        user.consecutive_days = streak
        user.last_checkin_date = last_on.isoformat()
    db.commit()

    return ImportResult(
        records_new=records_new,
        records_merged=records_merged,
        sessions_added=sessions_added,
        sessions_skipped=sessions_skipped,
        messages_added=messages_added,
        messages_skipped=messages_skipped,
        words_unmatched=words_unmatched,
        consecutive_days=user.consecutive_days or 0,
    )
