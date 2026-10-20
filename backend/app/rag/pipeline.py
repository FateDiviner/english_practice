"""RAG 管线入口。

唯一的对外接口是 run()。它必须做到一件事：**任何失败都不阻断对话**——
检索拿不到东西时照常走无上下文路径，而不是让用户看到一个报错气泡。
"""

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.config import get_settings
from app.rag.strategies import base as strategies  # noqa: F401  触发策略与阶段注册
from app.rag.types import RagContext, RagResult

logger = logging.getLogger(__name__)
settings = get_settings()


def run(
    query: str,
    db: Session,
    history: list[dict] | None = None,
    strategy_name: str | None = None,
) -> RagResult:
    """跑一次检索，永不抛出。

    返回的 context 为空字符串时，调用方就当没有 RAG 一样继续对话。
    """
    if not settings.rag_enabled or not query.strip():
        return RagResult(skipped="RAG 未启用或问题为空")

    ctx = RagContext(query=query, history=history or [], db=db)
    name = strategy_name or settings.rag_strategy
    started = time.perf_counter()

    try:
        strategy = strategies.resolve_strategy(name)
        strategy(ctx)
    except NotImplementedError as exc:
        # 配置指向了尚未实现的策略：降级到 naive，而不是让对话直接挂掉
        logger.warning("策略 %s 未实现，降级为 naive：%s", name, exc)
        name = "naive"
        try:
            strategies.resolve_strategy("naive")(ctx)
        except Exception:  # noqa: BLE001 - 兜底，绝不冒泡
            logger.exception("naive 策略也失败了")
            return RagResult(skipped="检索失败", lang=ctx.lang)
    except Exception:  # noqa: BLE001 - 检索失败不该影响对话
        logger.exception("RAG 管线异常，降级为无上下文")
        return RagResult(skipped="检索异常", lang=ctx.lang)

    elapsed = (time.perf_counter() - started) * 1000
    if elapsed > 1500:
        logger.warning("RAG 检索耗时 %.0fms，已接近首字延迟预算", elapsed)

    return RagResult(
        context=ctx.context,
        hits=ctx.final,
        skipped=ctx.skipped,
        trace=ctx.trace,
        lang=ctx.lang,
        embedding_calls=ctx.embedding_calls,
    )


def preview(query: str, db: Session, history: list[dict] | None = None) -> RagResult:
    """管理端调试用：跑一次检索并带上完整 trace。

    调阈值、加减阶段全靠它——没有 trace 就只能盲调。
    """
    return run(query, db, history=history)
