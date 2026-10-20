"""词条关系图谱表 word_relations。

这是「精简词汇图谱」，用来替代完整的 Microsoft GraphRAG：
英语词汇的关系是结构化已知的（搭配、派生、易混、近反义），不需要 LLM 抽实体、
跑 Leiden 社区检测再生成社区摘要——那套索引阶段的开销与本项目「本地优先、
零运维」的原则直接冲突。

一张表 + 零 LLM 索引成本，就能命中「abandon 的派生词」「和 give up 有什么区别」
这类纯向量检索很难答好的问题。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# 关系类型。中文标签由前端按此映射，后端只存英文枚举，避免标签漂移
RELATION_COLLOCATION = "collocation"  # 常见搭配
RELATION_DERIVED = "derived"  # 派生词 / 同根词
RELATION_CONFUSE = "confuse"  # 易混词
RELATION_SYNONYM = "synonym"  # 近义词
RELATION_ANTONYM = "antonym"  # 反义词

RELATIONS = (
    RELATION_COLLOCATION,
    RELATION_DERIVED,
    RELATION_CONFUSE,
    RELATION_SYNONYM,
    RELATION_ANTONYM,
)

RELATION_LABELS = {
    RELATION_COLLOCATION: "[搭配]",
    RELATION_DERIVED: "[派生]",
    RELATION_CONFUSE: "[易混]",
    RELATION_SYNONYM: "[近义]",
    RELATION_ANTONYM: "[反义]",
}


class WordRelation(Base):
    """一条词条关系边。

    tail_word 存文本而非外键：搭配与近义词经常不在词库内（如 give up），
    强制建外键会逼着运营方先把这些词也录成词条，不现实。
    """

    __tablename__ = "word_relations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    head_word_id: Mapped[int] = mapped_column(
        ForeignKey("words.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tail_word: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    # collocation / derived / confuse / synonym / antonym
    relation: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    # 中文说明，例如「后接名词，表示不顾危险继续做」
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = ({"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},)
