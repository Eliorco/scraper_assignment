"""Playwright implementation of the rendering port."""

from __future__ import annotations

from playwright.async_api import Browser, Playwright, async_playwright

from sitemapper.domains.crawling.models import RenderedPage
from sitemapper.domains.crawling.rate_limiter import RateLimiter


class PlaywrightRenderer:
    """Lazily start one headless Chromium browser and render pages in fresh tabs."""

    def __init__(
        self,
        *,
        nav_timeout_ms: int = 30_000,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._nav_timeout_ms = nav_timeout_ms
        self._limiter = limiter or RateLimiter()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def _ensure_browser(self) -> Browser:
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def render(self, url: str) -> RenderedPage:
        """Navigate to a URL and return final URL, status, title, and rendered HTML."""

        async with self._limiter.limit(url):
            browser = await self._ensure_browser()
            page = await browser.new_page()
            try:
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self._nav_timeout_ms,
                )
                return RenderedPage(
                    url=page.url,
                    status=response.status if response else None,
                    html=await page.content(),
                    title=await page.title(),
                )
            finally:
                await page.close()

    async def aclose(self) -> None:
        """Release browser and Playwright resources."""

        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
