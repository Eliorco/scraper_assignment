"""Pydantic AI adapter for batched, structured sitemap classification."""

from __future__ import annotations

import json

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


class SitemapClassifier:
    """Classify every candidate on a page in one model call."""

    def __init__(
        self,
        model: Model | str = "openai:gpt-5",
        *,
        retries: int = 2,
        agent: Agent[object, PageClassification] | None = None,
    ) -> None:
        # Agent injection keeps wiring tests deterministic with Pydantic AI's TestModel.
        self._agent = agent or Agent[object, PageClassification](
            model,
            output_type=PageClassification,
            system_prompt=SYSTEM_PROMPT,
            retries=retries,
            tools=[analyze_url_pattern, identify_section_role, check_junk_signals],
        )

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

        result = await self._agent.run(_classification_prompt(page))
        items = result.output.items
        actual_ids = [item.target_id for item in items]
        if len(actual_ids) != len(set(actual_ids)):
            raise ValueError("Classifier returned duplicate candidate ids")
        unexpected = sorted(set(actual_ids) - set(expected_ids))
        if unexpected:
            raise ValueError(f"Classifier returned unexpected candidate ids: {unexpected}")
        by_id = {item.target_id: item for item in items}
        return [by_id[target_id] for target_id in expected_ids if target_id in by_id]


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
