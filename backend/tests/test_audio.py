from pathlib import Path

from app.services.tts import TtsUnavailableError
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
    assert audio.json()["data"] == {"audio_url": audio_url, "tts_text": None, "fallback": None}
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
    assert response.json()["data"] == {
        "audio_url": None,
        "tts_text": "alpha",
        "fallback": "tts",
    }


async def test_audio_word_not_found(client: AsyncClient) -> None:
    user, _ = await create_user(client, "audio_missing")
    response = await client.get("/api/v1/words/999999999/audio", headers=user)

    assert response.status_code == 404
    assert response.json()["code"] == 40401


async def test_word_audio_file_streams_system_voice(
    client: AsyncClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    context = await build_context(client, "audio_file", ["alpha"])
    word_id = context["words"][0]["id"]
    wav_path = tmp_path / "alpha.wav"
    wav_path.write_bytes(b"RIFF-fake-wav")
    calls: list[tuple[str, str]] = []

    async def fake_synthesize(spelling: str, accent: str = "us") -> Path:
        calls.append((spelling, accent))
        return wav_path

    monkeypatch.setattr("app.api.v1.audio.synthesize_word_audio", fake_synthesize)

    response = await client.get(
        f"/api/v1/words/{word_id}/audio/file?accent=uk",
        headers=context["user"],
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF-fake-wav"
    assert calls == [("alpha", "uk")]


async def test_word_audio_file_rejects_unknown_accent(client: AsyncClient) -> None:
    context = await build_context(client, "audio_accent", ["alpha"])
    response = await client.get(
        f"/api/v1/words/{context['words'][0]['id']}/audio/file?accent=au",
        headers=context["user"],
    )

    assert response.status_code == 422


async def test_word_audio_file_not_found(client: AsyncClient) -> None:
    user, _ = await create_user(client, "audio_file_missing")
    response = await client.get("/api/v1/words/999999999/audio/file", headers=user)

    assert response.status_code == 404
    assert response.json()["code"] == 40401


async def test_word_audio_file_reports_unavailable_voice(
    client: AsyncClient,
    monkeypatch,
) -> None:
    context = await build_context(client, "audio_unavailable", ["alpha"])

    async def fake_synthesize(spelling: str, accent: str = "us") -> Path:
        raise TtsUnavailableError("no voice")

    monkeypatch.setattr("app.api.v1.audio.synthesize_word_audio", fake_synthesize)

    response = await client.get(
        f"/api/v1/words/{context['words'][0]['id']}/audio/file",
        headers=context["user"],
    )

    assert response.status_code == 503
    assert response.json()["code"] == 50301
