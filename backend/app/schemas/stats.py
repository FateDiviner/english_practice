from datetime import date

from pydantic import BaseModel


class StatsOverviewOut(BaseModel):
    total_practiced: int
    accuracy: float
    streak_days: int
    mastered_words: int
    wrong_words_count: int


class StatsDailyItem(BaseModel):
    date: date
    answered: int
    correct: int


class StatsDailyOut(BaseModel):
    items: list[StatsDailyItem]
