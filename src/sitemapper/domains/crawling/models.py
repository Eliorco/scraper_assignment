"""Crawling domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CrawlTarget(BaseModel):
    """A URL queued to be rendered, tagged with its BFS depth from the start URL."""

    url: str
    depth: int = Field(ge=0)


class RenderedPage(BaseModel):
    """The result of rendering a single page with a headless browser.

    ``url`` is the *final* URL after any client/server redirects — extraction resolves
    relative links against it, not against the requested URL.
    """

    url: str
    status: int | None = None
    html: str = ""
    title: str = ""
