"""阶段与策略的注册表——「可插拔」的落地形式。

加一个优化 = 写一个 Stage + 装饰器注册 + 环境变量启用，不改管线代码。
增删阶段也不用改代码：RAG_STAGES_* 全部走配置。

为什么策略要单独一层：CRAG 是循环、Self-RAG 要插反思调用，它们改变的是
控制流而不是某个阶段的实现。只做阶段级插拔接不住 CRAG 的循环。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from app.rag.types import RagContext, StageKind

Stage = Callable[[RagContext], None]
Strategy = Callable[[RagContext], RagContext]

_STAGES: dict[tuple[StageKind, str], Stage] = {}
_STRATEGIES: dict[str, Strategy] = {}

F = TypeVar("F", Stage, Strategy)


class RagConfigError(ValueError):
    """配置里写了不存在的阶段或策略名。"""


def register_stage(kind: StageKind, name: str) -> Callable[[F], F]:
    """把一个阶段挂到 (环节, 名字) 上。"""

    def decorator(fn: F) -> F:
        key = (kind, name)
        if key in _STAGES:
            raise RagConfigError(f"阶段 {kind.value}/{name} 重复注册")
        _STAGES[key] = fn  # type: ignore[assignment]
        return fn

    return decorator


def register_strategy(name: str) -> Callable[[F], F]:
    """把一个编排策略挂到名字上。"""

    def decorator(fn: F) -> F:
        if name in _STRATEGIES:
            raise RagConfigError(f"策略 {name} 重复注册")
        _STRATEGIES[name] = fn  # type: ignore[assignment]
        return fn

    return decorator


def get_stage(kind: StageKind, name: str) -> Stage:
    try:
        return _STAGES[(kind, name)]
    except KeyError:
        known = sorted(n for (k, n) in _STAGES if k == kind)
        raise RagConfigError(
            f"未知的 {kind.value} 阶段 {name!r}，可用：{', '.join(known) or '（无）'}"
        ) from None


def get_strategy(name: str) -> Strategy:
    try:
        return _STRATEGIES[name]
    except KeyError:
        raise RagConfigError(
            f"未知的策略 {name!r}，可用：{', '.join(sorted(_STRATEGIES)) or '（无）'}"
        ) from None


def available_stages() -> dict[str, list[str]]:
    """按环节列出全部已注册阶段，供配置校验与调试页展示。"""
    grouped: dict[str, list[str]] = {}
    for (kind, name) in _STAGES:
        grouped.setdefault(kind.value, []).append(name)
    return {key: sorted(value) for key, value in grouped.items()}


def available_strategies() -> list[str]:
    return sorted(_STRATEGIES)


def resolve_stages(kind: StageKind, configured: str) -> list[tuple[str, Stage]]:
    """把逗号分隔的配置串解析成可执行阶段列表，未知名字直接报错。

    宁可启动时报错，也不要静默跳过——否则配错了只会表现为「RAG 没效果」，
    而这种问题极难从现象反查。
    """
    names = [part.strip() for part in configured.split(",") if part.strip()]
    return [(name, get_stage(kind, name)) for name in names]


def _reset_for_tests() -> None:
    """测试用：清空注册表，验证重复注册与未知阶段。"""
    _STAGES.clear()
    _STRATEGIES.clear()



__all__ = [
    "RagConfigError",
    "Stage",
    "Strategy",
    "available_stages",
    "available_strategies",
    "get_stage",
    "get_strategy",
    "register_stage",
    "register_strategy",
    "resolve_stages",
]
