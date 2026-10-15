"""端到端 API 测试：认证、词书、默写流程、错题本、AI 流式对话。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


def first_wordbook(client: TestClient) -> dict:
    response = client.get("/api/wordbooks")
    assert response.status_code == 200, response.text
    books = response.json()
    assert books, "词书列表不应为空"
    return books[0]


def parse_sse(text: str) -> list[dict]:
    """解析 SSE 响应体中的全部 data 帧。"""
    frames: list[dict] = []
    for block in text.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    frames.append(json.loads(payload))
    return frames


class TestHealth:
    def test_health(self, client: TestClient):
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        # 未配置凭证时必须走 Mock 降级
        assert body["ai_enabled"] is False


class TestAuth:
    def test_register_and_me(self, client: TestClient):
        response = client.post(
            "/api/auth/register",
            json={"username": "alice_01", "password": "secret123"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user"]["username"] == "alice_01"
        assert body["user"]["is_guest"] is False
        assert "password_hash" not in json.dumps(body)

        token = body["access_token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["username"] == "alice_01"

    def test_duplicate_username_rejected(self, client: TestClient):
        payload = {"username": "dup_user_1", "password": "secret123"}
        assert client.post("/api/auth/register", json=payload).status_code == 200
        second = client.post("/api/auth/register", json=payload)
        assert second.status_code == 409

    def test_short_username_rejected(self, client: TestClient):
        response = client.post(
            "/api/auth/register", json={"username": "ab", "password": "secret123"}
        )
        assert response.status_code == 422

    def test_login_with_wrong_password(self, client: TestClient):
        client.post(
            "/api/auth/register", json={"username": "bob_01", "password": "secret123"}
        )
        response = client.post(
            "/api/auth/login", json={"username": "bob_01", "password": "wrongpass"}
        )
        assert response.status_code == 401

    def test_login_success(self, client: TestClient):
        client.post(
            "/api/auth/register", json={"username": "carol_01", "password": "secret123"}
        )
        response = client.post(
            "/api/auth/login", json={"username": "carol_01", "password": "secret123"}
        )
        assert response.status_code == 200
        assert response.json()["user"]["username"] == "carol_01"

    def test_guest_mode(self, client: TestClient):
        response = client.post("/api/auth/guest")
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["is_guest"] is True
        assert body["user"]["username"].startswith("guest_")

    def test_requests_without_token_are_unauthorized(self, client: TestClient):
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/wordbooks/1/progress").status_code == 401
        assert client.post("/api/practice/start", json={"wordbook_id": 1}).status_code == 401

    def test_invalid_token_rejected(self, client: TestClient):
        response = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not.a.token"}
        )
        assert response.status_code == 401


class TestGuestMigration:
    def test_guest_progress_migrates_on_register(self, client: TestClient):
        """游客期练习的进度，注册后必须迁移到正式账号。"""
        guest = client.post("/api/auth/guest").json()
        guest_headers = {"Authorization": f"Bearer {guest['access_token']}"}
        book = first_wordbook(client)

        start = client.post(
            "/api/practice/start",
            json={"wordbook_id": book["id"], "size": 5},
            headers=guest_headers,
        )
        assert start.status_code == 200, start.text
        session = start.json()
        clue = session["clues"][0]

        submit = client.post(
            "/api/practice/submit",
            json={
                "session_id": session["session_id"],
                "word_id": clue["id"],
                "answer": "definitely-wrong-spelling",
            },
            headers=guest_headers,
        )
        assert submit.status_code == 200
        assert submit.json()["correct"] is False

        guest_id = str(guest["user"]["id"])
        register = client.post(
            "/api/auth/register",
            json={"username": "migrate_user", "password": "secret123"},
            headers={"X-Guest-Id": guest_id},
        )
        assert register.status_code == 200, register.text
        assert register.json()["migrated"] is True

        account_headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
        progress = client.get(
            f"/api/wordbooks/{book['id']}/progress", headers=account_headers
        )
        assert progress.status_code == 200
        assert progress.json()["wrong"] >= 1, "游客期错题必须迁移到新账号"

        # 游客账号本身应已删除
        guest_me = client.get("/api/auth/me", headers=guest_headers)
        assert guest_me.status_code == 401


class TestWordbooks:
    def test_list_and_progress(self, auth_client: TestClient):
        books = auth_client.get("/api/wordbooks").json()
        assert len(books) >= 3
        for book in books:
            for key in ("id", "code", "title", "description", "difficulty", "total_words"):
                assert key in book
            assert book["total_words"] > 0

        progress = auth_client.get(f"/api/wordbooks/{books[0]['id']}/progress")
        assert progress.status_code == 200
        body = progress.json()
        assert body["total_words"] == books[0]["total_words"]
        assert body["untouched"] == body["total_words"], "初始应全部未学习"

    def test_missing_progress_404(self, auth_client: TestClient):
        assert auth_client.get("/api/wordbooks/99999/progress").status_code == 404

    def test_activate(self, auth_client: TestClient):
        books = auth_client.get("/api/wordbooks").json()
        target = books[-1]
        response = auth_client.post(f"/api/wordbooks/{target['id']}/activate")
        assert response.status_code == 200
        me = auth_client.get("/api/auth/me").json()
        assert me["active_wordbook_id"] == target["id"]


class TestPracticeFlow:
    def _start(self, client: TestClient, size: int = 5) -> dict:
        book = first_wordbook(client)
        response = client.post(
            "/api/practice/start", json={"wordbook_id": book["id"], "size": size}
        )
        assert response.status_code == 200, response.text
        return response.json()

    def test_start_returns_clues_without_answer_field(self, auth_client: TestClient):
        session = self._start(auth_client)
        assert session["total"] == 5
        assert len(session["clues"]) == 5

        for clue in session["clues"]:
            # 线索绝不能直接暴露拼写字段
            assert "word" not in clue, f"线索泄露了 word 字段: {clue}"
            assert clue["translation"]
            assert clue["phonetic"].startswith("/")
            assert clue["speak"], "缺少发音文本"

    def test_clue_does_not_leak_spelling_via_example(self, auth_client: TestClient):
        session = self._start(auth_client, size=10)
        from app.db import SessionLocal
        from app.models.word import Word

        with SessionLocal() as db:
            for clue in session["clues"]:
                word = db.get(Word, clue["id"])
                assert word is not None
                masked = clue["example_en_masked"]
                assert word.word.lower() not in masked.lower(), (
                    f"例句挖空未生效，泄露了 {word.word}: {masked}"
                )
                # 屈折形式同样不能残留
                stem = word.word[: max(4, len(word.word) - 2)]
                assert stem not in masked.lower(), (
                    f"例句残留词根 {stem}: {masked}"
                )

    def test_hint_reveals_only_first_letter(self, auth_client: TestClient):
        session = self._start(auth_client, size=1)
        clue = session["clues"][0]
        response = auth_client.post(
            "/api/practice/hint",
            json={"session_id": session["session_id"], "word_id": clue["id"]},
        )
        assert response.status_code == 200, response.text
        hint = response.json()
        assert hint["masked"].startswith(hint["first_letter"])
        assert set(hint["masked"][1:]) == {"_"}
        assert len(hint["masked"]) >= 2

    def test_submit_wrong_then_correct(self, auth_client: TestClient):
        session = self._start(auth_client, size=1)
        clue = session["clues"][0]
        sid = session["session_id"]

        wrong = auth_client.post(
            "/api/practice/submit",
            json={"session_id": sid, "word_id": clue["id"], "answer": "zzzzz"},
        )
        assert wrong.status_code == 200
        body = wrong.json()
        assert body["correct"] is False
        assert body["diff"], "错误提交必须返回逐字符比对结果"
        assert any(cell["status"] == "missing" for cell in body["diff"])
        assert "[拼写错误]" in body["message"]
        assert body["answer"], "必须返回正确拼写供订正"
        assert body["wrong_count"] == 1

        # 原地订正：再答一次
        from app.db import SessionLocal
        from app.models.word import Word

        with SessionLocal() as db:
            word = db.get(Word, clue["id"])
            answer = word.word if word else ""

        corrected = auth_client.post(
            "/api/practice/submit",
            json={"session_id": sid, "word_id": clue["id"], "answer": answer.upper()},
        )
        assert corrected.status_code == 200
        fixed = corrected.json()
        assert fixed["correct"] is True, "忽略大小写后应判定正确"
        assert "[正确]" in fixed["message"]

    def test_skip_counts_as_wrong(self, auth_client: TestClient):
        session = self._start(auth_client, size=1)
        clue = session["clues"][0]
        response = auth_client.post(
            "/api/practice/submit",
            json={
                "session_id": session["session_id"],
                "word_id": clue["id"],
                "answer": "",
                "skipped": True,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["correct"] is False
        assert "[已跳过]" in body["message"]

    def test_submit_unknown_word_rejected(self, auth_client: TestClient):
        session = self._start(auth_client, size=1)
        response = auth_client.post(
            "/api/practice/submit",
            json={
                "session_id": session["session_id"],
                "word_id": 999999,
                "answer": "x",
            },
        )
        assert response.status_code == 404

    def test_foreign_session_rejected(self, auth_client: TestClient, client: TestClient):
        """他人会话必须拒绝（越权防护）。"""
        session = self._start(auth_client, size=1)
        other = client.post(
            "/api/auth/register",
            json={"username": "intruder_9", "password": "secret123"},
        ).json()
        response = client.post(
            "/api/practice/submit",
            json={
                "session_id": session["session_id"],
                "word_id": session["clues"][0]["id"],
                "answer": "x",
            },
            headers={"Authorization": f"Bearer {other['access_token']}"},
        )
        assert response.status_code == 403

    def test_settlement(self, auth_client: TestClient):
        session = self._start(auth_client, size=5)
        sid = session["session_id"]
        from app.db import SessionLocal
        from app.models.word import Word

        with SessionLocal() as db:
            answers = {c["id"]: (db.get(Word, c["id"]).word if db.get(Word, c["id"]) else "")
                       for c in session["clues"]}

        # 前 3 个答对，后 2 个答错
        for index, clue in enumerate(session["clues"]):
            auth_client.post(
                "/api/practice/submit",
                json={
                    "session_id": sid,
                    "word_id": clue["id"],
                    "answer": answers[clue["id"]] if index < 3 else "zzzz",
                },
            )

        finish = auth_client.post(f"/api/practice/finish?session_id={sid}")
        assert finish.status_code == 200, finish.text
        settle = finish.json()
        assert settle["total"] == 5
        assert settle["correct_count"] == 3
        assert settle["wrong_count"] == 2
        assert settle["accuracy"] == 60.0
        assert settle["duration_ms"] >= 0
        assert len(settle["items"]) == 5
        wrong_items = [i for i in settle["items"] if not i["correct"]]
        assert all(i["submitted"] for i in wrong_items)

    def test_progress_persists_after_session_ends(self, auth_client: TestClient):
        """刷新 / 会话丢失后，练习进度绝不能丢。"""
        book = first_wordbook(auth_client)
        session = self._start(auth_client, size=3)
        clue = session["clues"][0]
        auth_client.post(
            "/api/practice/submit",
            json={
                "session_id": session["session_id"],
                "word_id": clue["id"],
                "answer": "totally-wrong",
            },
        )

        progress = auth_client.get(f"/api/wordbooks/{book['id']}/progress").json()
        assert progress["wrong"] >= 1, "提交后即使会话消失，错题状态也应已落库"


class TestWrongBook:
    def test_wrong_book_lists_misses_and_allows_repractice(
        self, auth_client: TestClient
    ):
        book = first_wordbook(auth_client)
        assert auth_client.get("/api/practice/wrong-book").json()["total"] == 0

        session = auth_client.post(
            "/api/practice/start", json={"wordbook_id": book["id"], "size": 3}
        ).json()
        for clue in session["clues"]:
            auth_client.post(
                "/api/practice/submit",
                json={
                    "session_id": session["session_id"],
                    "word_id": clue["id"],
                    "answer": "nope",
                },
            )

        wrong = auth_client.get("/api/practice/wrong-book")
        assert wrong.status_code == 200
        payload = wrong.json()
        assert payload["total"] == 3
        for item in payload["items"]:
            assert item["wordbook_id"] == book["id"]
            assert item["wrong_count"] >= 1
            assert item["word"]

        # 错题专项重练
        retry = auth_client.post(
            "/api/practice/start",
            json={"wordbook_id": book["id"], "size": 10, "mode": "wrong_book"},
        )
        assert retry.status_code == 200, retry.text
        retry_body = retry.json()
        assert retry_body["mode"] == "wrong_book"
        assert retry_body["total"] == 3, "错题重练应只包含错题"

    def test_empty_wrong_book_returns_400(self, auth_client: TestClient):
        book = first_wordbook(auth_client)
        response = auth_client.post(
            "/api/practice/start",
            json={"wordbook_id": book["id"], "size": 5, "mode": "wrong_book"},
        )
        assert response.status_code == 400
        assert "错题本为空" in response.json()["detail"]


class TestChat:
    def test_stream_replies_and_persists(self, auth_client: TestClient):
        response = auth_client.post(
            "/api/chat/send", json={"content": "I am agree with you."}
        )
        assert response.status_code == 200, response.text
        assert "text/event-stream" in response.headers["content-type"]

        frames = parse_sse(response.text)
        assert frames, "SSE 未返回任何数据帧"
        assert frames[0]["type"] == "start"

        deltas = [f for f in frames if f["type"] == "delta"]
        assert deltas, "缺少逐字流式 delta"
        assert all(isinstance(f["delta"], str) and f["delta"] for f in deltas)

        done = [f for f in frames if f["type"] == "done"]
        assert done, "缺少结束帧"
        assert done[0]["content"], "结束帧应包含完整回复"
        # 纠错区块应被结构化拆出
        assert done[0]["feedback"] is not None
        assert "agree" in done[0]["feedback"]["grammar"]
        assert done[0]["feedback"]["polish"], "应给出地道表达建议"

        joined = "".join(f["delta"] for f in deltas)
        # done.content 是剔除纠错区块标题后的正文，故应等于 [语法指正] 之前的部分
        body = joined.split("[语法指正]", 1)[0].strip()
        assert done[0]["content"] == body, "落库正文应为流式文本去掉纠错区块后的部分"
        assert "[语法指正]" in joined, "原始流式文本必须携带纠错区块"
        assert done[0]["feedback"]["grammar"] not in body, "纠错区块不应重复出现在正文中"

    def test_history_and_clear(self, auth_client: TestClient):
        auth_client.post("/api/chat/send", json={"content": "Hello there"})
        auth_client.post("/api/chat/send", json={"content": "How are you"})

        history = auth_client.get("/api/chat/messages")
        assert history.status_code == 200
        messages = history.json()
        assert len(messages) >= 4, "应包含两条用户消息与两条助手回复"
        assert messages[-1]["role"] == "assistant"

        cleared = auth_client.delete("/api/chat/messages")
        assert cleared.status_code == 200
        assert auth_client.get("/api/chat/messages").json() == []

    def test_empty_message_rejected(self, auth_client: TestClient):
        response = auth_client.post("/api/chat/send", json={"content": "   "})
        assert response.status_code == 422

    def test_preset_reply(self, auth_client: TestClient):
        response = auth_client.post(
            "/api/chat/send", json={"content": "", "preset": "grammar_check"}
        )
        # 空内容会被 422 拒绝；带内容的预设应正常返回
        assert response.status_code == 422

        response = auth_client.post(
            "/api/chat/send",
            json={"content": "Please check my sentence.", "preset": "grammar_check"},
        )
        assert response.status_code == 200
        frames = parse_sse(response.text)
        assert any(f["type"] == "done" for f in frames)

    @pytest.mark.parametrize("preset", ["explain_word", "grammar_check", "free_chat"])
    def test_all_presets_stream(self, auth_client: TestClient, preset: str):
        response = auth_client.post(
            "/api/chat/send", json={"content": "open", "preset": preset}
        )
        assert response.status_code == 200
        frames = parse_sse(response.text)
        assert any(f["type"] == "done" for f in frames)
