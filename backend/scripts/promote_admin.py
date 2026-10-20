"""把指定用户提升为管理员。

注册口会让首个注册用户自动成为管理员，覆盖全新安装的场景。
本脚本用于两种补充情况：
  1. 库里已有历史用户但一个管理员都没有（例如本次从 v1.8 回退后重建的库）；
  2. 管理员全部误删/误降级后的恢复。

脚本只做提升，不创建账号、也不打印任何凭据。

用法：
    cd backend
    .venv/Scripts/python -m scripts.promote_admin <用户名>
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.constants import ROLE_ADMIN
from app.db import SessionLocal
from app.models.user import User


def promote(username: str) -> tuple[bool, str]:
    """提升指定用户为管理员，返回 (是否发生变化, 说明)。"""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            return False, f"用户 {username} 不存在"

        if user.role == ROLE_ADMIN:
            return False, f"{username} 已经是管理员"

        # 游客账号不应被提升：它随时可能被转正删除，权限跟着人走更安全
        if user.is_guest:
            return False, f"{username} 是游客账号，请先转正为正式用户"

        user.role = ROLE_ADMIN
        db.commit()
        return True, f"{username} 已提升为管理员"


def main() -> int:
    if len(sys.argv) != 2:
        print("用法: python -m scripts.promote_admin <用户名>")
        return 2

    changed, message = promote(sys.argv[1])
    print(message)
    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
