from datetime import datetime

from pydantic import BaseModel


class WrongWordItem(BaseModel):
    word_id: int
    spelling: str
    phonetic_uk: str | None
    phonetic_us: str | None
    meaning_cn: str | None
    wrong_count: int
    last_wrong_at: datetime | None
    resolved: bool


class WrongWordListOut(BaseModel):
    items: list[WrongWordItem]
    total: int
    page: int
    page_size: int


class WrongWordRemoveOut(BaseModel):
    removed: bool
