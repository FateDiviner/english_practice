"""默写练习相关请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiffCell(BaseModel):
    """单字符比对单元，供前端标红错误片段。"""

    char: str
    # same / insert / delete / replace
    status: str


class WordClue(BaseModel):
    """默写线索：给释义、词性、音标与发音文本。

    例句已挖空目标词，防止从例句反查拼写。
    speak 字段是发音所必需的（浏览器 speechSynthesis 只能朗读真实文本），
    与"例句挖空"共同构成防误触的提示边界；见 README 的说明。
    """

    id: int
    translation: str
    phonetic: str
    example_en_masked: str
    example_cn: str
    pos: str = ""
    speak: str


class PracticeStartRequest(BaseModel):
    """开始一组练习的入参。"""

    wordbook_id: int
    size: int = Field(default=10, ge=1, le=50, description="每组词数")
    # wrong_book: 错题专项重练
    mode: str = Field(default="normal", pattern="^(normal|wrong_book)$")


class PracticeStartResponse(BaseModel):
    """练习开场响应：一次性下发本组全部线索，支持纯键盘连续切词。"""

    session_id: str
    wordbook_id: int
    mode: str
    total: int
    clues: list[WordClue]


class HintRequest(BaseModel):
    """获取当前词提示（Tab 触发）。"""

    session_id: str
    word_id: int


class HintResponse(BaseModel):
    """首字母提示：只泄露首字母与长度，不返回完整拼写。"""

    word_id: int
    masked: str
    first_letter: str
    hint_level: int = 1


class SubmitRequest(BaseModel):
    """提交一次拼写。"""

    session_id: str
    word_id: int
    answer: str = Field(max_length=128)
    # 用户是否主动跳过（直接查看答案并计入错题）
    skipped: bool = False


class SubmitResponse(BaseModel):
    """单次提交校验结果。"""

    correct: bool
    answer: str
    submitted: str
    pos: str
    phonetic: str
    translation: str
    diff: list[DiffCell] = Field(default_factory=list)
    message: str
    wrong_count: int = 0
    # 本组已提交进度
    answered: int = 0
    total: int = 0


class SettlementItem(BaseModel):
    """结算卡片中的单词条目。"""

    word_id: int
    word: str
    phonetic: str
    translation: str
    correct: bool
    submitted: str
    skipped: bool


class SettlementResponse(BaseModel):
    """一组练习完毕的结算数据。"""

    session_id: str
    wordbook_id: int
    total: int
    correct_count: int
    wrong_count: int
    accuracy: float
    duration_ms: int
    items: list[SettlementItem]


class WrongBookItem(BaseModel):
    """错题本条目。"""

    word_id: int
    # 错题可能来自不同词书，重练时需要据此定位所属词书
    wordbook_id: int
    word: str
    phonetic: str
    translation: str
    wrong_count: int
    example_en: str
    example_cn: str
    last_practiced: str | None = None


class WrongBookResponse(BaseModel):
    """错题本列表。"""

    total: int
    items: list[WrongBookItem]
