"""AI 会话持久化接口测试。"""

import json
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.db.session import async_session_factory
from app.models.ai_conversation import AiConversation
from app.models.ai_message import AiMessage
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy import delete, func, select

PREFIX = "pytest_ai_"
USER_PASSWORD = "UserPass123!"


async def _clean_ai_data() -> None:
    async with async_session_factory() as session:
        user_ids = list(
            await session.scalars(select(User.id).where(User.username.like(f"{PREFIX}%"))),
        )
        if not user_ids:
            await session.commit()
            return
        conversation_ids = list(
            await session.scalars(
                select(AiConversation.id).where(AiConversation.user_id.in_(user_ids)),
            ),
        )
        if conversation_ids:
            await session.execute(
                delete(AiMessage).where(AiMessage.conversation_id.in_(conversation_ids)),
            )
        await session.execute(
            delete(AiConversation).where(AiConversation.user_id.in_(user_ids)),
        )
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_ai_data() -> AsyncIterator[None]:
    await _clean_ai_data()
    yield
    await _clean_ai_data()


async def _create_user(client: AsyncClient, label: str) -> tuple[dict[str, str], int]:
    username = f"{PREFIX}user_{label}_{uuid4().hex[:10]}"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": USER_PASSWORD,
        },
    )
    assert response.status_code == 201
    user_id = response.json()["data"]["id"]
    login = await client.post(
        "/api/v1/auth/login",
        json={"account": username, "password": USER_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}, user_id


def _sse_events(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.strip().split("\n\n"):
        lines = block.splitlines()
        if not lines:
            continue
        event = next(
            (line.removeprefix("event: ") for line in lines if line.startswith("event: ")),
            "message",
        )
        data = "\n".join(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        events.append((event, json.loads(data)))
    return events


async def _chat(
    client: AsyncClient,
    headers: dict[str, str],
    message: str,
    conversation_id: int | None = None,
) -> tuple[int, list[tuple[str, dict]]]:
    payload: dict = {"message": message, "scene": None, "history": []}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = await client.post("/api/v1/agent/chat", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    events = _sse_events(response.text)
    meta = events[0][1]
    return meta["conversation_id"], events


async def test_ai_sessions_require_login(client: AsyncClient) -> None:
    for method, path in (
        ("get", "/api/v1/ai/sessions"),
        ("post", "/api/v1/ai/sessions"),
        ("get", "/api/v1/ai/sessions/1"),
        ("delete", "/api/v1/ai/sessions/1"),
    ):
        response = await getattr(client, method)(path)
        assert response.status_code == 401
        assert response.json()["code"] == 40101


async def test_create_and_list_sessions(client: AsyncClient) -> None:
    user, _ = await _create_user(client, "list")

    empty = await client.post("/api/v1/ai/sessions", headers=user, json={})
    assert empty.status_code == 201
    assert empty.json()["data"]["title"] is None

    named = await client.post(
        "/api/v1/ai/sessions",
        headers=user,
        json={"title": "  餐厅对话  ", "scene": "restaurant"},
    )
    assert named.status_code == 201
    named_data = named.json()["data"]
    assert named_data["title"] == "餐厅对话"
    assert named_data["scene"] == "restaurant"

    listing = await client.get("/api/v1/ai/sessions?page=1&page_size=10", headers=user)
    body = listing.json()["data"]
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert [item["id"] for item in body["items"]] == [
        named_data["id"],
        empty.json()["data"]["id"],
    ]
    assert all(item["message_count"] == 0 for item in body["items"])


async def test_session_detail_and_ownership(client: AsyncClient) -> None:
    owner, _ = await _create_user(client, "owner")
    other, _ = await _create_user(client, "other")
    created = await client.post(
        "/api/v1/ai/sessions",
        headers=owner,
        json={"title": "only mine"},
    )
    conversation_id = created.json()["data"]["id"]

    detail = await client.get(f"/api/v1/ai/sessions/{conversation_id}", headers=owner)
    assert detail.status_code == 200
    assert detail.json()["data"]["messages"] == []

    for response in (
        await client.get(f"/api/v1/ai/sessions/{conversation_id}", headers=other),
        await client.delete(f"/api/v1/ai/sessions/{conversation_id}", headers=other),
    ):
        assert response.status_code == 404
        assert response.json()["code"] == 40401

    denied_chat = await client.post(
        "/api/v1/agent/chat",
        headers=other,
        json={"message": "hi", "conversation_id": conversation_id},
    )
    assert denied_chat.status_code == 404
    assert denied_chat.json()["code"] == 40401


async def test_chat_creates_conversation_and_persists_messages(
    client: AsyncClient,
) -> None:
    user, _ = await _create_user(client, "chat_new")
    conversation_id, events = await _chat(client, user, "abandon 是什么意思")

    names = [event for event, _ in events]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert set(names) == {"meta", "delta", "done"}
    assert events[0][1]["conversation_id"] == conversation_id

    detail = await client.get(f"/api/v1/ai/sessions/{conversation_id}", headers=user)
    data = detail.json()["data"]
    assert data["title"] == "abandon 是什么意思"
    assert [message["role"] for message in data["messages"]] == ["user", "assistant"]
    assert data["messages"][0]["content"] == "abandon 是什么意思"
    assert "abandon" in data["messages"][1]["content"]

    listing = await client.get("/api/v1/ai/sessions", headers=user)
    assert listing.json()["data"]["items"][0]["message_count"] == 2


async def test_chat_continues_existing_conversation(client: AsyncClient) -> None:
    user, _ = await _create_user(client, "chat_continue")
    created = await client.post(
        "/api/v1/ai/sessions",
        headers=user,
        json={"scene": "restaurant"},
    )
    conversation_id = created.json()["data"]["id"]

    await _chat(client, user, "我想练点餐口语", conversation_id)
    await _chat(client, user, "再来一句", conversation_id)

    detail = await client.get(f"/api/v1/ai/sessions/{conversation_id}", headers=user)
    data = detail.json()["data"]
    assert data["title"] == "我想练点餐口语"
    assert data["scene"] == "restaurant"
    assert [message["role"] for message in data["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]

    listing = await client.get("/api/v1/ai/sessions", headers=user)
    assert listing.json()["data"]["total"] == 1
    assert listing.json()["data"]["items"][0]["message_count"] == 4


async def test_chat_generates_truncated_title(client: AsyncClient) -> None:
    user, _ = await _create_user(client, "chat_title")
    long_message = "a" * 50
    conversation_id, _ = await _chat(client, user, long_message)

    detail = await client.get(f"/api/v1/ai/sessions/{conversation_id}", headers=user)
    assert detail.json()["data"]["title"] == ("a" * 30) + "…"


async def test_chat_rejects_blank_message(client: AsyncClient) -> None:
    user, _ = await _create_user(client, "chat_blank")
    response = await client.post(
        "/api/v1/agent/chat",
        headers=user,
        json={"message": "   "},
    )
    assert response.status_code == 422
    assert response.json()["code"] == 42201


async def test_delete_conversation_cascades_messages(client: AsyncClient) -> None:
    user, _ = await _create_user(client, "chat_delete")
    conversation_id, _ = await _chat(client, user, "hello")

    response = await client.delete(f"/api/v1/ai/sessions/{conversation_id}", headers=user)
    assert response.status_code == 200
    assert response.json()["data"] == {"deleted": True}

    missing = await client.get(f"/api/v1/ai/sessions/{conversation_id}", headers=user)
    assert missing.status_code == 404

    async with async_session_factory() as session:
        count = await session.scalar(
            select(func.count(AiMessage.id)).where(
                AiMessage.conversation_id == conversation_id,
            ),
        )
    assert count == 0
