"""Cached robots.txt policy adapter."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser


class RobotsTxtChecker:
    """Fetch and cache one robots policy per scheme/host."""

    def __init__(self, *, user_agent: str = "sitemapper", timeout_s: float = 10.0) -> None:
        self._user_agent = user_agent
        self._timeout_s = timeout_s
        self._cache: dict[str, RobotFileParser | None] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def allowed(self, url: str) -> bool:
        """Return robots permission, allowing access when no policy can be retrieved."""

        parts = urlsplit(url)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        if origin not in self._cache:
            async with self._locks[origin]:
                if origin not in self._cache:
                    self._cache[origin] = await asyncio.to_thread(self._load, origin)
        policy = self._cache[origin]
        return True if policy is None else policy.can_fetch(self._user_agent, url)

    def _load(self, origin: str) -> RobotFileParser | None:
        robots_url = f"{origin}/robots.txt"
        request = Request(robots_url, headers={"User-Agent": self._user_agent})
        try:
            with urlopen(request, timeout=self._timeout_s) as response:  # noqa: S310
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if exc.code in {401, 403, 429} or exc.code >= 500:
                parser = RobotFileParser(robots_url)
                parser.parse(["User-agent: *", "Disallow: /"])
                return parser
            return None
        except (URLError, TimeoutError, OSError):
            return None
        parser = RobotFileParser(robots_url)
        parser.parse(body.splitlines())
        return parser
