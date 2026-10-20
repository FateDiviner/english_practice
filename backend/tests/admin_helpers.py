"""管理端测试共用夹具。

注册口会让首个注册用户成为管理员，因此这里不依赖注册顺序：
一律显式落定角色，避免用例之间互相干扰。
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ROLE_ADMIN, ROLE_USER
from app.models.user import User


def unique_name(prefix: str) -> str:
    """生成不会与会话内既有账号撞名的用户名。

    测试库是会话级共享的，固定名字跑第二个用例就会撞上「用户名已被注册」。
    """
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, username: str, password: str = "secret123") -> dict:
    response = client.post(
        "/api/auth/register", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def make_admin(db: Session, client: TestClient, username: str) -> dict:
    """注册并强制落成管理员，返回含 access_token 的响应体。"""
    data = register(client, username)
    db.get(User, data["user"]["id"]).role = ROLE_ADMIN
    db.commit()
    return data


def make_user(db: Session, client: TestClient, username: str) -> dict:
    """注册并强制落成普通用户。"""
    data = register(client, username)
    db.get(User, data["user"]["id"]).role = ROLE_USER
    db.commit()
    return data


def demote_other_admins(db: Session, keep_id: int) -> None:
    """把除 keep_id 以外的管理员全部降级。

    测试库是会话级共享的，前面用例留下的管理员会让「最后一个管理员」这类
    断言永远不成立，必须先清场。
    """
    for admin in db.scalars(select(User).where(User.role == ROLE_ADMIN)).all():
        if admin.id != keep_id:
            admin.role = ROLE_USER
    db.commit()


def admin_client(db: Session, client: TestClient, username: str = "admin_main") -> TestClient:
    """返回带管理员 Authorization 头的 TestClient。"""
    data = make_admin(db, client, username)
    client.headers.update(headers(data["access_token"]))
    return client


def good_word(**overrides) -> dict:
    """一条完全合规的词条。"""
    item = {
        "word": "abandon",
        "phonetic": "/əˈbændən/",
        "translation": "v. 放弃，遗弃",
        "example_en": "They had to abandon the plan.",
        "example_cn": "他们不得不放弃这个计划。",
    }
    item.update(overrides)
    return item


def good_book(code: str = "admin-test", words: list | None = None, **overrides) -> dict:
    """一本完全合规的词书，用例只改自己关心的部分。"""
    payload = {
        "code": code,
        "title": "管理端测试词书",
        "description": "仅用于测试",
        "difficulty": "easy",
        "words": words if words is not None else [good_word()],
    }
    payload.update(overrides)
    return payload
