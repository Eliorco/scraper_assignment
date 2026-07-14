from __future__ import annotations

from datetime import UTC, datetime

from sitemapper.domains.sitemap.builder import build
from sitemapper.domains.sitemap.models import PageNode, SitemapConfig


def test_build_populates_run_metadata_and_pages() -> None:
    generated_at = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
    pages = [PageNode(url="https://example.com/", depth=0, title="Home")]

    sitemap = build(
        root_url="https://example.com/",
        pages=pages,
        config=SitemapConfig(max_depth=2, max_pages=20),
        llm_model="test:model",
        duration_s=1.25,
        run_id="run-1",
        generated_at=generated_at,
    )

    assert sitemap.generated_at == generated_at
    assert sitemap.pages == pages
    assert sitemap.run.pages_visited == 1
    assert sitemap.run.llm_model == "test:model"
    assert sitemap.config.max_pages == 20
