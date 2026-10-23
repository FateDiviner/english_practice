from app.db.session import async_session_factory
from app.models.wrong_word import WrongWord
from httpx import AsyncClient
from sqlalchemy import select

from tests.practice_answer_helpers import (
    answer,
    build_context,
    create_practice_session,
    create_user,
)


async def test_wrong_words_requires_login(client: AsyncClient) -> None:
    response = await client.get("/api/v1/wrong-words")
    assert response.status_code == 401
    assert response.json()["code"] == 40101


async def test_wrong_answer_appears_in_wrong_words(client: AsyncClient) -> None:
    context = await build_context(client, "appears", ["alpha"])
    question = context["session"]["questions"][0]
    await answer(
        client, context["user"], context["session"]["session_id"], question["word_id"], "wrong"
    )

    response = await client.get("/api/v1/wrong-words", headers=context["user"])

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total"] == 1
    assert body["items"] == [
        {
            "word_id": question["word_id"],
            "spelling": "alpha",
            "phonetic_uk": None,
            "phonetic_us": None,
            "meaning_cn": "释义 alpha",
            "wrong_count": 1,
            "last_wrong_at": body["items"][0]["last_wrong_at"],
            "resolved": False,
        },
    ]


async def test_repeated_wrong_answers_accumulate_count(client: AsyncClient) -> None:
    context = await build_context(client, "accumulate", ["alpha"])
    word_id = context["session"]["questions"][0]["word_id"]
    await answer(client, context["user"], context["session"]["session_id"], word_id, "wrong")
    second_session = await create_practice_session(client, context["user"], context["wordbook_id"])
    await answer(client, context["user"], second_session["session_id"], word_id, "wrong")

    response = await client.get("/api/v1/wrong-words", headers=context["user"])

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["total"] == 1
    assert body["items"][0]["wrong_count"] == 2


async def test_wrong_words_pagination(client: AsyncClient) -> None:
    context = await build_context(client, "pagination", ["alpha", "beta", "gamma"])
    for question in context["session"]["questions"]:
        await answer(
            client, context["user"], context["session"]["session_id"], question["word_id"], "wrong"
        )

    first_page = await client.get(
        "/api/v1/wrong-words?page=1&page_size=2",
        headers=context["user"],
    )
    second_page = await client.get(
        "/api/v1/wrong-words?page=2&page_size=2",
        headers=context["user"],
    )

    assert first_page.status_code == 200
    assert first_page.json()["data"]["total"] == 3
    assert len(first_page.json()["data"]["items"]) == 2
    assert second_page.status_code == 200
    assert len(second_page.json()["data"]["items"]) == 1


async def test_resolved_filter(client: AsyncClient) -> None:
    context = await build_context(client, "resolved", ["alpha"])
    word_id = context["session"]["questions"][0]["word_id"]
    await answer(client, context["user"], context["session"]["session_id"], word_id, "wrong")
    async with async_session_factory() as session:
        wrong_word = await session.scalar(
            select(WrongWord).where(
                WrongWord.user_id == context["user_id"],
                WrongWord.word_id == word_id,
            ),
        )
        assert wrong_word is not None
        wrong_word.resolved = True
        await session.commit()

    unresolved = await client.get("/api/v1/wrong-words", headers=context["user"])
    resolved = await client.get("/api/v1/wrong-words?resolved=true", headers=context["user"])

    assert unresolved.status_code == 200
    assert unresolved.json()["data"]["total"] == 0
    assert resolved.status_code == 200
    assert resolved.json()["data"]["total"] == 1
    assert resolved.json()["data"]["items"][0]["resolved"] is True


async def test_remove_wrong_word_success_and_not_found(client: AsyncClient) -> None:
    context = await build_context(client, "remove", ["alpha"])
    word_id = context["session"]["questions"][0]["word_id"]
    await answer(client, context["user"], context["session"]["session_id"], word_id, "wrong")

    first = await client.delete(f"/api/v1/wrong-words/{word_id}", headers=context["user"])
    second = await client.delete(f"/api/v1/wrong-words/{word_id}", headers=context["user"])
    listing = await client.get("/api/v1/wrong-words", headers=context["user"])

    assert first.status_code == 200
    assert first.json()["data"] == {"removed": True}
    assert second.status_code == 404
    assert second.json()["code"] == 40401
    assert listing.json()["data"]["total"] == 0


async def test_cannot_remove_another_users_wrong_word(client: AsyncClient) -> None:
    context = await build_context(client, "other_owner", ["alpha"])
    word_id = context["session"]["questions"][0]["word_id"]
    await answer(client, context["user"], context["session"]["session_id"], word_id, "wrong")
    other_user, _ = await create_user(client, "remove_other")

    response = await client.delete(f"/api/v1/wrong-words/{word_id}", headers=other_user)

    assert response.status_code == 404
    assert response.json()["code"] == 40401
