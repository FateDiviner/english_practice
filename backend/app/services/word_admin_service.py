"""管理端词库服务：查询、增改、下架、批量导入与导出。

两条设计原则：
1. **校验先行**——批量导入先用 core 的 word_validator 跑完整校验，
   任一条不通过则整批不写库，绝不「先入库再修」
2. **软删除优先**——下架（status=archived）是默认，物理删除只在零用户引用时开放，
   因为 ON DELETE CASCADE 会连带清空用户的练习记录
"""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.schemas.admin import (
    ImportResult,
    ValidationIssueOut,
    WordAdminOut,
    WordPage,
    WordbookAdminOut,
    WordbookUpdateRequest,
    WordbookUpsertRequest,
    WordUpsertRequest,
)
from app.services import audit_service
from app.services.admin_errors import AdminError
from app.constants import STATUS_ACTIVE, STATUS_ARCHIVED
from app.models.record import UserWordRecord
from app.models.user import User
from app.models.word import Word
from app.models.wordbook import WordBook
from app.services.word_validator import validate_batch, validate_word

WORD_FIELDS = ("word", "phonetic", "translation", "example_en", "example_cn")


def _active_user_count(db: Session, wordbook_id: int) -> int:
    return (
        db.scalar(
            select(func.count(User.id)).where(User.active_wordbook_id == wordbook_id)
        )
        or 0
    )


def _archived_word_count(db: Session, wordbook_id: int) -> int:
    return (
        db.scalar(
            select(func.count(Word.id)).where(
                Word.wordbook_id == wordbook_id,
                Word.status == STATUS_ARCHIVED,
            )
        )
        or 0
    )


def _active_word_count(db: Session, wordbook_id: int) -> int:
    return (
        db.scalar(
            select(func.count(Word.id)).where(
                Word.wordbook_id == wordbook_id,
                Word.status == STATUS_ACTIVE,
            )
        )
        or 0
    )


def _referenced_word_count(db: Session, word_ids: list[int]) -> int:
    """有多少用户的练习记录指向这些词——决定能不能物理删除。"""
    if not word_ids:
        return 0
    return (
        db.scalar(
            select(func.count(UserWordRecord.id)).where(
                UserWordRecord.word_id.in_(word_ids)
            )
        )
        or 0
    )


def to_wordbook_out(db: Session, book: WordBook) -> WordbookAdminOut:
    return WordbookAdminOut(
        id=book.id,
        code=book.code,
        title=book.title,
        description=book.description,
        difficulty=book.difficulty,
        status=book.status,
        total_words=book.total_words or 0,
        archived_words=_archived_word_count(db, book.id),
        active_users=_active_user_count(db, book.id),
    )


def to_word_out(word: Word) -> WordAdminOut:
    return WordAdminOut(
        id=word.id,
        word=word.word,
        phonetic=word.phonetic,
        translation=word.translation,
        example_en=word.example_en,
        example_cn=word.example_cn,
        sequence=word.sequence,
        status=word.status,
    )


def list_wordbooks(db: Session) -> list[WordbookAdminOut]:
    """全部词书，含已下架的——管理端必须看得见自己下架过什么。"""
    books = db.scalars(select(WordBook).order_by(WordBook.id)).all()
    return [to_wordbook_out(db, book) for book in books]


def create_wordbook(
    db: Session, actor: User, payload: WordbookUpsertRequest, request: Request | None = None
) -> WordBook:
    if db.scalar(select(WordBook.id).where(WordBook.code == payload.code)) is not None:
        raise AdminError("词书 code 已存在", status_code=409)

    book = WordBook(
        code=payload.code,
        title=payload.title,
        description=payload.description,
        difficulty=payload.difficulty,
        status=STATUS_ACTIVE,
        total_words=0,
    )
    db.add(book)
    db.flush()
    audit_service.record(
        db,
        actor=actor,
        action="wordbook.create",
        target_type="wordbook",
        target_id=book.id,
        detail={"code": book.code, "title": book.title},
        affected_rows=1,
        request=request,
    )
    db.commit()
    db.refresh(book)
    return book


def update_wordbook(
    db: Session,
    actor: User,
    book_id: int,
    payload: WordbookUpdateRequest,
    request: Request | None = None,
) -> WordBook:
    book = db.get(WordBook, book_id)
    if book is None:
        raise AdminError("词书不存在", status_code=404)
    if not any(
        value is not None
        for value in (payload.title, payload.description, payload.difficulty, payload.status)
    ):
        raise AdminError("没有需要更新的字段", status_code=400)

    detail: dict[str, object] = {"code": book.code}
    if payload.title is not None and payload.title != book.title:
        detail["title"] = f"{book.title} -> {payload.title}"
        book.title = payload.title
    if payload.description is not None:
        book.description = payload.description
    if payload.difficulty is not None:
        book.difficulty = payload.difficulty

    if payload.status is not None and payload.status != book.status:
        book.status = payload.status
        action = "wordbook.restore" if payload.status == STATUS_ACTIVE else "wordbook.archive"
        detail["status"] = payload.status
        audit_service.record(
            db,
            actor=actor,
            action=action,
            target_type="wordbook",
            target_id=book.id,
            detail=detail,
            affected_rows=1,
            request=request,
        )

    if len(detail) > 1:  # 除 code 外还有其它变更
        audit_service.record(
            db,
            actor=actor,
            action="wordbook.update",
            target_type="wordbook",
            target_id=book.id,
            detail=detail,
            affected_rows=1,
            request=request,
        )
    db.commit()
    db.refresh(book)
    return book


def list_words(
    db: Session,
    book_id: int,
    *,
    search: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> WordPage:
    filters = [Word.wordbook_id == book_id]
    if search:
        filters.append(Word.word.ilike(f"%{search.strip()}%"))
    if status:
        filters.append(Word.status == status)

    total = db.scalar(select(func.count(Word.id)).where(*filters))
    rows = db.scalars(
        select(Word)
        .where(*filters)
        .order_by(Word.sequence, Word.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return WordPage(total=total or 0, items=[to_word_out(row) for row in rows])


def create_word(
    db: Session, actor: User, book_id: int, payload: WordUpsertRequest, request: Request | None = None
) -> Word:
    book = db.get(WordBook, book_id)
    if book is None:
        raise AdminError("词书不存在", status_code=404)

    item = {field: getattr(payload, field) for field in WORD_FIELDS}
    validation = validate_word(item)
    if not validation.ok:
        raise AdminError(
            "；".join(issue.message for issue in validation.issues),
            status_code=422,
        )

    exists = db.scalar(
        select(Word.id).where(
            Word.wordbook_id == book_id,
            func.lower(Word.word) == payload.word.strip().lower(),
        )
    )
    if exists is not None:
        raise AdminError("该词已存在于本词书", status_code=409)

    sequence = (
        db.scalar(select(func.coalesce(func.max(Word.sequence), -1)).where(Word.wordbook_id == book_id))
        or 0
    ) + 1
    word = Word(
        wordbook_id=book_id,
        word=payload.word.strip(),
        phonetic=payload.phonetic,
        translation=payload.translation,
        example_en=payload.example_en,
        example_cn=payload.example_cn,
        sequence=sequence,
        status=STATUS_ACTIVE,
    )
    db.add(word)
    db.flush()
    _refresh_total_words(db, book)

    audit_service.record(
        db,
        actor=actor,
        action="word.create",
        target_type="word",
        target_id=word.id,
        detail={"book": book.code, "word": word.word},
        affected_rows=1,
        request=request,
    )
    db.commit()
    db.refresh(word)
    return word


def update_word(
    db: Session, actor: User, word_id: int, payload: WordUpsertRequest, request: Request | None = None
) -> Word:
    word = db.get(Word, word_id)
    if word is None:
        raise AdminError("词条不存在", status_code=404)

    item = {field: getattr(payload, field) for field in WORD_FIELDS}
    validation = validate_word(item)
    if not validation.ok:
        raise AdminError(
            "；".join(issue.message for issue in validation.issues),
            status_code=422,
        )

    word.word = payload.word.strip()
    word.phonetic = payload.phonetic
    word.translation = payload.translation
    word.example_en = payload.example_en
    word.example_cn = payload.example_cn
    # 重新编辑意味着要它回来
    word.status = STATUS_ACTIVE
    book = db.get(WordBook, word.wordbook_id)
    if book is not None:
        _refresh_total_words(db, book)

    audit_service.record(
        db,
        actor=actor,
        action="word.update",
        target_type="word",
        target_id=word.id,
        detail={"word": word.word},
        affected_rows=1,
        request=request,
    )
    db.commit()
    db.refresh(word)
    return word


def set_word_status(
    db: Session, actor: User, word_id: int, status: str, request: Request | None = None
) -> Word:
    """上架 / 下架单个词条。"""
    word = db.get(Word, word_id)
    if word is None:
        raise AdminError("词条不存在", status_code=404)
    if word.status == status:
        return word

    word.status = status
    book = db.get(WordBook, word.wordbook_id)
    if book is not None:
        _refresh_total_words(db, book)

    audit_service.record(
        db,
        actor=actor,
        action="word.restore" if status == STATUS_ACTIVE else "word.archive",
        target_type="word",
        target_id=word.id,
        detail={"word": word.word, "status": status},
        affected_rows=1,
        request=request,
    )
    db.commit()
    db.refresh(word)
    return word


def purge_word(db: Session, actor: User, word_id: int, request: Request | None = None) -> None:
    """物理删除单个词条：仅在零用户引用时允许。"""
    word = db.get(Word, word_id)
    if word is None:
        raise AdminError("词条不存在", status_code=404)

    referenced = _referenced_word_count(db, [word.id])
    if referenced:
        raise AdminError(
            f"该词已被 {referenced} 条用户练习记录引用，只能下架不能删除",
            status_code=409,
        )

    book_id = word.wordbook_id
    word_text = word.word
    db.delete(word)
    book = db.get(WordBook, book_id)
    if book is not None:
        _refresh_total_words(db, book)

    audit_service.record(
        db,
        actor=actor,
        action="word.purge",
        target_type="word",
        target_id=word_id,
        detail={"word": word_text},
        affected_rows=1,
        request=request,
    )
    db.commit()


def import_books(
    db: Session, actor: User, payload: object, request: Request | None = None
) -> ImportResult:
    """批量导入：先校验，任一条不通过则整批不写库。

    payload 支持单本书对象（与 data/*.json 同构）或书的数组。
    """
    books = payload if isinstance(payload, list) else [payload]
    if not books:
        raise AdminError("导入内容为空", status_code=400)
    for entry in books:
        if not isinstance(entry, dict):
            raise AdminError("导入文件结构不正确，应为词书对象或其数组", status_code=422)

    validation = validate_batch(books)
    if not validation.ok:
        return ImportResult(
            applied=False,
            issues=[
                ValidationIssueOut(
                    rule=issue.rule, field=issue.field, message=issue.message
                )
                for issue in validation.issues
            ],
        )

    stats = {
        "books_created": 0,
        "books_updated": 0,
        "words_created": 0,
        "words_updated": 0,
        "words_total": 0,
    }

    for book_payload in books:
        code = str(book_payload["code"]).strip()
        book = db.scalar(select(WordBook).where(WordBook.code == code))
        if book is None:
            book = WordBook(
                code=code,
                title=book_payload["title"],
                description=book_payload.get("description", ""),
                difficulty=book_payload.get("difficulty", ""),
                status=STATUS_ACTIVE,
                total_words=0,
            )
            db.add(book)
            db.flush()
            stats["books_created"] += 1
        else:
            book.title = book_payload["title"]
            book.description = book_payload.get("description", "")
            book.difficulty = book_payload.get("difficulty", "")
            # 重新导入意味着这本书要回来
            book.status = STATUS_ACTIVE
            stats["books_updated"] += 1

        existing = {
            row.word.strip().lower(): row
            for row in db.scalars(select(Word).where(Word.wordbook_id == book.id)).all()
        }

        for sequence, item in enumerate(book_payload["words"]):
            key = str(item["word"]).strip().lower()
            target = existing.get(key)
            if target is None:
                db.add(
                    Word(
                        wordbook_id=book.id,
                        word=str(item["word"]).strip(),
                        phonetic=item["phonetic"],
                        translation=item["translation"],
                        example_en=item["example_en"],
                        example_cn=item["example_cn"],
                        sequence=sequence,
                        status=STATUS_ACTIVE,
                    )
                )
                stats["words_created"] += 1
            else:
                # 内容以导入文件为准；重新出现在文件里 = 要它回来
                target.phonetic = item["phonetic"]
                target.translation = item["translation"]
                target.example_en = item["example_en"]
                target.example_cn = item["example_cn"]
                target.sequence = sequence
                target.status = STATUS_ACTIVE
                stats["words_updated"] += 1
            stats["words_total"] += 1

        db.flush()
        _refresh_total_words(db, book)

        audit_service.record(
            db,
            actor=actor,
            action="wordbook.import",
            target_type="wordbook",
            target_id=book.id,
            detail={
                "code": book.code,
                "words_in_file": len(book_payload["words"]),
                "words_created": stats["words_created"],
                "words_updated": stats["words_updated"],
            },
            affected_rows=stats["words_created"] + stats["words_updated"],
            request=request,
        )

    db.commit()
    return ImportResult(applied=True, **stats)


def import_words_into_book(
    db: Session,
    actor: User,
    book: WordBook,
    words: list[dict],
    request: Request | None = None,
) -> ImportResult:
    """向指定词书批量导入词条（词条数组，不含词书元信息）。

    与 import_books 同一套「校验先行、任一条不过整批不写库」语义：
    - 词条本身用 validate_word 逐条校验，issues 定位到 words[i].xxx；
    - 仅当全部通过才写入，已存在的词按 word 小写去重、内容以导入文件为准，
      只回填五个内容字段并置为可用，不动用户练习记录。
    """
    if not words:
        raise AdminError("导入内容为空", status_code=400)

    issues: list[ValidationIssueOut] = []
    seen: dict[str, int] = {}
    for index, item in enumerate(words):
        if not isinstance(item, dict):
            issues.append(
                ValidationIssueOut(
                    rule="word_not_object",
                    field=f"words[{index}]",
                    message=f"第 {index + 1} 条不是对象",
                )
            )
            continue
        label = str(item.get("word") or f"#{index + 1}")
        key = str(item.get("word") or "").strip().lower()
        if key and key in seen:
            issues.append(
                ValidationIssueOut(
                    rule="word_duplicate",
                    field=f"words[{index}].word",
                    message=f"[{label}] 与第 {seen[key] + 1} 条重复",
                )
            )
        elif key:
            seen[key] = index
        for issue in validate_word(item).issues:
            issues.append(
                ValidationIssueOut(
                    rule=issue.rule,
                    field=f"words[{index}].{issue.field}",
                    message=f"[{label}] {issue.message}",
                )
            )
    if issues:
        return ImportResult(applied=False, issues=issues)

    existing = {
        row.word.strip().lower(): row
        for row in db.scalars(select(Word).where(Word.wordbook_id == book.id)).all()
    }
    max_sequence = (
        db.scalar(select(func.max(Word.sequence)).where(Word.wordbook_id == book.id)) or -1
    )

    words_created = 0
    words_updated = 0
    for sequence, item in enumerate(words, start=max_sequence + 1):
        key = str(item["word"]).strip().lower()
        target = existing.get(key)
        if target is None:
            db.add(
                Word(
                    wordbook_id=book.id,
                    word=str(item["word"]).strip(),
                    phonetic=item["phonetic"],
                    translation=item["translation"],
                    example_en=item["example_en"],
                    example_cn=item["example_cn"],
                    sequence=sequence,
                    status=STATUS_ACTIVE,
                )
            )
            words_created += 1
        else:
            # 重新导入 = 要它回来；内容以文件为准
            target.phonetic = item["phonetic"]
            target.translation = item["translation"]
            target.example_en = item["example_en"]
            target.example_cn = item["example_cn"]
            target.status = STATUS_ACTIVE
            words_updated += 1

    db.flush()
    _refresh_total_words(db, book)
    audit_service.record(
        db,
        actor=actor,
        action="wordbook.import_words",
        target_type="wordbook",
        target_id=book.id,
        detail={
            "code": book.code,
            "words_in_file": len(words),
            "words_created": words_created,
            "words_updated": words_updated,
        },
        affected_rows=words_created + words_updated,
        request=request,
    )
    db.commit()
    return ImportResult(
        applied=True,
        words_created=words_created,
        words_updated=words_updated,
        words_total=len(words),
    )

def export_book(db: Session, book_id: int) -> dict:
    """导出为 data/*.json 同构结构，便于写回仓库做版本管理。

    只导出可用词条：下架是运行时决定，不该被带进种子文件。
    """
    book = db.get(WordBook, book_id)
    if book is None:
        raise AdminError("词书不存在", status_code=404)

    words = db.scalars(
        select(Word)
        .where(Word.wordbook_id == book_id, Word.status == STATUS_ACTIVE)
        .order_by(Word.sequence, Word.id)
    ).all()
    return {
        "code": book.code,
        "title": book.title,
        "description": book.description,
        "difficulty": book.difficulty,
        "words": [
            {
                "word": row.word,
                "phonetic": row.phonetic,
                "translation": row.translation,
                "example_en": row.example_en,
                "example_cn": row.example_cn,
            }
            for row in words
        ],
    }


def _refresh_total_words(db: Session, book: WordBook) -> None:
    """total_words 只算可用词，与 compute_progress 的分母口径保持一致。

    必须先 flush：会话是 autoflush=False，调用方刚改完的 word.status 还没落盘，
    直接 COUNT 会把刚下架的词仍算成可用，total_words 就永远刷不下来。
    """
    db.flush()
    book.total_words = _active_word_count(db, book.id)
