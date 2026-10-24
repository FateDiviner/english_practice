"""Small process-local TTL cache with per-key request coalescing."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CacheEntry(Generic[T]):
    value: T
    expires_at: datetime


class TTLProfileCache(Generic[T]):
    """Cache final reports so repeated admin views do not re-run four experts."""

    def __init__(self, ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")
        self._ttl = timedelta(seconds=ttl_seconds)
        self._entries: dict[str, CacheEntry[T]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()

    def _purge_expired(self, now: datetime) -> None:
        expired_keys = [
            key for key, entry in self._entries.items() if entry.expires_at <= now
        ]
        for key in expired_keys:
            self._entries.pop(key, None)
            lock = self._locks.get(key)
            if lock is None or not lock.locked():
                self._locks.pop(key, None)

    async def get_or_create(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
    ) -> tuple[T, bool, datetime]:
        now = datetime.now(UTC)
        self._purge_expired(now)
        entry = self._entries.get(key)
        if entry is not None and entry.expires_at > now:
            return entry.value, True, entry.expires_at
        if entry is not None:
            self._entries.pop(key, None)

        async with self._registry_lock:
            lock = self._locks.setdefault(key, asyncio.Lock())

        async with lock:
            now = datetime.now(UTC)
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                return entry.value, True, entry.expires_at

            value = await factory()
            expires_at = datetime.now(UTC) + self._ttl
            self._purge_expired(datetime.now(UTC))
            self._entries[key] = CacheEntry(value=value, expires_at=expires_at)
            return value, False, expires_at

    async def clear(self) -> None:
        self._entries.clear()

    @property
    def ttl_seconds(self) -> int:
        return int(self._ttl.total_seconds())