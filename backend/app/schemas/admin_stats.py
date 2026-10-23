from pydantic import BaseModel


class AdminOverviewOut(BaseModel):
    total_users: int
    active_users: int
    total_wordbooks: int
    total_words: int
    today_sessions: int
    today_answers: int
