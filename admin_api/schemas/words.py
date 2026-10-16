"""管理端词库契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WordbookAdminOut(BaseModel):
    """词书（管理端视角）。"""

    id: int
    code: str
    title: str
    description: str
    difficulty: str
    # active: 可用 / archived: 已下架
    status: str
    total_words: int
    # 该书里已下架的词条数，与 total_words 分开显示
    archived_words: int
    # 有多少用户把它设为当前激活词书
    active_users: int


class WordbookUpsertRequest(BaseModel):
    """新建词书；编辑时只填要改的字段。"""

    code: str = Field(min_length=2, max_length=32, pattern="^[a-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=500)
    difficulty: str = Field(default="", max_length=32)


class WordbookUpdateRequest(BaseModel):
    """编辑词书元信息或上架 / 下架。"""

    title: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    difficulty: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class WordAdminOut(BaseModel):
    """词条（管理端视角）。"""

    id: int
    word: str
    phonetic: str
    translation: str
    example_en: str
    example_cn: str
    sequence: int
    status: str


class WordPage(BaseModel):
    """词条分页。"""

    total: int
    items: list[WordAdminOut] = Field(default_factory=list)


class WordUpsertRequest(BaseModel):
    """新增 / 编辑词条。字段与 data/*.json 完全一致，校验器同源。"""

    word: str = Field(min_length=1, max_length=128)
    phonetic: str = Field(min_length=1, max_length=128)
    translation: str = Field(min_length=1, max_length=500)
    example_en: str = Field(min_length=1, max_length=500)
    example_cn: str = Field(min_length=1, max_length=500)


class ValidationIssueOut(BaseModel):
    """一条校验问题，可直接定位到某本书的第几条。"""

    rule: str
    field: str
    message: str


class ImportResult(BaseModel):
    """批量导入结果。

    applied 为 False 时整批未写库，issues 就是全部待修项。
    """

    applied: bool
    books_created: int = 0
    books_updated: int = 0
    words_created: int = 0
    words_updated: int = 0
    words_total: int = 0
    issues: list[ValidationIssueOut] = Field(default_factory=list)


class PurgeRequest(BaseModel):
    """物理删除：仅在零用户引用时允许，默认只做下架。"""

    purge: bool = False
