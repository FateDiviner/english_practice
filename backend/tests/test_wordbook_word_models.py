from app.models.word import Word
from app.models.wordbook import Wordbook
from sqlalchemy import BigInteger, Integer, String, Text


def test_wordbook_table_matches_data_dictionary() -> None:
    table = Wordbook.__table__

    assert table.name == "wordbooks"
    assert set(table.columns.keys()) == {
        "id",
        "name",
        "description",
        "level",
        "status",
        "created_by",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.id.type, BigInteger)
    assert table.c.id.primary_key
    assert isinstance(table.c.name.type, String)
    assert table.c.name.type.length == 100
    assert isinstance(table.c.description.type, Text)
    assert table.c.description.nullable
    assert isinstance(table.c.level.type, String)
    assert table.c.level.type.length == 20
    assert table.c.level.nullable
    assert table.c.status.type.enums == ["draft", "published", "archived"]
    assert table.c.created_by.nullable is False


def test_wordbook_indexes_and_foreign_key() -> None:
    table = Wordbook.__table__
    indexes = {index.name: index for index in table.indexes}

    assert set(indexes) == {"idx_wordbooks_status", "idx_wordbooks_created_by"}
    foreign_key = next(iter(table.c.created_by.foreign_keys))
    assert foreign_key.target_fullname == "users.id"
    assert foreign_key.ondelete == "RESTRICT"


def test_word_table_matches_data_dictionary() -> None:
    table = Word.__table__

    assert table.name == "words"
    assert set(table.columns.keys()) == {
        "id",
        "wordbook_id",
        "spelling",
        "phonetic_uk",
        "phonetic_us",
        "meaning_cn",
        "part_of_speech",
        "example_en",
        "example_cn",
        "audio_url",
        "sort_order",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.id.type, BigInteger)
    assert table.c.id.primary_key
    assert table.c.wordbook_id.nullable is False
    assert isinstance(table.c.spelling.type, String)
    assert table.c.spelling.type.length == 100
    assert isinstance(table.c.phonetic_uk.type, String)
    assert table.c.phonetic_uk.type.length == 100
    assert isinstance(table.c.phonetic_us.type, String)
    assert table.c.phonetic_us.type.length == 100
    assert isinstance(table.c.meaning_cn.type, String)
    assert table.c.meaning_cn.type.length == 255
    assert isinstance(table.c.part_of_speech.type, String)
    assert table.c.part_of_speech.type.length == 20
    assert isinstance(table.c.example_en.type, Text)
    assert isinstance(table.c.example_cn.type, Text)
    assert isinstance(table.c.audio_url.type, String)
    assert table.c.audio_url.type.length == 255
    assert isinstance(table.c.sort_order.type, Integer)
    assert table.c.sort_order.nullable is False


def test_word_constraints_and_foreign_key() -> None:
    table = Word.__table__
    indexes = {index.name: index for index in table.indexes}
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    foreign_key = next(iter(table.c.wordbook_id.foreign_keys))

    assert "idx_words_wordbook_id" in indexes
    assert ("wordbook_id", "spelling") in unique_columns
    assert foreign_key.target_fullname == "wordbooks.id"
    assert foreign_key.ondelete == "RESTRICT"
