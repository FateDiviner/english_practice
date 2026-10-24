from pathlib import Path

from app.services.import_file import parse_import_file, parse_word_row

SAMPLE_FILE = (
    Path(__file__).resolve().parents[2] / "docs" / "examples" / "sample-words.csv"
)


def test_sample_wordbook_can_be_parsed_and_imported() -> None:
    parsed = parse_import_file(SAMPLE_FILE.name, SAMPLE_FILE.read_bytes())
    mapping = {header: index for index, header in enumerate(parsed.headers)}

    rows = [parse_word_row(row, mapping) for row in parsed.rows]
    spellings = [row.spelling.lower() for row in rows]

    assert len(rows) >= 20
    assert len(set(spellings)) == len(rows)
    assert all(row.spelling and row.meaning_cn for row in rows)
    assert all(row.sort_order >= 0 for row in rows)
