"""Extraction domain models: the candidates the classifier will judge."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sitemapper.core.types import CandidateId

# Signals are simple JSON-scalar flags/measures produced by deterministic heuristics
# (see ``signals.py``). They are fed to the agent as hints; they never make the final call.
SignalValue = bool | int | str
SignalMap = dict[str, SignalValue]


class LinkCandidate(BaseModel):
    """A single outbound link discovered on a page."""

    id: CandidateId
    url: str  # absolute, normalized (fragment stripped, query sorted)
    normalized_url: str
    canonical_url: str | None = None
    anchor_text: str = ""
    section_role: str = ""  # nav | header | main | footer | aside | body
    signals: SignalMap = Field(default_factory=dict)


class SectionCandidate(BaseModel):
    """A landmark region of the page (nav, footer, ...)."""

    id: CandidateId
    role: str
    label: str = ""
    sample_links: list[str] = Field(default_factory=list)
    signals: SignalMap = Field(default_factory=dict)


class PageContent(BaseModel):
    """Everything extracted from one rendered page — the input to classification."""

    url: str
    title: str = ""
    headings: list[str] = Field(default_factory=list)
    canonical_url: str | None = None
    links: list[LinkCandidate] = Field(default_factory=list)
    sections: list[SectionCandidate] = Field(default_factory=list)
