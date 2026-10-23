from httpx import AsyncClient

from tests.practice_answer_helpers import (
    build_context,
    create_admin,
    create_practice_session,
    create_user,
    create_word,
    create_wordbook,
)


async def test_audio_requires_login(client: AsyncClient) -> None:
    response = await client.get("/api/v1/words/1/audio")
    assert response.status_code == 401
    assert response.json()["code"] == 40101


async def test_audio_returns_url_and_question_fields(client: AsyncClient) -> None:
    admin = await create_admin(client, "audio")
    user, _ = await create_user(client, "audio")
    wordbook_id = await create_wordbook(client, admin, "audio")
    audio_url = "https://cdn.example.test/alpha.mp3"
    word = await create_word(client, admin, wordbook_id, "alpha", audio_url=audio_url)

    audio = await client.get(f"/api/v1/words/{word['id']}/audio", headers=user)
    words = await client.get(f"/api/v1/wordbooks/{wordbook_id}/words", headers=user)
    session = await create_practice_session(client, user, wordbook_id)

    assert audio.status_code == 200
    assert audio.json()["data"] == {"audio_url": audio_url, "fallback": None}
    assert words.status_code == 200
    assert words.json()["data"]["items"][0]["audio_url"] == audio_url
    assert session["questions"][0]["audio_url"] == audio_url
    assert "spelling" not in session["questions"][0]


async def test_audio_without_url_returns_tts_fallback(client: AsyncClient) -> None:
    context = await build_context(client, "audio_fallback", ["alpha"])
    response = await client.get(
        f"/api/v1/words/{context['words'][0]['id']}/audio",
        headers=context["user"],
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"audio_url": None, "fallback": "tts"}


async def test_audio_word_not_found(client: AsyncClient) -> None:
    user, _ = await create_user(client, "audio_missing")
    response = await client.get("/api/v1/words/999999999/audio", headers=user)

    assert response.status_code == 404
    assert response.json()["code"] == 40401
