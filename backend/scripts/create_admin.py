"""把指定用户提升为管理端管理员。

首个管理员必须通过本脚本创建：走注册接口会留下抢注管理员的入口。
脚本只做提升，不创建账号、也不打印任何凭据。

用法：
    cd backend
    python -m scripts.create_admin <用户名>
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from core.db import SessionLocal
from core.models.user import User

ADMIN_ROLE = "admin"


def promote(username: str) -> tuple[bool, str]:
    """提升指定用户为管理员，返回 (是否发生变化, 说明)。"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            return False, f"用户 {username} 不存在"

        if user.role == ADMIN_ROLE:
            return False, f"{username} 已经是管理员"

        # 游客账号不应被提升：它随时可能被转正删除，权限跟着人走更安全
        if user.is_guest:
            return False, f"{username} 是游客账号，请先转正为正式用户"

        user.role = ADMIN_ROLE
        db.commit()
        return True, f"{username} 已提升为管理员"


def main() -> int:
    if len(sys.argv) != 2:
        print("用法: python -m scripts.create_admin <用户名>")
        return 2

    changed, message = promote(sys.argv[1])
    print(message)
    if not changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
