"""End-to-end deterministic pipeline test over static HTML."""

from __future__ import annotations

import pytest
from conftest import AllowAllRobots, FakeRenderer, SignalClassifier

from sitemapper.domains.extraction.parser import parse
from sitemapper.pipeline.orchestrator import CrawlPipeline


@pytest.mark.asyncio
async def test_pipeline_respects_depth_and_drops_junk(fixture_pages: dict[str, str]) -> None:
    renderer = FakeRenderer(fixture_pages)
    pipeline = CrawlPipeline(
        renderer=renderer,
        robots=AllowAllRobots(),
        classifier=SignalClassifier(),
        parser=parse,
        max_depth=1,
        max_pages=10,
    )

    pages = await pipeline.run("https://example.test/")

    assert [page.url for page in pages] == [
        "https://example.test/",
        "https://example.test/docs",
        "https://example.test/guide",
    ]
    assert max(page.depth for page in pages) == 1
    root = pages[0]
    by_anchor = {link.anchor: link for link in root.links}
    assert by_anchor["Documentation"].followed is True
    assert by_anchor["Guide"].followed is True
    assert by_anchor["Log in"].meaningful is False
    assert by_anchor["Log in"].followed is False
    assert by_anchor["Next"].followed is False
    assert by_anchor["Privacy"].followed is False
