"""Shared value objects used across every domain.

Kept dependency-free (stdlib only) so any domain can import it without cycles.
"""

from __future__ import annotations

from enum import StrEnum

# A candidate's stable, per-page identifier (e.g. "l0" for the first link, "s2" for
# the third section). Assigned deterministically by the parser and echoed back by the
# classification agent so verdicts can be matched to candidates.
CandidateId = str


class Importance(StrEnum):
    """How important a meaningful element is to understanding the site's structure."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ElementKind(StrEnum):
    """Whether a classification target is a link or a page section."""

    LINK = "link"
    SECTION = "section"
