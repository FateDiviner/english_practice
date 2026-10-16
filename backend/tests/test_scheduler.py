"""遗忘曲线与调度算法的单元测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.models.record import UserWordRecord
from core.models.word import Word
from app.services import scheduler


def make_record(**kwargs) -> UserWordRecord:
    """构造一个未落库的练习记录。"""
    defaults = {"user_id": 1, "word_id": 1, "status": scheduler.STATUS_LEARNING}
    defaults.update(kwargs)
    return UserWordRecord(**defaults)


def make_word(word_id: int = 1, sequence: int = 0) -> Word:
    """构造一个未落库的单词。"""
    return Word(
        id=word_id,
        wordbook_id=1,
        word=f"word{word_id}",
        translation="n. 测试",
        sequence=sequence,
    )


class TestStageBounds:
    def test_clamp_below_zero(self):
        assert scheduler.clamp_stage(-3) == 0

    def test_clamp_above_max(self):
        assert scheduler.clamp_stage(99) == len(scheduler.REVIEW_INTERVALS_MINUTES) - 1

    @pytest.mark.parametrize("stage", [0, 1, 2, 3, 4, 5, 6])
    def test_stage_within_range(self, stage: int):
        assert 0 <= scheduler.clamp_stage(stage) <= len(scheduler.REVIEW_INTERVALS_MINUTES) - 1


class TestIntervals:
    def test_intervals_are_increasing(self):
        intervals = scheduler.REVIEW_INTERVALS_MINUTES
        assert intervals == sorted(intervals)
        assert intervals[0] < intervals[-1]

    def test_interval_for_stage_returns_mapped_value(self):
        assert scheduler.interval_for_stage(0) == scheduler.REVIEW_INTERVALS_MINUTES[0]
        assert scheduler.interval_for_stage(100) == scheduler.REVIEW_INTERVALS_MINUTES[-1]

    def test_next_review_is_in_future(self):
        base = datetime(2026, 1, 1, 12, 0, 0)
        assert scheduler.next_review_at(3, base) > base


class TestApplyResult:
    def test_correct_raises_stage_and_counts_right(self):
        record = make_record(ease_stage=1)
        scheduler.apply_result(record, correct=True)
        assert record.ease_stage == 2
        assert record.right_count == 1
        assert record.wrong_count == 0
        assert record.status == scheduler.STATUS_LEARNING

    def test_correct_at_threshold_marks_mastered(self):
        record = make_record(ease_stage=scheduler.MASTERED_STAGE - 1)
        scheduler.apply_result(record, correct=True)
        assert record.status == scheduler.STATUS_MASTERED

    def test_wrong_marks_wrong_book_and_penalises_stage(self):
        record = make_record(ease_stage=3)
        scheduler.apply_result(record, correct=False)
        assert record.status == scheduler.STATUS_WRONG
        assert record.wrong_count == 1
        assert record.ease_stage == 1

    def test_wrong_never_drops_below_zero(self):
        record = make_record(ease_stage=0)
        scheduler.apply_result(record, correct=False)
        assert record.ease_stage == 0
        assert record.status == scheduler.STATUS_WRONG

    def test_stays_in_wrong_book_until_corrected_twice(self):
        """订正一次不应立刻移出错题本，必须达标。"""
        record = make_record()
        scheduler.apply_result(record, correct=False)
        assert record.status == scheduler.STATUS_WRONG

        scheduler.apply_result(record, correct=True)
        assert record.status == scheduler.STATUS_WRONG, "首次订正仍应留在错题本"
        assert record.wrong_count == 1
        assert record.right_count == 1

        scheduler.apply_result(record, correct=True)
        assert record.status != scheduler.STATUS_WRONG, "订正达标后应移出错题本"

    def test_wrong_after_mastered_returns_to_wrong_book(self):
        record = make_record(ease_stage=scheduler.MASTERED_STAGE, status=scheduler.STATUS_MASTERED)
        scheduler.apply_result(record, correct=False)
        assert record.status == scheduler.STATUS_WRONG

    def test_records_timestamps(self):
        record = make_record()
        scheduler.apply_result(record, correct=True)
        assert record.last_practiced is not None
        assert record.next_review_at is not None
        assert record.next_review_at > record.last_practiced


class TestPriority:
    def test_untouched_words_ranks_before_due_mastered(self):
        now = datetime(2026, 1, 1)
        fresh = make_word(word_id=1, sequence=0)
        mastered_due = make_record(
            word_id=2, status=scheduler.STATUS_MASTERED, next_review_at=now - timedelta(days=1)
        )
        assert scheduler._priority(None, fresh, now) < scheduler._priority(
            mastered_due, make_word(word_id=2), now
        )

    def test_due_wrong_ranks_first(self):
        now = datetime(2026, 1, 1)
        due_wrong = make_record(
            word_id=1,
            status=scheduler.STATUS_WRONG,
            wrong_count=5,
            next_review_at=now - timedelta(minutes=1),
        )
        untouched = make_word(word_id=2, sequence=0)
        assert scheduler._priority(due_wrong, make_word(word_id=1), now) < scheduler._priority(
            None, untouched, now
        )

    def test_untouched_follows_wordbook_sequence(self):
        now = datetime(2026, 1, 1)
        later = scheduler._priority(None, make_word(word_id=9, sequence=5), now)
        earlier = scheduler._priority(None, make_word(word_id=8, sequence=1), now)
        assert earlier < later
