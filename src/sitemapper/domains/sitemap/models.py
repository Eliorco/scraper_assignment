"""Validated models for the generated sitemap document."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from sitemapper.core.types import CandidateId, Importance
from sitemapper.domains.extraction.models import SignalMap


class ClassifiedLink(BaseModel):
    id: CandidateId
    url: str
    anchor: str = ""
    section_role: str = ""
    signals: SignalMap = Field(default_factory=dict)
    meaningful: bool
    importance: Importance
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    followed: bool = False
    follow_reason: str = ""


class ClassifiedSection(BaseModel):
    id: CandidateId
    role: str
    label: str = ""
    sample_links: list[str] = Field(default_factory=list)
    signals: SignalMap = Field(default_factory=dict)
    meaningful: bool
    importance: Importance
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class PageNode(BaseModel):
    url: str
    depth: int = Field(ge=0)
    title: str = ""
    canonical_url: str | None = None
    headings: list[str] = Field(default_factory=list)
    candidate_count: int = Field(default=0, ge=0)
    classified_candidate_count: int = Field(default=0, ge=0)
    dropped_candidate_count: int = Field(default=0, ge=0)
    classification_partial: bool = False
    sections: list[ClassifiedSection] = Field(default_factory=list)
    links: list[ClassifiedLink] = Field(default_factory=list)


class SitemapConfig(BaseModel):
    max_depth: int = Field(default=2, ge=0)
    max_pages: int = Field(default=100, ge=1)
    max_candidates_per_page: int = Field(default=400, ge=1)
    same_domain_only: bool = True
    respect_robots: bool = True


class RunMeta(BaseModel):
    llm_model: str
    pages_visited: int = Field(ge=0)
    duration_s: float = Field(ge=0.0)
    run_id: str | None = None


class Sitemap(BaseModel):
    root_url: str
    generated_at: datetime
    config: SitemapConfig
    run: RunMeta
    pages: list[PageNode] = Field(default_factory=list)
