"""管理端路由包。

所有路由都必须挂 require_admin，权限判定只在后端——前端隐藏入口不算权限。
"""

from __future__ import annotations

from app.api.admin.audit import router as audit_router

__all__ = ["audit_router"]
