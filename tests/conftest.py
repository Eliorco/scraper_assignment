"""Shared deterministic test doubles."""

from __future__ import annotations

from pathlib import Path

import pytest

from sitemapper.core.types import Importance
from sitemapper.domains.classification.models import Classification
from sitemapper.domains.crawling.models import RenderedPage
from sitemapper.domains.extraction.models import PageContent


class FakeRenderer:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.rendered_urls: list[str] = []
        self.closed = False

    async def render(self, url: str) -> RenderedPage:
        self.rendered_urls.append(url)
        return RenderedPage(url=url, status=200, html=self.pages[url])

    async def aclose(self) -> None:
        self.closed = True


class AllowAllRobots:
    async def allowed(self, url: str) -> bool:
        return True


class SignalClassifier:
    """Classify fixture junk as low-value and ordinary content as meaningful."""

    async def classify(self, page: PageContent) -> list[Classification]:
        verdicts: list[Classification] = []
        for candidate in [*page.links, *page.sections]:
            junk = any(
                candidate.signals.get(key, False)
                for key in (
                    "in_footer",
                    "is_footer",
                    "is_auth",
                    "is_language_switcher",
                    "is_pagination",
                    "is_permalink",
                    "is_legal_boilerplate",
                )
            )
            verdicts.append(
                Classification(
                    target_id=candidate.id,
                    meaningful=not junk,
                    importance=Importance.LOW if junk else Importance.HIGH,
                    reason="fixture junk signal" if junk else "fixture meaningful content",
                    confidence=0.99,
                )
            )
        return verdicts


@pytest.fixture
def fixture_pages() -> dict[str, str]:
    fixture_dir = Path(__file__).parent / "fixtures" / "site"
    return {
        "https://example.test/": (fixture_dir / "index.html").read_text(encoding="utf-8"),
        "https://example.test/docs": (fixture_dir / "docs.html").read_text(encoding="utf-8"),
        "https://example.test/guide": (fixture_dir / "guide.html").read_text(encoding="utf-8"),
    }
