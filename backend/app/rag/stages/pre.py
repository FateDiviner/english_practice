"""检索前阶段：查询规整、语言判定、意图门控、关键词、改写。"""

from __future__ import annotations

import re

from app.rag.registry import register_stage
from app.rag.types import RagContext, StageKind

# 全角转半角的映射区间
_FULLWIDTH_START, _FULLWIDTH_END = 0xFF01, 0xFF5E
_HALFWIDTH_OFFSET = 0xFEE0

# 中日韩统一表意文字 + 扩展 A + 兼容表意 + 标点
_CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿぀-ヿ]")
_ENGLISH_TOKEN = re.compile(r"[A-Za-z][A-Za-z'-]{1,}")
_CJK_BIGRAM = re.compile(r"[一-鿿]{2,}")
_QUOTED = re.compile(r"[\"'「『“”‘’]([^\"'「』“”‘’]{2,})[\"'」』“”‘’]")

# 纯寒暄或过短的问题，检索只会引入无关上下文
_SMALLTALK = {
    "hi", "hello", "hey", "thanks", "thank", "ok", "okay", "yes", "no",
    "good", "great", "nice", "bye", "see", "yo", "hmm", "ah", "oh",
}
# 请求纠错、要求翻译、让 AI 接话——这些不需要外部资料
_CORRECTION_HINTS = (
    "correct", "grammar", "mistake", "wrong", "polish", "translate",
    "怎么翻译", "帮我翻译", "纠正", "改一下", "对吗", "语法对吗",
)


@register_stage(StageKind.PRE, "normalize")
def normalize(ctx: RagContext) -> None:
    """去空白与全半角归一，同时保留原始 query 不动。

    原始 query 要留给展示与日志；检索与关键词都用归一后的版本。
    """
    text = ctx.query.strip()
    halfwidth = "".join(
        chr(ord(ch) - _HALFWIDTH_OFFSET)
        if _FULLWIDTH_START <= ord(ch) <= _FULLWIDTH_END
        else ch
        for ch in text
    )
    ctx.normalized = re.sub(r"\s+", " ", halfwidth).strip()
    ctx.retrieval_query = ctx.normalized


@register_stage(StageKind.PRE, "lang_detect")
def lang_detect(ctx: RagContext) -> None:
    """按 CJK 占比判定 zh / en / mixed。

    这是跨语言检索的前提：中文提问要去命中英文原文的知识库，
    知道语言才能决定要不要走查询翻译。
    """
    text = ctx.normalized or ctx.query
    if not text:
        ctx.lang = "en"
        return
    cjk = len(_CJK.findall(text))
    latin = len(re.findall(r"[A-Za-z]", text))
    total = cjk + latin
    if total == 0:
        ctx.lang = "en"
        return
    ratio = cjk / total
    if ratio >= 0.6:
        ctx.lang = "zh"
    elif ratio <= 0.2:
        ctx.lang = "en"
    else:
        ctx.lang = "mixed"


@register_stage(StageKind.PRE, "intent_gate")
def intent_gate(ctx: RagContext) -> None:
    """判断这一轮是否需要检索。

    伴学对话里大半轮次是短句纠错、寒暄或模型自己在接话。每轮都去打一次
    embedding，既烧延迟又会用无关上下文污染原本很稳的纠错行为——
    RAG 不该劣化现有的纠错能力。
    """
    text = (ctx.normalized or ctx.query).strip()
    if not text:
        ctx.skipped = "空消息"
        return
    if len(text) < 3:
        ctx.skipped = "输入过短"
        return

    lowered = text.lower()
    if lowered.strip(" .!?。，！？") in _SMALLTALK:
        ctx.skipped = "寒暄"
        return

    # 纠错请求靠现有的 prompt 与纠错区块就够了，不需要外部资料
    if any(hint in lowered for hint in _CORRECTION_HINTS) and len(text) < 40:
        ctx.skipped = "纠错类请求，走现有纠错流程"
        return


@register_stage(StageKind.PRE, "keywords")
def keywords(ctx: RagContext) -> None:
    """抽取英文 token 与中文 2-gram，供 BM25 与重排使用。

    不装分词器：中文召回靠 2-gram 与向量两路互补，
    为这个场景引入 jieba 只会多一个依赖而收益有限。
    """
    text = ctx.normalized or ctx.query
    found: list[str] = []

    # 引号里的一般是被点名的词，权重最高，放最前
    for match in _QUOTED.finditer(text):
        found.append(match.group(1).strip().lower())

    for token in _ENGLISH_TOKEN.findall(text):
        lowered = token.lower()
        if len(lowered) >= 3 and lowered not in found:
            found.append(lowered)

    for match in _CJK_BIGRAM.finditer(text):
        found.append(match.group(0))

    ctx.keywords = found[:24]


@register_stage(StageKind.PRE, "rewrite")
def rewrite(ctx: RagContext) -> None:
    """结合对话历史还原指代，让检索拿到的不是「这个词」。

    只做确定性改写，不调模型——加一次 LLM 调用会吃掉 2 秒首字延迟预算。

    刻意不做拼写纠正：那要逐个字母试删再查库，延迟不可控，而且一旦把
    专有名词改错，检索结果会比不改更糟。学习者的笔误交给 BM25 的模糊度
    与向量的语义相似度去兜。
    """
    text = ctx.normalized or ctx.query

    # 「这个词 / 这个词怎么用 / 上面那个」→ 取最近一轮里被点名的英文词
    if re.search(r"这个词|这个单词|上面那个|刚才那个|它", text) and ctx.history:
        mentioned = _latest_mentioned_word(ctx.history)
        if mentioned:
            text = re.sub(
                r"这个词|这个单词|上面那个|刚才那个|它", mentioned, text
            )
            ctx.retrieval_query = text



def _latest_mentioned_word(history: list[dict]) -> str | None:
    """从最近几轮对话里找出最近被提到的英文单词。"""
    for message in reversed(history[-6:]):
        content = message.get("content") or ""
        # 优先取被点名的词（引号、加粗、独立成句）
        for match in _QUOTED.finditer(content):
            candidate = match.group(1).strip()
            if candidate.isascii() and 2 < len(candidate) < 32:
                return candidate
        tokens = _ENGLISH_TOKEN.findall(content)
        if tokens:
            # 避免把 the / and 这类功能词当成指代对象
            content_words = [t for t in tokens if len(t) >= 4]
            if content_words:
                return content_words[-1]
    return None
