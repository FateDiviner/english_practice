from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImportMappingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spelling: int = Field(ge=0)
    phonetic_uk: int | None = Field(default=None, ge=0)
    phonetic_us: int | None = Field(default=None, ge=0)
    meaning_cn: int | None = Field(default=None, ge=0)
    part_of_speech: int | None = Field(default=None, ge=0)
    example_en: int | None = Field(default=None, ge=0)
    example_cn: int | None = Field(default=None, ge=0)
    audio_url: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)


class ImportPreviewOut(BaseModel):
    file_name: str
    sheet_name: str | None = None
    headers: list[str]
    rows: list[list[str]]
    total_rows: int


class ImportJobCreateOut(BaseModel):
    import_job_id: int


class ImportJobErrorOut(BaseModel):
    row: int
    content: str | None = None
    reason: str


class ImportJobOut(BaseModel):
    id: int
    status: Literal["pending", "processing", "done", "failed"]
    total_rows: int
    success_rows: int
    failed_rows: int
    errors: list[ImportJobErrorOut]
