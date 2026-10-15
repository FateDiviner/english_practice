"""初始化数据库并导入内置词书（幂等，可重复执行）。

用法：
    cd backend
    python -m scripts.init_db
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models.word import Word
from app.models.wordbook import WordBook

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def seed_wordbooks(force: bool = False) -> dict[str, int]:
    """从 backend/data/*.json 导入词书与单词。

    同一 code 的词书已存在且未指定 force 时，仅补齐缺失的单词，不重复插入。
    """
    stats = {"books": 0, "words": 0, "skipped": 0}
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"未在 {DATA_DIR} 找到任何词书数据文件")

    with SessionLocal() as db:
        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            code = payload["code"]

            book = db.scalar(select(WordBook).where(WordBook.code == code))
            if book is None:
                book = WordBook(
                    code=code,
                    title=payload["title"],
                    description=payload.get("description", ""),
                    difficulty=payload.get("difficulty", ""),
                )
                db.add(book)
                db.flush()
                stats["books"] += 1
            else:
                book.title = payload["title"]
                book.description = payload.get("description", "")
                book.difficulty = payload.get("difficulty", "")

            existing = {
                row.word.lower()
                for row in db.scalars(
                    select(Word).where(Word.wordbook_id == book.id)
                ).all()
            }
            if force:
                db.query(Word).filter(Word.wordbook_id == book.id).delete()
                db.flush()
                existing = set()

            for sequence, item in enumerate(payload["words"]):
                if item["word"].lower() in existing:
                    stats["skipped"] += 1
                    continue
                db.add(
                    Word(
                        wordbook_id=book.id,
                        word=item["word"],
                        phonetic=item.get("phonetic", ""),
                        translation=item.get("translation", ""),
                        example_en=item.get("example_en", ""),
                        example_cn=item.get("example_cn", ""),
                        sequence=sequence,
                    )
                )
                stats["words"] += 1

            # 会话 autoflush=False，必须先落盘再统计，否则查不到刚插入的单词
            db.flush()
            count = len(
                list(db.scalars(select(Word).where(Word.wordbook_id == book.id)).all())
            )
            book.total_words = count
            print(f"[词书] {book.title} -> {count} 词")

        db.commit()
    return stats


def main() -> int:
    """入口：建表 + 导入词书。"""
    force = "--force" in sys.argv
    init_db()
    print("[数据库] 表结构已就绪")
    stats = seed_wordbooks(force=force)
    print(
        f"[导入完成] 新增词书 {stats['books']} 本，新增单词 {stats['words']} 个，"
        f"跳过已存在 {stats['skipped']} 个"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
