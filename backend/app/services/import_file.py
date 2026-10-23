import csv
import io
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.core.exception_handlers import ERROR_CODE_VALIDATION, AppError

MAX_IMPORT_FILE_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 20_000
MAX_IMPORT_COLUMNS = 100
MAX_TEXT_LENGTH = 5_000
SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".txt", ".xlsx"}
OPTIONAL_TEXT_LIMITS = {
    "phonetic_uk": ("英式音标", 100),
    "phonetic_us": ("美式音标", 100),
    "meaning_cn": ("中文释义", 255),
    "part_of_speech": ("词性", 20),
    "example_en": ("英文例句", MAX_TEXT_LENGTH),
    "example_cn": ("例句译文", MAX_TEXT_LENGTH),
    "audio_url": ("音频地址", 255),
}


@dataclass(frozen=True)
class ParsedImportFile:
    file_name: str
    sheet_name: str | None
    headers: list[str]
    rows: list[list[str]]


@dataclass(frozen=True)
class ParsedWordRow:
    spelling: str
    phonetic_uk: str | None
    phonetic_us: str | None
    meaning_cn: str | None
    part_of_speech: str | None
    example_en: str | None
    example_cn: str | None
    audio_url: str | None
    sort_order: int


class ImportRowError(ValueError):
    """单行导入数据不符合字段约束。"""


def clean_upload_filename(filename: str | None) -> str:
    """规范化上传文件名并校验扩展名。"""
    safe_name = Path(filename or "").name.strip()
    if not safe_name:
        raise AppError(422, ERROR_CODE_VALIDATION, "请选择导入文件")
    extension = Path(safe_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise AppError(422, ERROR_CODE_VALIDATION, "仅支持 CSV、TSV、TXT 或 XLSX 文件")
    return safe_name[:255]


def ensure_file_size(content: bytes) -> None:
    """拒绝空文件和超过 10MB 的上传。"""
    if not content:
        raise AppError(422, ERROR_CODE_VALIDATION, "导入文件为空")
    if len(content) > MAX_IMPORT_FILE_BYTES:
        raise AppError(422, ERROR_CODE_VALIDATION, "导入文件不能超过 10MB")


def parse_import_file(file_name: str, content: bytes) -> ParsedImportFile:
    """解析 CSV/TSV/XLSX 为统一的表头与数据行结构。"""
    ensure_file_size(content)
    extension = Path(file_name).suffix.lower()
    if extension == ".xlsx":
        rows, sheet_name = _parse_xlsx(content)
    else:
        rows = _parse_delimited(file_name, content)
        sheet_name = None
    return _build_parsed_file(file_name, sheet_name, rows)


def parse_word_row(
    row: list[str],
    mapping: dict[str, int | None],
) -> ParsedWordRow:
    """按列映射校验一行数据并转换为单词字段。"""
    spelling = _cell(row, mapping.get("spelling")).strip()
    if not spelling:
        raise ImportRowError("拼写为空")
    if len(spelling) > 100:
        raise ImportRowError("拼写超过 100 个字符")

    optional_values = {}
    for field, (label, max_length) in OPTIONAL_TEXT_LIMITS.items():
        value = _cell(row, mapping.get(field)).strip()
        if len(value) > max_length:
            raise ImportRowError(f"{label}超过 {max_length} 个字符")
        optional_values[field] = value or None

    sort_text = _cell(row, mapping.get("sort_order")).strip()
    try:
        sort_order = int(sort_text) if sort_text else 0
    except ValueError as exc:
        raise ImportRowError("排序必须是非负整数") from exc
    if sort_order < 0:
        raise ImportRowError("排序必须是非负整数")

    return ParsedWordRow(
        spelling=spelling,
        sort_order=sort_order,
        **optional_values,
    )


def row_content_preview(row: list[str]) -> str:
    """截断行内容，避免错误明细过长。"""
    content = " | ".join(value for value in row if value)
    return content[:500]


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return str(row[index] or "")


def _build_parsed_file(
    file_name: str,
    sheet_name: str | None,
    rows: list[list[str]],
) -> ParsedImportFile:
    non_empty_rows = [row for row in rows if any(value for value in row)]
    if not non_empty_rows:
        raise AppError(422, ERROR_CODE_VALIDATION, "导入文件中没有可读取的数据")
    headers = non_empty_rows[0]
    if not any(headers):
        raise AppError(422, ERROR_CODE_VALIDATION, "文件第一行必须包含表头")
    if len(headers) > MAX_IMPORT_COLUMNS:
        raise AppError(422, ERROR_CODE_VALIDATION, "文件列数不能超过 100 列")
    data_rows = non_empty_rows[1:]
    if len(data_rows) > MAX_IMPORT_ROWS:
        raise AppError(422, ERROR_CODE_VALIDATION, "单次导入不能超过 20000 行")
    return ParsedImportFile(
        file_name=file_name,
        sheet_name=sheet_name,
        headers=headers,
        rows=data_rows,
    )


def _parse_delimited(file_name: str, content: bytes) -> list[list[str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("gb18030")
        except UnicodeDecodeError as exc:
            raise AppError(422, ERROR_CODE_VALIDATION, "文件编码无法识别") from exc

    first_line = text.splitlines()[0] if text.splitlines() else ""
    if Path(file_name).suffix.lower() == ".tsv":
        delimiter = "\t"
    else:
        delimiter = max([",", "\t", ";"], key=first_line.count)
    try:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter, strict=True)
        return [[str(value).strip() for value in row] for row in reader]
    except csv.Error as exc:
        raise AppError(422, ERROR_CODE_VALIDATION, "分隔文件格式不正确") from exc


def _parse_xlsx(content: bytes) -> tuple[list[list[str]], str | None]:
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except (InvalidFileException, OSError, ValueError) as exc:
        raise AppError(422, ERROR_CODE_VALIDATION, "XLSX 文件格式不正确") from exc

    try:
        worksheet = workbook.active
        rows = []
        for values in worksheet.iter_rows(values_only=True):
            rows.append([_normalize_excel_cell(value) for value in values])
        return rows, worksheet.title
    finally:
        workbook.close()


def _normalize_excel_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()
