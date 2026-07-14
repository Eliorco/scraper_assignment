"""Pure follow policy: agent verdict plus deterministic crawl constraints."""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass

from sitemapper.domains.classification.models import Classification
from sitemapper.domains.extraction.models import LinkCandidate
from sitemapper.domains.extraction.url_tools import canonical_key, in_scope


@dataclass(frozen=True, slots=True)
class FollowDecision:
    follow: bool
    reason: str
    canonical_key: str


def decide(
    link: LinkCandidate,
    classification: Classification,
    *,
    current_depth: int,
    max_depth: int,
    start_url: str,
    same_domain_only: bool,
    seen_keys: Set[str],
) -> FollowDecision:
    """Decide whether one classified link may enter the next BFS level.

    Robots policy and the global page budget are I/O/runtime concerns applied later by the
    orchestrator. This function does not mutate ``seen_keys``.
    """
    target_url = link.canonical_url or link.normalized_url
    key = canonical_key(target_url)

    if classification.target_id != link.id:
        return FollowDecision(False, "classification target does not match link", key)
    if not classification.meaningful:
        return FollowDecision(False, "agent marked link non-meaningful", key)
    if current_depth >= max_depth:
        return FollowDecision(False, "maximum crawl depth reached", key)
    if not in_scope(start_url, target_url, same_domain_only=same_domain_only):
        return FollowDecision(False, "URL is outside configured crawl scope", key)
    if key in seen_keys:
        return FollowDecision(False, "canonical URL already seen or queued", key)
    return FollowDecision(True, "meaningful, in scope, unseen, and within depth", key)
