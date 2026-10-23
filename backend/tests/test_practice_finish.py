from app.db.session import async_session_factory
from app.models.practice_session import PracticeSession
from app.models.user_wordbook import UserWordbook
from httpx import AsyncClient
from sqlalchemy import select

from tests.practice_answer_helpers import (
    answer,
    build_context,
    create_practice_session,
    create_user,
)


async def test_finish_requires_login(client: AsyncClient) -> None:
    response = await client.post("/api/v1/practice/sessions/1/finish")
    assert response.status_code == 401
    assert response.json()["code"] == 40101


async def test_finish_returns_summary_and_updates_user_wordbook(client: AsyncClient) -> None:
    context = await build_context(client, "finish", ["alpha"])
    question = context["session"]["questions"][0]
    await answer(
        client, context["user"], context["session"]["session_id"], question["word_id"], "alpha"
    )

    response = await client.post(
        f"/api/v1/practice/sessions/{context['session']['session_id']}/finish",
        headers=context["user"],
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["session_id"] == context["session"]["session_id"]
    assert body["total"] == 1
    assert body["correct"] == 1
    assert body["accuracy"] == 100.0
    assert body["duration_seconds"] >= 0

    async with async_session_factory() as session:
        user_wordbook = await session.scalar(
            select(UserWordbook).where(
                UserWordbook.user_id == context["user_id"],
                UserWordbook.wordbook_id == context["wordbook_id"],
            ),
        )
        assert user_wordbook is not None
        assert user_wordbook.last_practiced_at is not None


async def test_finish_is_idempotent(client: AsyncClient) -> None:
    context = await build_context(client, "finish_idempotent", ["alpha"])
    session_id = context["session"]["session_id"]
    first = await client.post(
        f"/api/v1/practice/sessions/{session_id}/finish", headers=context["user"]
    )
    async with async_session_factory() as session:
        stored = await session.get(PracticeSession, session_id)
        assert stored is not None
        first_finished_at = stored.finished_at
    second = await client.post(
        f"/api/v1/practice/sessions/{session_id}/finish", headers=context["user"]
    )
    async with async_session_factory() as session:
        stored = await session.get(PracticeSession, session_id)
        assert stored is not None
        second_finished_at = stored.finished_at

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first_finished_at == second_finished_at


async def test_finish_creates_learning_user_wordbook(client: AsyncClient) -> None:
    context = await build_context(client, "finish_create", ["alpha"])
    response = await client.post(
        f"/api/v1/practice/sessions/{context['session']['session_id']}/finish",
        headers=context["user"],
    )
    assert response.status_code == 200

    async with async_session_factory() as session:
        user_wordbook = await session.scalar(
            select(UserWordbook).where(
                UserWordbook.user_id == context["user_id"],
                UserWordbook.wordbook_id == context["wordbook_id"],
            ),
        )
        assert user_wordbook is not None
        assert user_wordbook.status == "learning"
        assert user_wordbook.started_at is not None
        assert user_wordbook.last_practiced_at is not None


async def test_finish_marks_completed_when_all_words_mastered(client: AsyncClient) -> None:
    context = await build_context(client, "finish_completed", ["alpha"])
    first_session = context["session"]
    first_question = first_session["questions"][0]
    await answer(
        client, context["user"], first_session["session_id"], first_question["word_id"], "alpha"
    )
    await client.post(
        f"/api/v1/practice/sessions/{first_session['session_id']}/finish", headers=context["user"]
    )

    second_session = await create_practice_session(client, context["user"], context["wordbook_id"])
    second_question = second_session["questions"][0]
    await answer(
        client, context["user"], second_session["session_id"], second_question["word_id"], "alpha"
    )
    response = await client.post(
        f"/api/v1/practice/sessions/{second_session['session_id']}/finish",
        headers=context["user"],
    )
    assert response.status_code == 200

    async with async_session_factory() as session:
        user_wordbook = await session.scalar(
            select(UserWordbook).where(
                UserWordbook.user_id == context["user_id"],
                UserWordbook.wordbook_id == context["wordbook_id"],
            ),
        )
        assert user_wordbook is not None
        assert user_wordbook.status == "completed"


async def test_finish_rejects_other_user_and_missing_session(client: AsyncClient) -> None:
    context = await build_context(client, "finish_errors", ["alpha"])
    other_user, _ = await create_user(client, "finish_other")

    other_response = await client.post(
        f"/api/v1/practice/sessions/{context['session']['session_id']}/finish",
        headers=other_user,
    )
    missing_response = await client.post(
        "/api/v1/practice/sessions/999999999/finish",
        headers=context["user"],
    )

    assert other_response.status_code == 403
    assert other_response.json()["code"] == 40301
    assert missing_response.status_code == 404
    assert missing_response.json()["code"] == 40401


async def test_session_detail_returns_records_and_enforces_owner(client: AsyncClient) -> None:
    context = await build_context(client, "detail", ["alpha"])
    question = context["session"]["questions"][0]
    await answer(
        client, context["user"], context["session"]["session_id"], question["word_id"], "alpha"
    )
    await client.post(
        f"/api/v1/practice/sessions/{context['session']['session_id']}/finish",
        headers=context["user"],
    )

    response = await client.get(
        f"/api/v1/practice/sessions/{context['session']['session_id']}",
        headers=context["user"],
    )
    other_user, _ = await create_user(client, "detail_other")
    forbidden = await client.get(
        f"/api/v1/practice/sessions/{context['session']['session_id']}",
        headers=other_user,
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "finished"
    assert body["total"] == 1
    assert body["correct"] == 1
    assert body["accuracy"] == 100.0
    assert body["records"] == [
        {"word_id": question["word_id"], "is_correct": True, "user_input": "alpha"}
    ]
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == 40301
