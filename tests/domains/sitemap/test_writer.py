from __future__ import annotations

import json
from datetime import UTC, datetime

from sitemapper.core.types import Importance
from sitemapper.domains.sitemap.models import (
    ClassifiedLink,
    PageNode,
    RunMeta,
    Sitemap,
    SitemapConfig,
)
from sitemapper.domains.sitemap.writer import summary, write


def _sitemap() -> Sitemap:
    return Sitemap(
        root_url="https://docs.example.com/guide/",
        generated_at=datetime(2026, 7, 14, 13, 15, tzinfo=UTC),
        config=SitemapConfig(),
        run=RunMeta(llm_model="test:model", pages_visited=1, duration_s=0.5),
        pages=[
            PageNode(
                url="https://docs.example.com/guide/",
                depth=0,
                links=[
                    ClassifiedLink(
                        id="l0",
                        url="https://docs.example.com/api",
                        anchor="API",
                        meaningful=True,
                        importance=Importance.HIGH,
                        reason="core documentation",
                        confidence=0.98,
                    )
                ],
            )
        ],
    )


def test_write_uses_url_slug_and_utc_timestamp(tmp_path) -> None:
    sitemap = _sitemap()

    path = write(sitemap, tmp_path)

    assert path.name == "docs-example-com_guide_20260714T131500Z.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["root_url"] == sitemap.root_url
    assert payload["pages"][0]["links"][0]["reason"] == "core documentation"


def test_summary_reports_counts_and_output_path(tmp_path) -> None:
    sitemap = _sitemap()
    path = tmp_path / "result.json"

    text = summary(sitemap, path)

    assert "Pages visited: 1" in text
    assert "1 meaningful, 0 non-meaningful" in text
    assert str(path) in text
