from app.db.session import async_session_factory
from app.models.practice_record import PracticeRecord
from app.models.practice_session import PracticeSession
from app.models.word_progress import WordProgress
from app.models.wrong_word import WrongWord
from httpx import AsyncClient
from sqlalchemy import func, select

from tests.practice_answer_helpers import (
    answer,
    build_context,
    create_practice_session,
    create_user,
    create_word,
)


async def test_answer_requires_login(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/practice/sessions/1/answer",
        json={"word_id": 1, "user_input": "answer", "used_hint": False},
    )
    assert response.status_code == 401
    assert response.json()["code"] == 40101


async def test_correct_answer_returns_no_answer_fields(client: AsyncClient) -> None:
    context = await build_context(client, "correct", ["alpha"])
    question = context["session"]["questions"][0]
    response = await answer(
        client, context["user"], context["session"]["session_id"], question["word_id"], "alpha"
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["is_correct"] is True
    assert "correct_spelling" not in body
    assert "example_en" not in body
    assert "example_cn" not in body


async def test_wrong_answer_returns_correct_spelling_and_examples(client: AsyncClient) -> None:
    context = await build_context(client, "wrong", ["alpha"])
    question = context["session"]["questions"][0]
    response = await answer(
        client, context["user"], context["session"]["session_id"], question["word_id"], "wrong"
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["is_correct"] is False
    assert body["correct_spelling"] == "alpha"
    assert body["example_en"] == "Example for alpha."
    assert body["example_cn"] == "alpha 的例句。"
    assert body["mastery_level"] == 1


async def test_strict_and_loose_mode_for_icecream(client: AsyncClient) -> None:
    context = await build_context(client, "mode", ["ice cream"])
    strict_session = await create_practice_session(
        client, context["user"], context["wordbook_id"], True
    )
    loose_session = await create_practice_session(
        client, context["user"], context["wordbook_id"], False
    )

    strict_response = await answer(
        client,
        context["user"],
        strict_session["session_id"],
        strict_session["questions"][0]["word_id"],
        "icecream",
    )
    loose_response = await answer(
        client,
        context["user"],
        loose_session["session_id"],
        loose_session["questions"][0]["word_id"],
        "icecream",
    )

    assert strict_response.status_code == 200
    assert strict_response.json()["data"]["is_correct"] is False
    assert loose_response.status_code == 200
    assert loose_response.json()["data"]["is_correct"] is True


async def test_duplicate_submission_returns_first_result_without_recount(
    client: AsyncClient,
) -> None:
    context = await build_context(client, "duplicate", ["alpha"])
    question = context["session"]["questions"][0]
    first = await answer(
        client, context["user"], context["session"]["session_id"], question["word_id"], "alpha"
    )
    second = await answer(
        client, context["user"], context["session"]["session_id"], question["word_id"], "wrong"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"] == second.json()["data"]

    async with async_session_factory() as session:
        stored_session = await session.get(PracticeSession, context["session"]["session_id"])
        record_count = await session.scalar(
            select(func.count(PracticeRecord.id)).where(
                PracticeRecord.session_id == context["session"]["session_id"],
            ),
        )
        progress = await session.scalar(
            select(WordProgress).where(
                WordProgress.user_id == context["user_id"],
                WordProgress.word_id == question["word_id"],
            ),
        )
        assert stored_session is not None
        assert stored_session.correct_count == 1
        assert record_count == 1
        assert progress is not None
        assert progress.correct_count == 1


async def test_two_consecutive_correct_answers_master_word_and_wrong_resets(
    client: AsyncClient,
) -> None:
    context = await build_context(client, "mastery", ["alpha"])
    word_id = context["session"]["questions"][0]["word_id"]
    first_session = await create_practice_session(client, context["user"], context["wordbook_id"])
    second_session = await create_practice_session(client, context["user"], context["wordbook_id"])
    await answer(client, context["user"], first_session["session_id"], word_id, "alpha")
    second = await answer(client, context["user"], second_session["session_id"], word_id, "alpha")

    assert second.json()["data"]["mastery_level"] == 2

    third_session = await create_practice_session(client, context["user"], context["wordbook_id"])
    wrong = await answer(client, context["user"], third_session["session_id"], word_id, "oops")
    assert wrong.json()["data"]["mastery_level"] == 1

    async with async_session_factory() as session:
        progress = await session.scalar(
            select(WordProgress).where(
                WordProgress.user_id == context["user_id"], WordProgress.word_id == word_id
            )
        )
        wrong_word = await session.scalar(
            select(WrongWord).where(
                WrongWord.user_id == context["user_id"], WrongWord.word_id == word_id
            )
        )
        assert progress is not None and progress.mastery_level == 1
        assert wrong_word is not None and wrong_word.wrong_count == 1


async def test_finished_session_returns_40001(client: AsyncClient) -> None:
    context = await build_context(client, "finished", ["alpha"])
    async with async_session_factory() as session:
        stored_session = await session.get(PracticeSession, context["session"]["session_id"])
        assert stored_session is not None
        stored_session.status = "finished"
        await session.commit()
    response = await answer(
        client,
        context["user"],
        context["session"]["session_id"],
        context["session"]["questions"][0]["word_id"],
        "alpha",
    )
    assert response.status_code == 400
    assert response.json()["code"] == 40001


async def test_other_users_session_returns_40301(client: AsyncClient) -> None:
    context = await build_context(client, "owner", ["alpha"])
    other_user, _ = await create_user(client, "other")
    response = await answer(
        client,
        other_user,
        context["session"]["session_id"],
        context["session"]["questions"][0]["word_id"],
        "alpha",
    )
    assert response.status_code == 403
    assert response.json()["code"] == 40301


async def test_word_not_in_session_returns_40001(client: AsyncClient) -> None:
    context = await build_context(client, "outside", ["alpha"])
    outside_word = await create_word(client, context["admin"], context["wordbook_id"], "outside")
    response = await answer(
        client, context["user"], context["session"]["session_id"], outside_word["id"], "outside"
    )
    assert response.status_code == 400
    assert response.json()["code"] == 40001


async def test_normal_practice_resolves_wrong_word_after_two_correct_answers(
    client: AsyncClient,
) -> None:
    context = await build_context(client, "resolve", ["alpha"])
    word_id = context["session"]["questions"][0]["word_id"]
    await answer(client, context["user"], context["session"]["session_id"], word_id, "wrong")

    second_session = await create_practice_session(client, context["user"], context["wordbook_id"])
    await answer(client, context["user"], second_session["session_id"], word_id, "alpha")
    third_session = await create_practice_session(client, context["user"], context["wordbook_id"])
    await answer(client, context["user"], third_session["session_id"], word_id, "alpha")

    async with async_session_factory() as session:
        wrong_word = await session.scalar(
            select(WrongWord).where(
                WrongWord.user_id == context["user_id"],
                WrongWord.word_id == word_id,
            ),
        )
        assert wrong_word is not None
        assert wrong_word.resolved is True
        assert wrong_word.resolved_at is not None


async def test_wrong_word_stays_unresolved_after_one_correct_answer(client: AsyncClient) -> None:
    context = await build_context(client, "one_correct", ["alpha"])
    word_id = context["session"]["questions"][0]["word_id"]
    await answer(client, context["user"], context["session"]["session_id"], word_id, "wrong")
    second_session = await create_practice_session(client, context["user"], context["wordbook_id"])
    await answer(client, context["user"], second_session["session_id"], word_id, "alpha")

    async with async_session_factory() as session:
        wrong_word = await session.scalar(
            select(WrongWord).where(
                WrongWord.user_id == context["user_id"],
                WrongWord.word_id == word_id,
            ),
        )
        assert wrong_word is not None
        assert wrong_word.resolved is False
        assert wrong_word.resolved_at is None


async def test_wrong_answer_reopens_resolved_wrong_word(client: AsyncClient) -> None:
    context = await build_context(client, "reopen", ["alpha"])
    word_id = context["session"]["questions"][0]["word_id"]
    await answer(client, context["user"], context["session"]["session_id"], word_id, "wrong")
    for _ in range(2):
        correct_session = await create_practice_session(
            client, context["user"], context["wordbook_id"]
        )
        await answer(client, context["user"], correct_session["session_id"], word_id, "alpha")

    wrong_session = await create_practice_session(client, context["user"], context["wordbook_id"])
    await answer(client, context["user"], wrong_session["session_id"], word_id, "wrong")

    async with async_session_factory() as session:
        wrong_word = await session.scalar(
            select(WrongWord).where(
                WrongWord.user_id == context["user_id"],
                WrongWord.word_id == word_id,
            ),
        )
        assert wrong_word is not None
        assert wrong_word.resolved is False
        assert wrong_word.resolved_at is None
        assert wrong_word.wrong_count == 2
