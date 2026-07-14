from __future__ import annotations

from sitemapper.core.types import Importance
from sitemapper.domains.classification.models import Classification
from sitemapper.domains.extraction.models import LinkCandidate
from sitemapper.pipeline.follow_policy import FollowDecision, decide


def _link(url: str = "https://example.com/docs") -> LinkCandidate:
    return LinkCandidate(id="l0", url=url, normalized_url=url, anchor_text="Docs")


def _verdict(*, meaningful: bool = True, target_id: str = "l0") -> Classification:
    return Classification(
        target_id=target_id,
        meaningful=meaningful,
        importance=Importance.HIGH,
        reason="Core documentation",
        confidence=0.95,
    )


def _decide(
    link: LinkCandidate | None = None,
    verdict: Classification | None = None,
    *,
    current_depth: int = 0,
    max_depth: int = 2,
    seen_keys: set[str] | None = None,
) -> FollowDecision:
    return decide(
        link or _link(),
        verdict or _verdict(),
        current_depth=current_depth,
        max_depth=max_depth,
        start_url="https://example.com/",
        same_domain_only=True,
        seen_keys=seen_keys or set(),
    )


def test_follows_meaningful_unseen_in_scope_link() -> None:
    assert _decide().follow is True


def test_rejects_agent_non_meaningful_link() -> None:
    decision = _decide(verdict=_verdict(meaningful=False))
    assert decision.follow is False
    assert "non-meaningful" in decision.reason


def test_rejects_at_depth_cap() -> None:
    assert _decide(current_depth=2, max_depth=2).follow is False


def test_rejects_out_of_scope_link() -> None:
    assert _decide(link=_link("https://other.example.net/docs")).follow is False


def test_rejects_seen_canonical_url() -> None:
    link = _link("https://www.example.com/docs/")
    assert _decide(link=link, seen_keys={"https://example.com/docs"}).follow is False


def test_rejects_mismatched_classification() -> None:
    assert _decide(verdict=_verdict(target_id="l9")).follow is False
