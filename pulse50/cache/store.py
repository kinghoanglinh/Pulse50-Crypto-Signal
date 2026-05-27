"""Thread-safe TTL cache for provider data."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    created_at: float
    ttl_seconds: float


class TTLCache:
    """Small in-memory cache for single-process Swarms tool execution."""

    def __init__(self, clock=time.time):
        self._clock = clock
        self._entries: dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> tuple[Any | None, float | None]:
        """Return cached value and age seconds, or `(None, None)` when absent."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None, None

            age_seconds = max(0.0, self._clock() - entry.created_at)
            if age_seconds > entry.ttl_seconds:
                return None, age_seconds

            return entry.value, age_seconds

    def get_stale(self, key: str) -> tuple[Any | None, float | None]:
        """Return cached value even after TTL expiry, for provider-failure fallback."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None, None
            age_seconds = max(0.0, self._clock() - entry.created_at)
            return entry.value, age_seconds

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """Store a value under `key` for `ttl_seconds`."""
        if ttl_seconds <= 0:
            return
        with self._lock:
            self._entries[key] = CacheEntry(
                value=value,
                created_at=self._clock(),
                ttl_seconds=ttl_seconds,
            )

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


CACHE_TTLS = {
    "universe": 300,
    "ohlcv": 60,
    "order_book": 15,
    "ticker": 30,
    "provider_capability": 900,
    "asset_market_data": 15,
}

default_cache = TTLCache()
