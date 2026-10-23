from app.models.practice_record import PracticeRecord
from app.models.practice_session import PracticeSession
from app.models.session_question import SessionQuestion
from app.models.user_wordbook import UserWordbook
from app.models.word_progress import WordProgress
from app.models.wrong_word import WrongWord
from sqlalchemy import BigInteger, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mysql import TINYINT


def test_user_wordbook_schema() -> None:
    table = UserWordbook.__table__
    unique_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert table.name == "user_wordbooks"
    assert set(table.columns.keys()) == {
        "id",
        "user_id",
        "wordbook_id",
        "status",
        "started_at",
        "last_practiced_at",
        "created_at",
        "updated_at",
    }
    assert table.c.status.type.enums == ["learning", "completed"]
    assert "uq_user_wordbooks_user_id_wordbook_id" in unique_names
    assert next(iter(table.c.user_id.foreign_keys)).ondelete == "RESTRICT"
    assert next(iter(table.c.wordbook_id.foreign_keys)).ondelete == "RESTRICT"


def test_word_progress_schema() -> None:
    table = WordProgress.__table__
    unique_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexes = {index.name for index in table.indexes}

    assert table.name == "word_progress"
    assert set(table.columns.keys()) == {
        "id",
        "user_id",
        "word_id",
        "mastery_level",
        "correct_count",
        "wrong_count",
        "consecutive_correct",
        "last_result",
        "last_practiced_at",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.id.type, BigInteger)
    assert isinstance(table.c.mastery_level.type, TINYINT)
    assert isinstance(table.c.correct_count.type, Integer)
    assert table.c.last_result.type.enums == ["correct", "wrong"]
    assert "uq_word_progress_user_id_word_id" in unique_names
    assert "idx_word_progress_user" in indexes
    assert next(iter(table.c.user_id.foreign_keys)).ondelete == "RESTRICT"
    assert next(iter(table.c.word_id.foreign_keys)).ondelete == "RESTRICT"


def test_practice_session_schema() -> None:
    table = PracticeSession.__table__
    indexes = {index.name for index in table.indexes}

    assert table.name == "practice_sessions"
    assert set(table.columns.keys()) == {
        "id",
        "user_id",
        "wordbook_id",
        "mode",
        "strict_mode",
        "total_count",
        "correct_count",
        "status",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    }
    assert table.c.wordbook_id.nullable is True
    assert isinstance(table.c.strict_mode.type, Boolean)
    assert table.c.mode.type.enums == ["normal", "wrong_only"]
    assert table.c.status.type.enums == ["ongoing", "finished"]
    assert indexes == {"idx_sessions_user", "idx_sessions_started_at"}
    assert next(iter(table.c.user_id.foreign_keys)).ondelete == "CASCADE"
    assert next(iter(table.c.wordbook_id.foreign_keys)).ondelete == "RESTRICT"


def test_practice_record_schema_and_cascade_chain() -> None:
    table = PracticeRecord.__table__
    unique_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexes = {index.name for index in table.indexes}

    assert table.name == "practice_records"
    assert set(table.columns.keys()) == {
        "id",
        "session_id",
        "word_id",
        "user_input",
        "is_correct",
        "used_hint",
        "answered_at",
        "created_at",
    }
    assert isinstance(table.c.user_input.type, String)
    assert table.c.user_input.type.length == 100
    assert isinstance(table.c.is_correct.type, Boolean)
    assert isinstance(table.c.used_hint.type, Boolean)
    assert "user_id" not in table.c
    assert "uq_practice_records_session_id_word_id" in unique_names
    assert indexes == {"idx_records_session", "idx_records_word"}
    assert next(iter(table.c.session_id.foreign_keys)).ondelete == "CASCADE"
    assert next(iter(table.c.word_id.foreign_keys)).ondelete == "RESTRICT"


def test_wrong_word_schema() -> None:
    table = WrongWord.__table__
    unique_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexes = {index.name for index in table.indexes}

    assert table.name == "wrong_words"
    assert set(table.columns.keys()) == {
        "id",
        "user_id",
        "word_id",
        "wrong_count",
        "last_wrong_at",
        "resolved",
        "resolved_at",
        "created_at",
        "updated_at",
    }
    assert table.c.resolved.nullable is False
    assert "uq_wrong_words_user_id_word_id" in unique_names
    assert "idx_wrong_words_user_resolved" in indexes
    assert next(iter(table.c.user_id.foreign_keys)).ondelete == "CASCADE"
    assert next(iter(table.c.word_id.foreign_keys)).ondelete == "RESTRICT"


def test_session_question_schema() -> None:
    table = SessionQuestion.__table__
    unique_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexes = {index.name for index in table.indexes}

    assert table.name == "session_questions"
    assert set(table.columns.keys()) == {
        "id",
        "session_id",
        "word_id",
        "sort_order",
        "created_at",
    }
    assert "uq_session_questions_session_id_word_id" in unique_names
    assert "idx_session_questions_session_sort" in indexes
    assert next(iter(table.c.session_id.foreign_keys)).ondelete == "CASCADE"
    assert next(iter(table.c.word_id.foreign_keys)).ondelete == "RESTRICT"
