"""向量计算：走与对话同一个 OpenAI 兼容供应商。

不复用 chat 的 client——那边是流式生成，这边是批量定长向量，超时、重试与
降级策略完全不同。混在一起会把「生成超时」和「检索失败」搅成一个错误。

失败一律降级而不是抛出：检索拿不到向量时照常走 BM25 与图谱，绝不阻断对话。
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections import OrderedDict


from app.config import get_settings

settings = get_settings()

# 查询向量缓存：同一句话反复问不该每次都打 embedding 接口。
# 进程内 LRU，容量刻意压小——缓存的是查询，不是文档。
_CACHE: OrderedDict[str, list[float]] = OrderedDict()
_CACHE_MAX = 512
_CACHE_TTL_SECONDS = 600
_CACHE_STAMP: dict[str, float] = {}


class EmbeddingError(Exception):
    """embedding 调用失败。调用方应当降级，不要让它冒泡到用户。"""


def _cache_key(texts: list[str]) -> str:
    payload = json.dumps(texts, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> list[float] | None:
    if key not in _CACHE:
        return None
    if time.monotonic() - _CACHE_STAMP[key] > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        _CACHE_STAMP.pop(key, None)
        return None
    _CACHE.move_to_end(key)
    return _CACHE[key]


def _cache_put(key: str, vector: list[float]) -> None:
    _CACHE[key] = vector
    _CACHE_STAMP[key] = time.monotonic()
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        stale = next(iter(_CACHE))
        _CACHE.pop(stale, None)
        _CACHE_STAMP.pop(stale, None)


def clear_cache() -> None:
    """测试与文档重新索引后调用。"""
    _CACHE.clear()
    _CACHE_STAMP.clear()


def embed(texts: list[str], use_cache: bool = True) -> list[list[float]]:
    """批量取向量。空输入直接返回空，不打接口。"""
    if not texts:
        return []
    if not (settings.ai_base_url and settings.ai_api_key):
        raise EmbeddingError("未配置 AI 凭证，无法计算向量")

    key = _cache_key(texts)
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return [cached]

    url = settings.ai_base_url.rstrip("/") + "/embeddings"
    body = json.dumps(
        {"model": settings.embedding_model, "input": texts}, ensure_ascii=False
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request, timeout=settings.embedding_timeout_seconds
        ) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise EmbeddingError(f"向量服务调用失败：{exc}") from exc

    rows = sorted(payload.get("data", []), key=lambda row: row.get("index", 0))
    vectors = [row["embedding"] for row in rows]
    if len(vectors) != len(texts):
        raise EmbeddingError(f"向量数量不符：请求 {len(texts)} 条，返回 {len(vectors)} 条")

    # 单条查询才进缓存：批量入库的调用带的文本各不相同，缓存命中率是零
    if use_cache and len(texts) == 1:
        _cache_put(key, vectors[0])
    return vectors


def embed_query(text: str) -> list[float]:
    """单条查询向量，走缓存。"""
    return embed([text])[0]


def ping() -> bool:
    """探活，管理端用。失败返回 False 而不是抛。"""
    try:
        return bool(embed(["ping"], use_cache=False))
    except EmbeddingError:
        return False

