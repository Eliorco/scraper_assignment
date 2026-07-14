from __future__ import annotations

import os

import pytest

from sitemapper.domains.classification.agent import SitemapClassifier
from sitemapper.domains.extraction.models import LinkCandidate, PageContent
from sitemapper.domains.extraction.signals import annotate


@pytest.mark.llm
@pytest.mark.asyncio
async def test_live_model_obvious_case_baseline() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for the opt-in LLM baseline")

    page = annotate(
        PageContent(
            url="https://example.com/",
            title="Example product",
            headings=["Build with Example"],
            links=[
                LinkCandidate(
                    id="l0",
                    url="https://example.com/docs",
                    normalized_url="https://example.com/docs",
                    anchor_text="Documentation",
                    section_role="nav",
                ),
                LinkCandidate(
                    id="l1",
                    url="https://example.com/login",
                    normalized_url="https://example.com/login",
                    anchor_text="Log in",
                    section_role="header",
                ),
                LinkCandidate(
                    id="l2",
                    url="https://example.com/privacy",
                    normalized_url="https://example.com/privacy",
                    anchor_text="Privacy policy",
                    section_role="footer",
                ),
                LinkCandidate(
                    id="l3",
                    url="https://example.com/blog?page=2",
                    normalized_url="https://example.com/blog?page=2",
                    anchor_text="Next",
                    section_role="main",
                ),
            ],
        )
    )
    expected = {"l0": True, "l1": False, "l2": False, "l3": False}
    classifier = SitemapClassifier(os.getenv("SCRAPER_LLM_MODEL", "openai:gpt-5"))

    verdicts = await classifier.classify(page)

    correct = sum(expected[item.target_id] is item.meaningful for item in verdicts)
    assert correct / len(expected) >= 0.75
    assert all(item.reason and 0.0 <= item.confidence <= 1.0 for item in verdicts)
