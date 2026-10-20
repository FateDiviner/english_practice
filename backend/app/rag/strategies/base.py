"""编排策略：决定调用哪些阶段、是否循环、是否插反思。

分这一层是因为 CRAG 与 Self-RAG 改的是控制流而不是某个阶段的实现：
CRAG 要在召回后打分、低分改写重检索（循环），Self-RAG 要在生成后回头判断
有没有被证据支撑（反思）。只做阶段级插拔接不住这些。
"""

from __future__ import annotations

import time

from app.config import get_settings
from app.rag.registry import get_strategy, register_strategy, resolve_stages
from app.rag.stages import post, pre, ranking, retrieve  # noqa: F401  触发阶段注册
from app.rag.types import RagContext, StageKind, StageTrace

settings = get_settings()


def run_stages(ctx: RagContext, kind: StageKind, configured: str) -> None:
    """按配置串依次执行某个环节的阶段，并记录 trace。"""
    for name, stage in resolve_stages(kind, configured):
        before = len(ctx.candidates)
        before_notes = len(ctx.notes)
        started = time.perf_counter()
        stage(ctx)
        duration = (time.perf_counter() - started) * 1000
        ctx.trace.append(
            StageTrace(
                stage=name,
                kind=kind.value,
                duration_ms=round(duration, 2),
                input_count=before,
                output_count=len(ctx.candidates),
                note="; ".join(ctx.notes[before_notes:]),
            )
        )


@register_strategy("naive")
def naive(ctx: RagContext) -> RagContext:
    """一条直线走完，不循环、不反思。

    这是默认路径：全程只有 embedding 调用，零额外 LLM 调用，
    用来守住 2 秒首字延迟预算。
    """
    run_stages(ctx, StageKind.PRE, settings.rag_stages_pre)
    if ctx.skipped:
        return ctx

    run_stages(ctx, StageKind.RETRIEVE, settings.rag_stages_retrieve)
    if not ctx.candidates:
        ctx.skipped = "三路召回均无结果"
        return ctx

    run_stages(ctx, StageKind.FUSE, settings.rag_stages_fuse)
    run_stages(ctx, StageKind.RERANK, settings.rag_stages_rerank)
    run_stages(ctx, StageKind.POST, settings.rag_stages_post)
    return ctx


@register_strategy("corrective")
def corrective(ctx: RagContext) -> RagContext:
    """CRAG：召回后逐条打分，整批不相关就改写查询重检索。

    只采纳 CRAG 的「评分 + 重检索」，**不做 web search 兜底**——英语教学
    场景引入外部网页内容不可控、有合规风险，且与「本地零运维」冲突。

    默认关闭：启用后每轮多一次评分（轻量启发式，不调模型），
    若同时打开 rag_llm_rerank 才会有额外的 LLM 调用。
    """
    run_stages(ctx, StageKind.PRE, settings.rag_stages_pre)
    if ctx.skipped:
        return ctx

    tried_queries: list[str] = []
    max_rounds = max(1, settings.rag_crag_max_rounds)
    for round_index in range(max_rounds):
        ctx.round = round_index
        ctx.candidates = []
        run_stages(ctx, StageKind.RETRIEVE, settings.rag_stages_retrieve)
        if not ctx.candidates:
            ctx.skipped = "三路召回均无结果"
            return ctx
        run_stages(ctx, StageKind.FUSE, settings.rag_stages_fuse)
        run_stages(ctx, StageKind.RERANK, settings.rag_stages_rerank)

        verdict = _grade(ctx)
        ctx.trace.append(
            StageTrace(
                stage="crag_grade",
                kind="post",
                duration_ms=0.0,
                input_count=len(ctx.candidates),
                output_count=len(ctx.candidates),
                note=f"第 {round_index + 1} 轮判定: {verdict}",
            )
        )
        if verdict != "incorrect":
            break

        # 整批不相关：放宽查询再试。放宽只做确定性过滤，不调模型
        tried_queries.append(ctx.retrieval_query or ctx.normalized or ctx.query)
        broadened = _broaden(ctx)
        if broadened in tried_queries or not broadened:
            ctx.skipped = "放宽查询后仍无相关内容"
            return ctx
        ctx.retrieval_query = broadened
    else:
        ctx.skipped = "多轮重检索后仍无相关内容"
        return ctx

    run_stages(ctx, StageKind.POST, settings.rag_stages_post)
    return ctx


def _grade(ctx: RagContext) -> str:
    """给整批候选定性：correct / ambiguous / incorrect。

    轻量启发式，不调模型——真正的 LLM 重排有独立开关（rag_llm_rerank）。
    """
    if not ctx.candidates:
        return "incorrect"
    best = max(hit.score for hit in ctx.candidates)
    if best >= settings.rag_score_threshold * 2:
        return "correct"
    if best >= settings.rag_score_threshold:
        return "ambiguous"
    return "incorrect"


def _broaden(ctx: RagContext) -> str:
    """把查询放宽：去掉疑问词与助词，只留实义词。

    学习者的问题常带「怎么」「什么」「帮我」这类噪音，
    去掉之后 BM25 的命中率会明显上升。
    """
    drop = {
        "怎么", "什么", "帮我", "请问", "一下", "这个", "那个", "的", "吗", "呢",
        "how", "what", "the", "a", "an",
    }
    terms = [keyword for keyword in ctx.keywords if keyword not in drop]
    if not terms:
        return ""
    return " ".join(terms)


@register_strategy("self_rag")
def self_rag(ctx: RagContext) -> RagContext:
    """Self-RAG 占位。

    真正的 Self-RAG 要在生成之后回头判断「这段回答有没有被检索内容支撑」，
    那需要 chat 管线暴露一个 post-generation 钩子，并在流式输出中途插入
    反思轮。本轮只留接口与注册项，不实现——它防的失效模式已经被
    「阈值门控 + 引用 + 拒答」用零延迟覆盖了大半。
    """
    raise NotImplementedError(
        "self_rag 策略尚未实现，请改用 RAG_STRATEGY=naive 或 corrective"
    )


def resolve_strategy(name: str):
    """按配置取策略，未知名字给出可用列表。"""
    return get_strategy(name)
