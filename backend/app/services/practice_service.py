"""默写练习核心业务：开场选词、即时校验、提示、结算与错题本。"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import STATUS_ACTIVE
from app.models.record import UserWordRecord
from app.models.word import Word
from app.schemas.practice import (
    DiffCell,
    HintResponse,
    PracticeStartResponse,
    SettlementItem,
    SettlementResponse,
    SubmitResponse,
    WordClue,
    WrongBookItem,
    WrongBookResponse,
)
from app.services import scheduler, stats_service

# 例句中目标词的挖空占位
BLANK_CHAR = "_"

# 长候选必须排在短候选之前，否则 "vt." 会先被 "v" 吃掉
_POS_PATTERN = re.compile(
    r"^\s*((?:conj|prep|pron|adj|adv|num|art|aux|intj|int|vt|vi|n|v)"
    r"\.?(?:\s*/\s*[a-z]+\.?)?)"
)


# --------------------------------------------------------------------------
# 练习会话（进程内缓存）
# 作答结果在每次 submit 时即写入数据库，进程内仅保存本组切词顺序与耗时，
# 因此即使会话丢失，用户的练习进度与错题记录也绝不丢失。
# --------------------------------------------------------------------------
@dataclass
class PracticeSession:
    """一次练习的临时状态。"""

    id: str
    user_id: int
    wordbook_id: int
    mode: str
    word_ids: list[int]
    started_at: float = field(default_factory=time.time)
    answers: dict[int, str] = field(default_factory=dict)
    skipped: dict[int, bool] = field(default_factory=dict)
    correct: dict[int, bool] = field(default_factory=dict)
    finished: bool = False


_SESSIONS: dict[str, PracticeSession] = {}
_SESSION_LOCK = threading.Lock()
_SESSION_TTL_SECONDS = 2 * 60 * 60


def _prune_sessions(now: float | None = None) -> None:
    """清理过期会话，避免内存无限增长。"""
    current = now or time.time()
    expired = [
        key
        for key, session in _SESSIONS.items()
        if current - session.started_at > _SESSION_TTL_SECONDS
    ]
    for key in expired:
        _SESSIONS.pop(key, None)


def clear_sessions() -> None:
    """清空全部会话（供测试隔离使用）。"""
    with _SESSION_LOCK:
        _SESSIONS.clear()


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------
def normalize_answer(text: str) -> str:
    """去首尾空格、合并多余空白、统一小写（专有名词场景可另行放宽）。"""
    return re.sub(r"\s+", " ", text.strip()).lower()


def extract_pos(translation: str) -> str:
    """从中文释义中抽取词性标注，如 `v. 放弃，遗弃` -> `v.`。"""
    match = _POS_PATTERN.match(translation or "")
    return match.group(1).strip() if match else ""


def mask_example(example: str, word: str) -> str:
    """将例句中的目标词及其屈折形式一并挖空，防止从例句反查拼写。

    仅在词首边界处匹配并吃掉后续字母，因此 "abandon" 会连同 "abandoned" 一起挖空，
    而 "form" 不会命中 "information"（词中无边界），避免误伤其他单词。
    """

    if not example or not word:
        return example or ""
    pattern = re.compile(rf"\b{re.escape(word)}[a-z]*", re.IGNORECASE)
    return pattern.sub(lambda match: BLANK_CHAR * len(match.group(0)), example)


def build_diff(submitted: str, answer: str) -> list[DiffCell]:
    """逐字符对齐比对，供前端标红错误片段并补出漏写字母。

    状态：same 正确 / wrong 提交错字 / extra 多余字符 / missing 漏写字符。
    """
    matcher = SequenceMatcher(a=submitted, b=answer, autojunk=False)
    cells: list[DiffCell] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            cells.extend(DiffCell(char=c, status="same") for c in submitted[i1:i2])
        elif tag == "replace":
            left, right = submitted[i1:i2], answer[j1:j2]
            width = max(len(left), len(right))
            for index in range(width):
                if index < len(left):
                    cells.append(DiffCell(char=left[index], status="wrong"))
                if index < len(right):
                    cells.append(DiffCell(char=right[index], status="missing"))
        elif tag == "delete":
            cells.extend(DiffCell(char=c, status="extra") for c in submitted[i1:i2])
        else:
            cells.extend(DiffCell(char=c, status="missing") for c in answer[j1:j2])
    return cells


def _to_clue(word: Word) -> WordClue:
    """构造不含答案的默写线索。"""
    return WordClue(
        id=word.id,
        translation=word.translation,
        phonetic=word.phonetic,
        example_en_masked=mask_example(word.example_en, word.word),
        example_cn=word.example_cn,
        pos=extract_pos(word.translation),
        speak=word.word,
    )


# --------------------------------------------------------------------------
# 业务入口
# --------------------------------------------------------------------------
def start_session(
    db: Session, user_id: int, wordbook_id: int, size: int, mode: str
) -> PracticeStartResponse:
    """开启一组练习，选词并一次性下发全部线索。"""
    words = scheduler.select_session_words(db, user_id, wordbook_id, size, mode)
    if not words:
        reason = {"wrong_book": "wrong_book", "review": "review"}.get(mode, "empty")
        raise ValueError(reason)

    session = PracticeSession(
        id=uuid.uuid4().hex,
        user_id=user_id,
        wordbook_id=wordbook_id,
        mode=mode,
        word_ids=[word.id for word in words],
    )
    with _SESSION_LOCK:
        _prune_sessions()
        _SESSIONS[session.id] = session

    return PracticeStartResponse(
        session_id=session.id,
        wordbook_id=wordbook_id,
        mode=mode,
        total=len(words),
        clues=[_to_clue(word) for word in words],
    )


def _get_session(session_id: str, user_id: int) -> PracticeSession:
    """取出并校验会话归属。"""
    with _SESSION_LOCK:
        session = _SESSIONS.get(session_id)
    if session is None:
        raise KeyError("session_not_found")
    if session.user_id != user_id:
        raise PermissionError("session_forbidden")
    return session


def get_hint(db: Session, user_id: int, session_id: str, word_id: int) -> HintResponse:
    """生成首字母提示：仅暴露首字母与词长。"""
    session = _get_session(session_id, user_id)
    word = db.get(Word, word_id)
    if word is None or word.id not in session.word_ids:
        raise KeyError("word_not_in_session")

    spelling = word.word
    masked = spelling[0] + BLANK_CHAR * (len(spelling) - 1)
    return HintResponse(
        word_id=word.id,
        masked=masked,
        first_letter=spelling[0],
        hint_level=1,
    )


def submit_answer(
    db: Session, user_id: int, session_id: str, word_id: int, answer: str, skipped: bool
) -> SubmitResponse:
    """校验一次拼写并立即持久化练习结果。"""
    session = _get_session(session_id, user_id)
    if word_id not in session.word_ids:
        raise KeyError("word_not_in_session")

    word = db.get(Word, word_id)
    if word is None:
        raise KeyError("word_not_found")

    submitted = answer.strip()
    correct = (not skipped) and normalize_answer(submitted) == normalize_answer(word.word)

    record = db.scalar(
        select(UserWordRecord).where(
            UserWordRecord.user_id == user_id, UserWordRecord.word_id == word_id
        )
    )
    if record is None:
        record = UserWordRecord(
            user_id=user_id,
            word_id=word_id,
            status=scheduler.STATUS_LEARNING,
            wrong_count=0,
            right_count=0,
            ease_stage=0,
        )
        db.add(record)

    scheduler.apply_result(record, correct)
    # 每次作答即打卡：练到一半退出也算当天练过，不必等到结算
    stats_service.mark_checkin(db, user_id)
    db.commit()
    db.refresh(record)

    session.answers[word_id] = submitted
    session.skipped[word_id] = skipped
    session.correct[word_id] = correct

    if skipped:
        message = "[已跳过] 正确拼写已计入错题本"
    elif correct:
        message = "[正确] 拼写无误，即将进入下一词"
    else:
        message = "[拼写错误] 请对照正确拼写订正"

    return SubmitResponse(
        correct=correct,
        answer=word.word,
        submitted=submitted,
        pos=extract_pos(word.translation),
        phonetic=word.phonetic,
        translation=word.translation,
        diff=(
            []
            if correct
            else build_diff(normalize_answer(submitted), normalize_answer(word.word))
        ),
        message=message,
        wrong_count=record.wrong_count,
        answered=len(session.answers),
        total=len(session.word_ids),
    )


def finish_session(db: Session, user_id: int, session_id: str) -> SettlementResponse:
    """结算一组练习：正确率、耗时、错词列表。"""
    session = _get_session(session_id, user_id)

    items: list[SettlementItem] = []
    correct_count = 0
    for word_id in session.word_ids:
        word = db.get(Word, word_id)
        if word is None:
            continue
        is_correct = session.correct.get(word_id, False)
        correct_count += 1 if is_correct else 0
        items.append(
            SettlementItem(
                word_id=word.id,
                word=word.word,
                phonetic=word.phonetic,
                translation=word.translation,
                correct=is_correct,
                submitted=session.answers.get(word_id, ""),
                skipped=session.skipped.get(word_id, False),
            )
        )

    total = len(session.word_ids)
    wrong_count = total - correct_count
    duration_ms = int((time.time() - session.started_at) * 1000)
    session.finished = True

    if total > 0:
        stats_service.record_session(
            db,
            user_id=user_id,
            wordbook_id=session.wordbook_id,
            mode=session.mode,
            total=total,
            correct_count=correct_count,
            wrong_count=wrong_count,
            duration_ms=duration_ms,
        )
        db.commit()

    return SettlementResponse(
        session_id=session.id,
        wordbook_id=session.wordbook_id,
        total=total,
        correct_count=correct_count,
        wrong_count=wrong_count,
        accuracy=round(correct_count / total * 100, 1) if total else 0.0,
        duration_ms=duration_ms,
        items=items,
    )


def list_wrong_book(db: Session, user_id: int, limit: int = 200) -> WrongBookResponse:
    """拉取错题本（生词本）条目，按错误次数降序。"""
    rows = db.execute(
        select(UserWordRecord, Word)
        .join(Word, Word.id == UserWordRecord.word_id)
        .where(
            UserWordRecord.user_id == user_id,
            UserWordRecord.status == scheduler.STATUS_WRONG,
        )
        .order_by(UserWordRecord.wrong_count.desc(), UserWordRecord.last_practiced.desc())
        .limit(limit)
    ).all()

    items: list[WrongBookItem] = []
    for record, word in rows:
        items.append(
            WrongBookItem(
                word_id=word.id,
                wordbook_id=word.wordbook_id,
                word=word.word,
                phonetic=word.phonetic,
                translation=word.translation,
                wrong_count=record.wrong_count,
                example_en=word.example_en,
                example_cn=word.example_cn,
                last_practiced=(
                    record.last_practiced.isoformat() if record.last_practiced else None
                ),
                # 下架的错词一律保留展示：静默消失会让用户以为错题数据丢了
                archived=word.status != STATUS_ACTIVE,
            )
        )
    return WrongBookResponse(total=len(items), items=items)
