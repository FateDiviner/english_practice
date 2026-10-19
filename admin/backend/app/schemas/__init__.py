"""管理端请求 / 响应契约。"""

from app.schemas.audit import AuditLogOut, AuditLogPage
from app.schemas.words import (
    ImportResult,
    ValidationIssueOut,
    WordAdminOut,
    WordPage,
    WordbookAdminOut,
    WordbookUpdateRequest,
    WordbookUpsertRequest,
    WordUpsertRequest,
)
from app.schemas.auth import (
    AdminAuthResponse,
    AdminLoginRequest,
    AdminRegisterRequest,
    AdminUserOut,
)
from app.schemas.users import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    AdminUserListPage,
)

__all__ = [
    "AdminAuthResponse",
    "AdminLoginRequest",
    "AdminRegisterRequest",
    "AdminUserOut",
    "AdminCreateUserRequest",
    "AdminUpdateUserRequest",
    "AdminUserListPage",
    "AuditLogOut",
    "AuditLogPage",
    "WordbookAdminOut",
    "WordbookUpsertRequest",
    "WordbookUpdateRequest",
    "WordAdminOut",
    "WordPage",
    "WordUpsertRequest",
    "ValidationIssueOut",
    "ImportResult",
]
