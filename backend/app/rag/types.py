"""RAG 管线的公共类型。

CRAG / Self-RAG / GraphRAG 改的不只是「多几个阶段」，而是控制流：CRAG 加循环，
Self-RAG 加反思调用，GraphRAG 加新检索器。所以阶段与编排必须分两层可插拔，
而 RagContext 是贯穿两层的唯一状态对象——每个 Stage 只读写它。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StageKind(str, Enum):
    """阶段所属的环节，决定它在管线里的位置与能读写 ctx 的哪些字段。"""

    PRE = "pre"  # 查询规整、意图门控、关键词、改写
    RETRIEVE = "retrieve"  # 各路召回，结果 append 到 ctx.candidates
    FUSE = "fuse"  # 多路排名融合
    RERANK = "rerank"  # 重排
    POST = "post"  # 去重、阈值门控、压缩、引用


@dataclass
class Hit:
    """一条候选。score 由各阶段逐步产生，最终决定注入顺序。"""

    # chunk / word / relation
    kind: str
    # bm25 / vector / graph
    source: str
    content: str
    score: float = 0.0
    # 原始排名，RRF 融合要用
    rank: int = 0
    heading: str = ""
    # document_id / word_id / chunk_id / relation 等，供引用与去重
    metadata: dict = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        """去重键：归一化后的正文，避免同一段落被两路各召回一次。"""
        return "".join(self.content.lower().split())


@dataclass
class StageTrace:
    """一个阶段的执行痕迹，是调参的前提。

    没有它，阈值和权重全是盲调；管理端调试页靠它回放一次检索。
    """

    stage: str
    kind: str
    duration_ms: float
    input_count: int
    output_count: int
    note: str = ""


@dataclass
class RagContext:
    """贯穿全管线的唯一状态对象。"""

    query: str
    normalized: str = ""
    # zh / en / mixed
    lang: str = "en"
    keywords: list[str] = field(default_factory=list)
    # 近几轮对话，供「这个词」这类指代还原
    history: list[dict] = field(default_factory=list)
    # 改写后的查询，检索阶段用它而不是原始 query
    retrieval_query: str = ""
    candidates: list[Hit] = field(default_factory=list)
    final: list[Hit] = field(default_factory=list)
    # 注入 prompt 的最终上下文文本
    context: str = ""
    # compress 阶段产出的摘要，key 是候选对象 id；cite 阶段取用
    compressed: dict = field(default_factory=dict, repr=False)
    trace: list[StageTrace] = field(default_factory=list)
    # 门控跳过的原因，便于排查「为什么没检索」
    skipped: str | None = None
    # CRAG 循环轮次，naive 恒为 0
    round: int = 0
    # embedding 调用次数，用于验证「默认路径零额外 LLM 调用」
    embedding_calls: int = 0
    # 阶段给自己的备注，管线会把它并进对应阶段的 trace.note
    notes: list[str] = field(default_factory=list)
    # 数据库会话挂在上下文里，让所有 Stage 的签名保持一致
    db: object | None = field(default=None, repr=False, compare=False)


@dataclass
class RagResult:
    """管线产出，交给 chat 管线组装 prompt 与 SSE 状态帧。"""

    context: str = ""
    hits: list[Hit] = field(default_factory=list)
    skipped: str | None = None
    trace: list[StageTrace] = field(default_factory=list)
    lang: str = "en"
    embedding_calls: int = 0

    @property
    def sources(self) -> list[dict]:
        """给前端渲染来源标签用，去重且保留引用序号。"""
        seen: dict[str, dict] = {}
        for index, hit in enumerate(self.hits, start=1):
            key = f"{hit.kind}:{hit.metadata.get('chunk_id') or hit.metadata.get('word_id')}"
            label = hit.heading or hit.metadata.get("word") or hit.metadata.get("name") or ""
            if key in seen:
                continue
            seen[key] = {
                "index": index,
                "kind": hit.kind,
                "label": label[:60],
                "source": hit.source,
            }
        return list(seen.values())
