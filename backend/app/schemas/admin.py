"""管理端请求与响应契约。

v1.8 把这些拆在 auth/users/words/audit 四个文件里，本轮合并为单文件：
它们全部只服务于管理端，且互相之间没有独立演化的理由。

刻意不含管理端独立的注册/登录契约——本轮复用用户端同一套登录口，
管理员只是 role 不同，不是另一套账号体系。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AdminUserOut(BaseModel):
    """管理端视角的用户信息。

    刻意不含 password_hash——它在任何管理接口响应里都不该出现。
    """

    id: int
    username: str
    is_guest: bool
    role: str
    status: str
    active_wordbook_id: int | None = None
    consecutive_days: int = 0
    created_at: str
    # 最近一次活跃（练习会话）；从未练习过为 None
    last_practiced_at: str | None = None
    practice_count: int = 0

class AdminCreateUserRequest(BaseModel):
    """新增用户（管理端代建）。"""

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=72)
    # user: 普通用户 / admin: 管理员
    role: str = Field(default="user", pattern="^(user|admin)$")

class AdminUpdateUserRequest(BaseModel):
    """启用 / 封禁 / 调整角色，至少给一项。"""

    role: str | None = Field(default=None, pattern="^(user|admin)$")
    # active: 启用 / banned: 封禁
    status: str | None = Field(default=None, pattern="^(active|banned)$")

class AdminUserListPage(BaseModel):
    """分页结果。"""

    total: int
    items: list[AdminUserOut] = Field(default_factory=list)

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

class AuditLogOut(BaseModel):
    """一条审计记录。"""

    id: int
    actor_id: int | None = None
    actor_name: str
    action: str
    target_type: str | None = None
    target_id: str | None = None
    # JSON 字符串，前端自行解析展示；服务端不保证结构，只保证可解析
    detail: str | None = None
    affected_rows: int = 0
    ip: str | None = None
    user_agent: str | None = None
    created_at: str

class AuditLogPage(BaseModel):
    """分页结果。"""

    total: int
    items: list[AuditLogOut] = Field(default_factory=list)
