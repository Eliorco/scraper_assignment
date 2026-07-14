"""End-to-end deterministic pipeline test over static HTML."""

from __future__ import annotations

import pytest
from conftest import AllowAllRobots, FakeRenderer, SignalClassifier

from sitemapper.domains.classification.models import Classification
from sitemapper.domains.crawling.models import RenderedPage
from sitemapper.domains.extraction.models import (
    LinkCandidate,
    PageContent,
    SectionCandidate,
)
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


@pytest.mark.asyncio
async def test_pipeline_returns_partial_page_when_candidate_batch_is_oversized(caplog) -> None:
    root_url = "https://example.test/"
    oversized_page = PageContent(
        url=root_url,
        links=[
            LinkCandidate(
                id=f"l{index}",
                url=f"https://example.test/item/{index}",
                normalized_url=f"https://example.test/item/{index}",
                anchor_text=f"Item {index}",
            )
            for index in range(405)
        ],
        sections=[
            SectionCandidate(id="s0", role="nav", label="Primary"),
            SectionCandidate(id="s1", role="main", label="Content"),
        ],
    )

    def oversized_parser(_rendered: RenderedPage) -> PageContent:
        return oversized_page

    pipeline = CrawlPipeline(
        renderer=FakeRenderer({root_url: ""}),
        robots=AllowAllRobots(),
        classifier=SignalClassifier(),
        parser=oversized_parser,
        max_depth=0,
        max_candidates_per_page=400,
    )

    pages = await pipeline.run(root_url)

    assert len(pages) == 1
    page = pages[0]
    assert page.candidate_count == 407
    assert page.classified_candidate_count == 400
    assert page.dropped_candidate_count == 7
    assert page.classification_partial is True
    assert len(page.sections) == 2
    assert len(page.links) == 398
    assert "partial results" in caplog.text


@pytest.mark.asyncio
async def test_pipeline_keeps_partial_model_response_instead_of_failing(caplog) -> None:
    root_url = "https://example.test/"
    page_content = PageContent(
        url=root_url,
        links=[
            LinkCandidate(
                id=f"l{index}",
                url=f"https://example.test/item/{index}",
                normalized_url=f"https://example.test/item/{index}",
            )
            for index in range(10)
        ],
    )

    class PartialClassifier:
        async def classify(self, page: PageContent) -> list[Classification]:
            verdicts = await SignalClassifier().classify(page)
            return verdicts[:4]

    def page_parser(_rendered: RenderedPage) -> PageContent:
        return page_content

    pipeline = CrawlPipeline(
        renderer=FakeRenderer({root_url: ""}),
        robots=AllowAllRobots(),
        classifier=PartialClassifier(),
        parser=page_parser,
        max_depth=0,
    )

    pages = await pipeline.run(root_url)

    page = pages[0]
    assert page.candidate_count == 10
    assert page.classified_candidate_count == 4
    assert page.dropped_candidate_count == 6
    assert page.classification_partial is True
    assert len(page.links) == 4
    assert "incomplete batch" in caplog.text
