"""Async breadth-first orchestration across the domain ports."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable

from sitemapper.domains.classification.models import Classification
from sitemapper.domains.classification.ports import Classifier
from sitemapper.domains.crawling.models import CrawlTarget, RenderedPage
from sitemapper.domains.crawling.ports import Renderer, RobotsChecker
from sitemapper.domains.extraction.models import LinkCandidate, PageContent, SectionCandidate
from sitemapper.domains.extraction.signals import annotate
from sitemapper.domains.extraction.url_tools import canonical_key, normalize_url
from sitemapper.domains.sitemap.models import (
    ClassifiedLink,
    ClassifiedSection,
    PageNode,
)
from sitemapper.pipeline.follow_policy import decide

Parser = Callable[[RenderedPage], PageContent]
logger = logging.getLogger(__name__)


class CrawlPipeline:
    """Render, extract, classify, and selectively queue pages in BFS order."""

    def __init__(
        self,
        *,
        renderer: Renderer,
        robots: RobotsChecker,
        classifier: Classifier,
        parser: Parser,
        max_depth: int = 2,
        max_pages: int = 100,
        max_candidates_per_page: int = 400,
        same_domain_only: bool = True,
        respect_robots: bool = True,
    ) -> None:
        if max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        if max_candidates_per_page < 1:
            raise ValueError("max_candidates_per_page must be at least 1")
        self._renderer = renderer
        self._robots = robots
        self._classifier = classifier
        self._parser = parser
        self._max_depth = max_depth
        self._max_pages = max_pages
        self._max_candidates_per_page = max_candidates_per_page
        self._same_domain_only = same_domain_only
        self._respect_robots = respect_robots

    async def run(self, start_url: str) -> list[PageNode]:
        normalized_start = normalize_url(start_url, start_url)
        if normalized_start is None:
            raise ValueError(f"Invalid HTTP(S) start URL: {start_url!r}")

        queue = deque([CrawlTarget(url=normalized_start, depth=0)])
        seen_keys = {canonical_key(normalized_start)}
        pages: list[PageNode] = []

        while queue and len(pages) < self._max_pages:
            target = queue.popleft()
            if self._respect_robots and not await self._robots.allowed(target.url):
                continue

            rendered = await self._renderer.render(target.url)
            page = annotate(self._parser(rendered))
            candidate_count = len(page.links) + len(page.sections)
            classification_page = _limit_candidates(page, self._max_candidates_per_page)
            batch_candidate_count = len(classification_page.links) + len(
                classification_page.sections
            )
            limit_dropped_count = candidate_count - batch_candidate_count
            if limit_dropped_count:
                logger.warning(
                    "Oversized candidate batch truncated; sitemap page contains partial results "
                    "(total=%d, limit=%d, dropped=%d)",
                    candidate_count,
                    self._max_candidates_per_page,
                    limit_dropped_count,
                    extra={"stage": "classify", "url": page.url},
                )

            classifications = await self._classifier.classify(classification_page)
            verdicts = _index_verdicts(classification_page, classifications)
            classified_candidate_count = len(verdicts)
            response_dropped_count = batch_candidate_count - classified_candidate_count
            if response_dropped_count:
                logger.warning(
                    "Classifier returned an incomplete batch; missing candidates were dropped "
                    "and the sitemap page contains partial results "
                    "(requested=%d, returned=%d, dropped=%d)",
                    batch_candidate_count,
                    classified_candidate_count,
                    response_dropped_count,
                    extra={"stage": "classify", "url": page.url},
                )
            dropped_candidate_count = candidate_count - classified_candidate_count

            classified_sections = [
                _classified_section(section, verdicts[section.id])
                for section in classification_page.sections
                if section.id in verdicts
            ]
            classified_links: list[ClassifiedLink] = []

            for link in classification_page.links:
                if link.id not in verdicts:
                    continue
                verdict = verdicts[link.id]
                decision = decide(
                    link,
                    verdict,
                    current_depth=target.depth,
                    max_depth=self._max_depth,
                    start_url=normalized_start,
                    same_domain_only=self._same_domain_only,
                    seen_keys=seen_keys,
                )
                followed = decision.follow
                follow_reason = decision.reason
                target_url = link.canonical_url or link.normalized_url

                if followed and len(seen_keys) >= self._max_pages:
                    followed = False
                    follow_reason = "global page budget reached"
                elif (
                    followed and self._respect_robots and not await self._robots.allowed(target_url)
                ):
                    followed = False
                    follow_reason = "disallowed by robots.txt"

                if followed:
                    seen_keys.add(decision.canonical_key)
                    queue.append(CrawlTarget(url=target_url, depth=target.depth + 1))

                classified_links.append(
                    _classified_link(link, verdict, followed=followed, follow_reason=follow_reason)
                )

            pages.append(
                PageNode(
                    url=page.url,
                    depth=target.depth,
                    title=page.title,
                    canonical_url=page.canonical_url,
                    headings=page.headings,
                    candidate_count=candidate_count,
                    classified_candidate_count=classified_candidate_count,
                    dropped_candidate_count=dropped_candidate_count,
                    classification_partial=bool(dropped_candidate_count),
                    sections=classified_sections,
                    links=classified_links,
                )
            )

        return pages


def _limit_candidates(page: PageContent, limit: int) -> PageContent:
    """Return a classification view capped to ``limit`` candidates.

    Landmark sections are retained first because they describe site structure; remaining
    capacity is filled by links in deterministic extraction order.
    """
    sections = page.sections[:limit]
    remaining = limit - len(sections)
    links = page.links[:remaining]
    return page.model_copy(update={"links": links, "sections": sections})


def _index_verdicts(
    page: PageContent, classifications: list[Classification]
) -> dict[str, Classification]:
    expected = {candidate.id for candidate in page.links} | {
        candidate.id for candidate in page.sections
    }
    indexed: dict[str, Classification] = {}
    for verdict in classifications:
        if verdict.target_id in indexed:
            raise ValueError(f"Duplicate classification for {verdict.target_id!r}")
        indexed[verdict.target_id] = verdict
    unexpected = sorted(set(indexed) - expected)
    if unexpected:
        raise ValueError(f"Classifier returned unexpected page candidates: {unexpected}")
    return indexed


def _classified_link(
    link: LinkCandidate,
    verdict: Classification,
    *,
    followed: bool,
    follow_reason: str,
) -> ClassifiedLink:
    return ClassifiedLink(
        id=link.id,
        url=link.normalized_url,
        anchor=link.anchor_text,
        section_role=link.section_role,
        signals=link.signals,
        meaningful=verdict.meaningful,
        importance=verdict.importance,
        reason=verdict.reason,
        confidence=verdict.confidence,
        followed=followed,
        follow_reason=follow_reason,
    )


def _classified_section(section: SectionCandidate, verdict: Classification) -> ClassifiedSection:
    return ClassifiedSection(
        id=section.id,
        role=section.role,
        label=section.label,
        sample_links=section.sample_links,
        signals=section.signals,
        meaningful=verdict.meaningful,
        importance=verdict.importance,
        reason=verdict.reason,
        confidence=verdict.confidence,
    )
