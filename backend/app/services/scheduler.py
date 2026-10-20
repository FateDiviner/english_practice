"""单词调度算法与遗忘曲线复习计算。

采用 Leitner 梯箱 + 遗忘曲线间隔的轻量实现：
- 答对：记忆档位上移一格，复习间隔按档位延长；档位封顶后判定为已掌握。
- 答错 / 跳过：记忆档位回落两格，状态置为错题并进入短期复现队列。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import STATUS_ACTIVE
from app.models.record import UserWordRecord
from app.models.word import Word

# 各记忆档位对应的复习间隔（分钟）：5 分钟 / 30 分钟 / 2 小时 / 6 小时 / 1 天 / 3 天 / 7 天
REVIEW_INTERVALS_MINUTES: list[int] = [5, 30, 120, 360, 1440, 4320, 10080]

# 档位达到该值即判定为已掌握
MASTERED_STAGE = 4

# 单次答错后的档位最大回落步数
PENALTY_STEPS = 2

# 进入错题本后，需累计答对这么多次才移出，避免订正一次就从错题本消失
WRONG_BOOK_RELEASE = 2

# next_review_at 为空视为无限期逾期，用一个可排序的大数参与优先级比较
_MAX_LATENESS = 1.0e12

STATUS_LEARNING = "learning"
STATUS_MASTERED = "mastered"
STATUS_WRONG = "wrong"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def clamp_stage(stage: int) -> int:
    """将记忆档位约束在合法范围内。"""
    return max(0, min(stage, len(REVIEW_INTERVALS_MINUTES) - 1))


def interval_for_stage(stage: int) -> int:
    """取指定档位的复习间隔（分钟）。"""
    return REVIEW_INTERVALS_MINUTES[clamp_stage(stage)]


def next_review_at(stage: int, base: datetime | None = None) -> datetime:
    """计算下次复习时间。"""
    anchor = base or _utcnow()
    return anchor + timedelta(minutes=interval_for_stage(stage))


def apply_result(record: UserWordRecord, correct: bool) -> UserWordRecord:
    """根据单次作答结果推进 / 回退记忆状态（就地修改并返回）。"""
    now = _utcnow()

    # 首次作答时记录尚在会话缓冲区、未执行 INSERT，列默认值尚未生效，
    # 必须先归零，否则 None += 1 会直接抛 TypeError。
    if record.right_count is None:
        record.right_count = 0
    if record.wrong_count is None:
        record.wrong_count = 0
    if record.ease_stage is None:
        record.ease_stage = 0

    if correct:
        record.right_count += 1
        record.ease_stage = clamp_stage(record.ease_stage + 1)
        if record.wrong_count > 0 and record.right_count < WRONG_BOOK_RELEASE:
            # 已沉淀进错题本的词必须订正达标才移出，保证错题本真正起到复盘作用
            record.status = STATUS_WRONG
        elif record.ease_stage >= MASTERED_STAGE:
            record.status = STATUS_MASTERED
        else:
            record.status = STATUS_LEARNING
    else:
        record.wrong_count += 1
        record.ease_stage = clamp_stage(record.ease_stage - PENALTY_STEPS)
        record.status = STATUS_WRONG

    record.last_practiced = now
    record.next_review_at = next_review_at(record.ease_stage, now)
    return record


def _priority(record: UserWordRecord | None, word: Word, now: datetime) -> tuple:
    """生成选词优先级元组（元组越小越优先）。

    排序次序：到期待复习错题 > 未学过的新词 > 到期学习中 > 到期已掌握 > 其余。
    """
    if record is None:
        # 新词按词书顺序插入，保证学习节奏贴合词书编排
        return (1, word.sequence, word.id)

    overdue = record.next_review_at is None or record.next_review_at <= now
    if record.status == STATUS_WRONG and overdue:
        return (0, 0, record.wrong_count * -1)
    if record.status == STATUS_WRONG:
        return (0, 1, record.wrong_count * -1)
    if overdue and record.status == STATUS_LEARNING:
        return (2, 0, word.sequence)
    if record.status == STATUS_LEARNING:
        return (3, 0, word.sequence)
    if overdue and record.status == STATUS_MASTERED:
        return (4, 0, word.sequence)
    return (5, 0, word.sequence)


def _end_of_day(now: datetime) -> datetime:
    """取当天最后一刻。

    口径与 _utcnow() 保持一致（均为 UTC），避免同一天存在两种边界。
    """
    return now.replace(hour=23, minute=59, second=59, microsecond=999999)


def _due_bucket(
    record: UserWordRecord, now: datetime, today_end: datetime, horizon: datetime
) -> str | None:
    """把一条记录归入复习分桶：overdue / due_today / upcoming_7d / None。"""
    due_at = record.next_review_at
    if due_at is None or due_at <= now:
        return "overdue"
    if due_at <= today_end:
        return "due_today"
    if due_at <= horizon:
        return "upcoming_7d"
    return None


def _review_priority(record: UserWordRecord, now: datetime) -> tuple:
    """生成复习选词优先级（元组越小越优先）。

    排序次序：逾期越久 > 错得越多 > 答对越少。
    """
    overdue = record.next_review_at is None or record.next_review_at <= now
    lateness = (
        (now - record.next_review_at).total_seconds()
        if record.next_review_at is not None
        else _MAX_LATENESS
    )
    return (
        0 if overdue else 1,
        -lateness,
        -(record.wrong_count or 0),
        -(record.right_count or 0),
    )


def select_session_words(
    db: Session,
    user_id: int,
    wordbook_id: int,
    size: int,
    mode: str = "normal",
) -> list[Word]:
    """为一次练习挑选单词，优先错题与到期复习词。"""
    now = _utcnow()

    words = list(
        db.scalars(
            select(Word)
            .where(Word.wordbook_id == wordbook_id, Word.status == STATUS_ACTIVE)
            .order_by(Word.sequence, Word.id)
        ).all()
    )
    if not words:
        return []

    records = {
        record.word_id: record
        for record in db.scalars(
            select(UserWordRecord).where(
                UserWordRecord.user_id == user_id,
                UserWordRecord.word_id.in_([w.id for w in words]),
            )
        ).all()
    }

    if mode == "wrong_book":
        wrong_words = [
            w
            for w in words
            if (rec := records.get(w.id)) is not None and rec.status == STATUS_WRONG
        ]
        wrong_words.sort(
            key=lambda w: (
                -(records[w.id].wrong_count),
                records[w.id].last_practiced or datetime.min,
            )
        )
        return wrong_words[:size]

    if mode == "review":
        today_end = _end_of_day(now)
        horizon = today_end + timedelta(days=7)
        due_words = [
            word
            for word in words
            if (rec := records.get(word.id)) is not None
            and _due_bucket(rec, now, today_end, horizon) in {"overdue", "due_today"}
        ]
        # 到期词不足 size 时一律不补新词：复习组一旦混入新词，
        # 词书中心那句"今日待复习 N"就失真了
        due_words.sort(key=lambda w: _review_priority(records[w.id], now))
        return due_words[:size]

    ranked = sorted(words, key=lambda w: _priority(records.get(w.id), w, now))
    return ranked[:size]


def compute_progress(db: Session, user_id: int, wordbook_id: int) -> dict[str, int | float]:
    """统计某词书的学习进度。"""
    words = list(
        db.scalars(
            select(Word.id).where(
                Word.wordbook_id == wordbook_id, Word.status == STATUS_ACTIVE
            )
        ).all()
    )
    total_words = len(words)
    if total_words == 0:
        return {
            "wordbook_id": wordbook_id,
            "total_words": 0,
            "mastered": 0,
            "learning": 0,
            "wrong": 0,
            "untouched": 0,
            "accuracy": 0.0,
        }

    records = list(
        db.scalars(
            select(UserWordRecord).where(
                UserWordRecord.user_id == user_id,
                UserWordRecord.word_id.in_(words),
            )
        ).all()
    )
    by_status = {STATUS_MASTERED: 0, STATUS_LEARNING: 0, STATUS_WRONG: 0}
    right_total = 0
    attempt_total = 0
    for record in records:
        if record.status in by_status:
            by_status[record.status] += 1
        right_total += record.right_count
        attempt_total += record.right_count + record.wrong_count

    return {
        "wordbook_id": wordbook_id,
        "total_words": total_words,
        "mastered": by_status[STATUS_MASTERED],
        "learning": by_status[STATUS_LEARNING],
        "wrong": by_status[STATUS_WRONG],
        "untouched": total_words - len(records),
        "accuracy": round(right_total / attempt_total * 100, 1) if attempt_total else 0.0,
    }


def build_review_queue(
    db: Session, user_id: int, wordbook_id: int, preview_limit: int = 10
) -> dict:
    """统计某词书今日的复习压力，并给出不含拼写的预览。

    预览刻意不返回 word 字段：列表一眼扫过就等于背过拼写，
    会与"例句挖空防泄漏"的设计初衷冲突。
    """
    now = _utcnow()
    today_end = _end_of_day(now)
    horizon = today_end + timedelta(days=7)

    words = list(
        db.scalars(
            select(Word).where(
                Word.wordbook_id == wordbook_id, Word.status == STATUS_ACTIVE
            )
        ).all()
    )
    records: dict[int, UserWordRecord] = {}
    if words:
        records = {
            record.word_id: record
            for record in db.scalars(
                select(UserWordRecord).where(
                    UserWordRecord.user_id == user_id,
                    UserWordRecord.word_id.in_([word.id for word in words]),
                )
            ).all()
        }

    counts = {"overdue": 0, "due_today": 0, "upcoming_7d": 0}
    due_items: list[tuple[UserWordRecord, Word]] = []
    for word in words:
        record = records.get(word.id)
        if record is None:
            continue
        bucket = _due_bucket(record, now, today_end, horizon)
        if bucket is None:
            continue
        counts[bucket] += 1
        if bucket in {"overdue", "due_today"}:
            due_items.append((record, word))

    due_items.sort(key=lambda item: _review_priority(item[0], now))
    return {
        "wordbook_id": wordbook_id,
        "total": counts["overdue"] + counts["due_today"],
        "overdue": counts["overdue"],
        "due_today": counts["due_today"],
        "upcoming_7d": counts["upcoming_7d"],
        "preview": [
            {
                "word_id": word.id,
                "translation": word.translation,
                "phonetic": word.phonetic,
                "status": record.status,
                "wrong_count": record.wrong_count,
                "next_review_at": (
                    record.next_review_at.isoformat() if record.next_review_at else None
                ),
            }
            for record, word in due_items[:preview_limit]
        ],
    }
