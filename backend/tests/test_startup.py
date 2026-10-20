"""应用启动路径的测试。

词书播种曾经只存在于 scripts/init_db 里，而容器跑的是 main.py——
不手动执行那条脚本的话 wordbooks 与 words 会一直是空表，
界面上表现为「没有词书」。这条契约钉在这里，避免再退回去。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.models.word import Word
from app.models.wordbook import WordBook


class TestStartupSeedsWordbooks:
    def test_lifespan_imports_builtin_books(self, db) -> None:
        books = db.scalars(select(WordBook)).all()
        words = db.scalar(select(func.count()).select_from(Word))

        assert len(books) >= 3, "PRD 要求 3~4 本预置词书"
        assert words > 0, "词书有了但没有词条，词书中心会显示空"
        # 管理端用例会建空词书，它们也在同一张表里，不能一并断言
        assert any(book.total_words > 0 for book in books)

    def test_seeding_is_idempotent(self) -> None:
        """重复启动不能把词书翻倍。seed_wordbooks 对已存在的 code 只补缺失词条。"""
        with SessionLocal() as first:
            before_books = first.scalar(select(func.count()).select_from(WordBook))
            before_words = first.scalar(select(func.count()).select_from(Word))

        # 再走一次启动路径（TestClient 的 lifespan）
        with TestClient(app):
            pass

        with SessionLocal() as after:
            assert after.scalar(select(func.count()).select_from(WordBook)) == before_books
            assert after.scalar(select(func.count()).select_from(Word)) == before_words

    def test_wordbooks_visible_to_users(self, client: TestClient) -> None:
        """播种之后用户端必须能直接看到词书，不需要额外的初始化步骤。"""
        response = client.get("/api/wordbooks")
        assert response.status_code == 200
        books = response.json()
        assert books, "用户端 /api/wordbooks 返回空，说明启动时没播种"
        # 管理端新建但尚未导词的书也是 active，会出现在这里，词数为 0 属正常
        assert any(book["total_words"] > 0 for book in books)


class TestStartupIsResilient:
    def test_seeding_failure_does_not_block_startup(self, monkeypatch) -> None:
        """播种失败只记日志，不能让服务起不来。

        否则连排查问题的接口都访问不到——这是最糟的失败形态。
        打的是 seed_wordbooks 而不是 _seed_wordbooks：后者内部才有
        try/except，替换掉它等于把要测的容错逻辑也一起换没了。
        """
        from scripts import init_db as init_script

        def boom(force: bool = False):
            raise RuntimeError("数据库还没就绪")

        monkeypatch.setattr(init_script, "seed_wordbooks", boom)
        # 能进入 lifespan 并正常响应，说明启动没被播种失败打断
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200
