"""词条关系图谱服务。

与 word_admin_service 分开：后者已经 500 多行且职责是词书/词条本身，
关系边是另一套生命周期（增删改频繁、无校验先行的需求、检索时按词批量取）。
"""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.relation import WordRelation
from app.models.user import User
from app.models.word import Word
from app.schemas.admin import (
    WordRelationCreateRequest,
    WordRelationOut,
    WordRelationUpdateRequest,
)
from app.services import audit_service
from app.services.admin_errors import AdminError


def to_relation_out(relation: WordRelation) -> WordRelationOut:
    """转成管理端视图。"""
    return WordRelationOut(
        id=relation.id,
        head_word_id=relation.head_word_id,
        tail_word=relation.tail_word,
        relation=relation.relation,
        note=relation.note,
    )


def list_relations(db: Session, word_id: int) -> list[WordRelationOut]:
    """列出某个词条的全部关系边。"""
    rows = db.scalars(
        select(WordRelation).where(WordRelation.head_word_id == word_id).order_by(
            WordRelation.id
        )
    ).all()
    return [to_relation_out(row) for row in rows]


def create_relation(
    db: Session,
    actor: User,
    word_id: int,
    payload: WordRelationCreateRequest,
    request: Request | None = None,
) -> WordRelation:
    """给词条加一条关系边。同一 (词, 关系, 对象) 不重复建。"""
    word = db.get(Word, word_id)
    if word is None:
        raise AdminError("词条不存在", status_code=404)

    tail = payload.tail_word.strip()
    existing = db.scalar(
        select(WordRelation).where(
            WordRelation.head_word_id == word_id,
            WordRelation.relation == payload.relation,
            WordRelation.tail_word == tail,
        )
    )
    if existing is not None:
        raise AdminError("该关系已存在", status_code=409)

    relation = WordRelation(
        head_word_id=word_id,
        tail_word=tail,
        relation=payload.relation,
        note=payload.note.strip(),
    )
    db.add(relation)
    audit_service.record(
        db,
        actor=actor,
        action="word.relation_create",
        target_type="word",
        target_id=word_id,
        detail={"word": word.word, "relation": payload.relation, "tail": tail},
        affected_rows=1,
        request=request,
    )
    db.commit()
    db.refresh(relation)
    return relation


def update_relation(
    db: Session,
    actor: User,
    relation_id: int,
    payload: WordRelationUpdateRequest,
    request: Request | None = None,
) -> WordRelation:
    """编辑关系边。空 payload 直接拒绝，避免写出「什么都没改」的审计。"""
    relation = db.get(WordRelation, relation_id)
    if relation is None:
        raise AdminError("关系记录不存在", status_code=404)

    changes: dict[str, str] = {}
    if payload.tail_word is not None:
        relation.tail_word = payload.tail_word.strip()
        changes["tail_word"] = relation.tail_word
    if payload.relation is not None:
        relation.relation = payload.relation
        changes["relation"] = relation.relation
    if payload.note is not None:
        relation.note = payload.note.strip()
        changes["note"] = relation.note

    if not changes:
        raise AdminError("没有需要更新的字段", status_code=400)

    word = db.get(Word, relation.head_word_id)
    audit_service.record(
        db,
        actor=actor,
        action="word.relation_update",
        target_type="word",
        target_id=relation.head_word_id,
        detail={"word": word.word if word else "", **changes},
        affected_rows=1,
        request=request,
    )
    db.commit()
    db.refresh(relation)
    return relation


def delete_relation(
    db: Session, actor: User, relation_id: int, request: Request | None = None
) -> None:
    """删除关系边。关系是辅助信息，删掉不影响用户的练习记录。"""
    relation = db.get(WordRelation, relation_id)
    if relation is None:
        raise AdminError("关系记录不存在", status_code=404)

    word = db.get(Word, relation.head_word_id)
    audit_service.record(
        db,
        actor=actor,
        action="word.relation_delete",
        target_type="word",
        target_id=relation.head_word_id,
        detail={
            "word": word.word if word else "",
            "relation": relation.relation,
            "tail": relation.tail_word,
        },
        affected_rows=1,
        request=request,
    )
    db.delete(relation)
    db.commit()


def neighbors(db: Session, word_ids: list[int]) -> dict[int, list[WordRelation]]:
    """按词批量取关系邻居，供检索时一次查完，避免 N+1。"""
    if not word_ids:
        return {}
    rows = db.scalars(
        select(WordRelation).where(WordRelation.head_word_id.in_(word_ids))
    ).all()
    grouped: dict[int, list[WordRelation]] = {}
    for row in rows:
        grouped.setdefault(row.head_word_id, []).append(row)
    return grouped
