"""Async concurrency and per-host delay limiter."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import monotonic
from urllib.parse import urlsplit


class RateLimiter:
    """Limit global concurrency and space requests to the same host."""

    def __init__(self, *, concurrency: int = 3, delay_s: float = 1.0) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if delay_s < 0:
            raise ValueError("delay_s must be non-negative")
        self._semaphore = asyncio.Semaphore(concurrency)
        self._delay_s = delay_s
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_request: dict[str, float] = {}

    @asynccontextmanager
    async def limit(self, url: str) -> AsyncIterator[None]:
        """Acquire capacity and wait for the host's configured delay."""

        host = (urlsplit(url).hostname or "").lower()
        async with self._semaphore, self._locks[host]:
            elapsed = monotonic() - self._last_request.get(host, 0.0)
            if elapsed < self._delay_s:
                await asyncio.sleep(self._delay_s - elapsed)
            try:
                yield
            finally:
                self._last_request[host] = monotonic()
