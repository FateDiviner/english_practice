"""单词与词书相关模型。"""

from __future__ import annotations

from pydantic import BaseModel


class WordOut(BaseModel):
    """单词完整信息（用于词书浏览与结算复盘，非默写过程）。"""

    id: int
    word: str
    phonetic: str
    translation: str
    example_en: str
    example_cn: str

    model_config = {"from_attributes": True}


class WordBookOut(BaseModel):
    """词书卡片。"""

    id: int
    code: str
    title: str
    description: str
    difficulty: str
    total_words: int

    model_config = {"from_attributes": True}


class WordBookProgress(BaseModel):
    """词书学习进度：已掌握 / 学习中 / 未学习。"""

    wordbook_id: int
    total_words: int
    mastered: int = 0
    learning: int = 0
    wrong: int = 0
    untouched: int = 0
    accuracy: float = 0.0
