"""Pydantic AI adapter for batched, structured sitemap classification."""

from __future__ import annotations

import asyncio
import json
import logging

from pydantic_ai import Agent
from pydantic_ai.models import Model

from sitemapper.domains.classification.models import Classification, PageClassification
from sitemapper.domains.classification.prompts import SYSTEM_PROMPT
from sitemapper.domains.classification.tools import (
    analyze_url_pattern,
    check_junk_signals,
    identify_section_role,
)
from sitemapper.domains.extraction.models import PageContent

logger = logging.getLogger(__name__)


class SitemapClassifier:
    """Classify page candidates in bounded, concurrent model requests."""

    def __init__(
        self,
        model: Model | str = "openai:gpt-5",
        *,
        retries: int = 2,
        batch_size: int = 100,
        concurrency: int = 4,
        agent: Agent[object, PageClassification] | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        # Agent injection keeps wiring tests deterministic with Pydantic AI's TestModel.
        self._agent = agent or Agent[object, PageClassification](
            model,
            output_type=PageClassification,
            system_prompt=SYSTEM_PROMPT,
            retries=retries,
            tools=[analyze_url_pattern, identify_section_role, check_junk_signals],
        )
        self._batch_size = batch_size
        self._concurrency = concurrency

    @property
    def agent(self) -> Agent[object, PageClassification]:
        """Expose the underlying agent for Pydantic AI test-model overrides."""
        return self._agent

    async def classify(self, page: PageContent) -> list[Classification]:
        expected_ids = [link.id for link in page.links] + [section.id for section in page.sections]
        if not expected_ids:
            return []
        if len(expected_ids) != len(set(expected_ids)):
            raise ValueError("Candidate ids must be unique within a page")

        chunks = _chunk_page(page, self._batch_size)
        semaphore = asyncio.Semaphore(self._concurrency)

        async def classify_chunk(
            index: int, chunk: PageContent
        ) -> tuple[list[Classification], Exception | None]:
            async with semaphore:
                candidate_count = len(chunk.links) + len(chunk.sections)
                logger.info(
                    "Classifying candidate batch %d/%d (%d candidates)",
                    index + 1,
                    len(chunks),
                    candidate_count,
                    extra={"stage": "classify", "url": page.url},
                )
                try:
                    result = await self._agent.run(_classification_prompt(chunk))
                    return _validated_items(chunk, result.output.items), None
                except Exception as exc:
                    return [], exc

        results = await asyncio.gather(
            *(classify_chunk(index, chunk) for index, chunk in enumerate(chunks))
        )
        items = [item for chunk_items, _error in results for item in chunk_items]
        errors = [error for _chunk_items, error in results if error is not None]
        if errors and not items:
            raise errors[0]
        if errors:
            logger.warning(
                "%d/%d classification batches failed; successful batches are retained as "
                "partial results",
                len(errors),
                len(chunks),
                extra={"stage": "classify", "url": page.url},
            )

        by_id = {item.target_id: item for item in items}
        return [by_id[target_id] for target_id in expected_ids if target_id in by_id]


def _validated_items(page: PageContent, items: list[Classification]) -> list[Classification]:
    expected_ids = [link.id for link in page.links] + [section.id for section in page.sections]
    actual_ids = [item.target_id for item in items]
    if len(actual_ids) != len(set(actual_ids)):
        raise ValueError("Classifier returned duplicate candidate ids")
    unexpected = sorted(set(actual_ids) - set(expected_ids))
    if unexpected:
        raise ValueError(f"Classifier returned unexpected candidate ids: {unexpected}")
    by_id = {item.target_id: item for item in items}
    return [by_id[target_id] for target_id in expected_ids if target_id in by_id]


def _chunk_page(page: PageContent, batch_size: int) -> list[PageContent]:
    """Split links followed by sections into deterministic classification views."""
    chunks: list[PageContent] = []
    link_count = len(page.links)
    total = link_count + len(page.sections)
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        links = page.links[start : min(end, link_count)] if start < link_count else []
        section_start = max(0, start - link_count)
        section_end = max(0, end - link_count)
        sections = page.sections[section_start:section_end]
        chunks.append(page.model_copy(update={"links": links, "sections": sections}))
    return chunks


def _classification_prompt(page: PageContent) -> str:
    payload = {
        "page": {
            "url": page.url,
            "title": page.title,
            "headings": page.headings,
            "canonical_url": page.canonical_url,
        },
        "candidates": [
            {
                "id": link.id,
                "kind": "link",
                "url": link.normalized_url,
                "anchor_text": link.anchor_text,
                "section_role": link.section_role,
                "signals": link.signals,
            }
            for link in page.links
        ]
        + [
            {
                "id": section.id,
                "kind": "section",
                "role": section.role,
                "label": section.label,
                "sample_links": section.sample_links,
                "signals": section.signals,
            }
            for section in page.sections
        ],
    }
    return (
        "Classify every candidate in this JSON payload. Return each id exactly once.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
