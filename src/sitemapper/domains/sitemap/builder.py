"""Assemble validated sitemap documents from collected page nodes."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sitemapper.domains.sitemap.models import (
    PageNode,
    RunMeta,
    Sitemap,
    SitemapConfig,
)


def build(
    *,
    root_url: str,
    pages: Sequence[PageNode],
    config: SitemapConfig,
    llm_model: str,
    duration_s: float,
    run_id: str | None = None,
    generated_at: datetime | None = None,
) -> Sitemap:
    """Build a complete, validated sitemap with reproducibility metadata."""

    page_list = list(pages)
    return Sitemap(
        root_url=root_url,
        generated_at=generated_at or datetime.now(UTC),
        config=config,
        run=RunMeta(
            llm_model=llm_model,
            pages_visited=len(page_list),
            duration_s=duration_s,
            run_id=run_id,
        ),
        pages=page_list,
    )
