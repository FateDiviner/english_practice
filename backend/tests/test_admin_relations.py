"""词条关系图谱接口测试。

关系边是精简词汇图谱的全部内容：零 LLM 索引成本，靠管理端人工维护，
检索侧按词批量取邻居。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.relation import WordRelation
from app.models.word import Word
from app.services import relation_service
from tests.admin_helpers import good_book, good_word, headers, make_admin, make_user, unique_name


def _setup(client: TestClient, db: Session) -> tuple[str, int]:
    """建一个管理员和一本带一个词的词书，返回 (token, word_id)。"""
    token = make_admin(db, client, unique_name("rel_admin"))["access_token"]
    book = client.post(
        "/api/admin/wordbooks",
        json=good_book(code=unique_name("wb_rel")[:32]),
        headers=headers(token),
    ).json()
    word = client.post(
        f"/api/admin/wordbooks/{book['id']}/words",
        json=good_word(),
        headers=headers(token),
    ).json()
    return token, word["id"]


def _add(client: TestClient, token: str, word_id: int, **payload) -> dict:
    body = {"tail_word": "give up", "relation": "synonym", "note": "近义"}
    body.update(payload)
    response = client.post(
        f"/api/admin/words/{word_id}/relations", json=body, headers=headers(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


def _count_relations(db: Session, word_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(WordRelation)
            .where(WordRelation.head_word_id == word_id)
        )
        or 0
    )


class TestPermissionGate:
    def test_plain_user_403(self, client: TestClient, db: Session) -> None:
        token, word_id = _setup(client, db)
        plain = make_user(db, client, unique_name("rel_plain"))
        response = client.get(
            f"/api/admin/words/{word_id}/relations", headers=headers(plain["access_token"])
        )
        assert response.status_code == 403
        assert token  # 管理员建的词书仍在


class TestRelationCrud:
    def test_create_and_list(self, client: TestClient, db: Session) -> None:
        token, word_id = _setup(client, db)
        created = _add(client, token, word_id)
        assert created["tail_word"] == "give up"
        assert created["relation"] == "synonym"

        listing = client.get(
            f"/api/admin/words/{word_id}/relations", headers=headers(token)
        ).json()
        assert len(listing) == 1
        assert listing[0]["id"] == created["id"]

    def test_all_relation_types_accepted(self, client: TestClient, db: Session) -> None:
        token, word_id = _setup(client, db)
        types = client.get("/api/admin/relations/types", headers=headers(token)).json()["types"]
        assert set(types) == {"collocation", "derived", "confuse", "synonym", "antonym"}
        for index, relation in enumerate(types):
            created = _add(
                client, token, word_id, tail_word=f"t{index}", relation=relation
            )
            assert created["relation"] == relation

    def test_invalid_relation_422(self, client: TestClient, db: Session) -> None:
        token, word_id = _setup(client, db)
        response = client.post(
            f"/api/admin/words/{word_id}/relations",
            json={"tail_word": "x", "relation": "nonsense"},
            headers=headers(token),
        )
        assert response.status_code == 422

    def test_duplicate_409(self, client: TestClient, db: Session) -> None:
        token, word_id = _setup(client, db)
        _add(client, token, word_id)
        response = client.post(
            f"/api/admin/words/{word_id}/relations",
            json={"tail_word": "give up", "relation": "synonym"},
            headers=headers(token),
        )
        assert response.status_code == 409

    def test_same_tail_different_relation_ok(self, client: TestClient, db: Session) -> None:
        """give up 既可能是近义也可能是易混，同对象不同关系要允许并存。"""
        token, word_id = _setup(client, db)
        _add(client, token, word_id, relation="synonym")
        _add(client, token, word_id, relation="confuse")
        listing = client.get(
            f"/api/admin/words/{word_id}/relations", headers=headers(token)
        ).json()
        assert len(listing) == 2

    def test_update(self, client: TestClient, db: Session) -> None:
        token, word_id = _setup(client, db)
        created = _add(client, token, word_id)
        response = client.patch(
            f"/api/admin/relations/{created['id']}",
            json={"tail_word": "abandon doing", "relation": "collocation",
                  "note": "后接动名词"},
            headers=headers(token),
        )
        assert response.status_code == 200
        assert response.json()["tail_word"] == "abandon doing"
        assert response.json()["relation"] == "collocation"

    def test_update_empty_payload_400(self, client: TestClient, db: Session) -> None:
        """空 payload 要拒绝，否则会写出「什么都没改」的审计。"""
        token, word_id = _setup(client, db)
        created = _add(client, token, word_id)
        response = client.patch(
            f"/api/admin/relations/{created['id']}", json={}, headers=headers(token)
        )
        assert response.status_code == 400

    def test_delete(self, client: TestClient, db: Session) -> None:
        token, word_id = _setup(client, db)
        created = _add(client, token, word_id)
        response = client.delete(
            f"/api/admin/relations/{created['id']}", headers=headers(token)
        )
        assert response.status_code == 200
        assert client.get(
            f"/api/admin/words/{word_id}/relations", headers=headers(token)
        ).json() == []
        assert db.get(WordRelation, created["id"]) is None

    def test_missing_word_404(self, client: TestClient, db: Session) -> None:
        token, _ = _setup(client, db)
        response = client.post(
            "/api/admin/words/999999/relations",
            json={"tail_word": "x", "relation": "synonym"},
            headers=headers(token),
        )
        assert response.status_code == 404


class TestAudit:
    def test_relation_writes_logged(self, client: TestClient, db: Session) -> None:
        token, word_id = _setup(client, db)
        created = _add(client, token, word_id)
        client.patch(
            f"/api/admin/relations/{created['id']}",
            json={"note": "改过的说明"},
            headers=headers(token),
        )
        client.delete(f"/api/admin/relations/{created['id']}", headers=headers(token))

        from sqlalchemy import select

        from app.models.audit import AuditLog

        actions = {
            entry.action for entry in db.scalars(select(AuditLog)).all()
        }
        assert {"word.relation_create", "word.relation_update", "word.relation_delete"} <= actions


class TestCascadesWithWord:
    def test_word_purge_removes_relations(self, client: TestClient, db: Session) -> None:
        """删词要连带删关系边，否则图谱里会留下指向不存在词的悬空边。"""
        token, word_id = _setup(client, db)
        _add(client, token, word_id)
        assert _count_relations(db, word_id) >= 1

        response = client.delete(
            f"/api/admin/words/{word_id}", params={"purge": "true"}, headers=headers(token)
        )
        assert response.status_code == 200, response.text
        assert db.get(Word, word_id) is None
        assert _count_relations(db, word_id) == 0


class TestNeighborsBatch:
    def test_groups_by_word(self, client: TestClient, db: Session) -> None:
        """检索侧按词批量取邻居，必须一次查完而不是 N+1。"""
        token, first_id = _setup(client, db)
        _add(client, token, first_id, tail_word="a")
        _add(client, token, first_id, tail_word="b")

        grouped = relation_service.neighbors(db, [first_id, 999999])
        assert set(grouped) == {first_id}
        assert len(grouped[first_id]) == 2

    def test_empty_input(self, db: Session) -> None:
        assert relation_service.neighbors(db, []) == {}
