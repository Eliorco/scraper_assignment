"""Crawling ports (Protocols). Adapters live alongside; the pipeline depends only on these."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sitemapper.domains.crawling.models import RenderedPage


@runtime_checkable
class Renderer(Protocol):
    """Renders a URL to fully-loaded HTML. The only network-fetching component."""

    async def render(self, url: str) -> RenderedPage:
        """Fetch and render ``url``; may raise on navigation failure."""
        ...

    async def aclose(self) -> None:
        """Release browser resources."""
        ...


@runtime_checkable
class RobotsChecker(Protocol):
    """Decides whether the crawler is permitted to fetch a URL per robots.txt."""

    async def allowed(self, url: str) -> bool: ...
