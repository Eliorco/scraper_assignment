from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from sitemapper.domains.classification.agent import SitemapClassifier
from sitemapper.domains.classification.tools import (
    analyze_url_pattern,
    check_junk_signals,
    identify_section_role,
)
from sitemapper.domains.extraction.models import LinkCandidate, PageContent


@pytest.mark.asyncio
async def test_classifier_returns_schema_valid_ordered_output_without_network() -> None:
    test_model = TestModel(
        custom_output_args={
            "items": [
                {
                    "target_id": "l0",
                    "meaningful": True,
                    "importance": "high",
                    "reason": "Primary documentation destination",
                    "confidence": 0.97,
                }
            ]
        }
    )
    classifier = SitemapClassifier(model=test_model)
    page = PageContent(
        url="https://example.com/",
        title="Example",
        links=[
            LinkCandidate(
                id="l0",
                url="https://example.com/docs",
                normalized_url="https://example.com/docs",
                anchor_text="Docs",
                section_role="nav",
            )
        ],
    )

    verdicts = await classifier.classify(page)

    assert [verdict.target_id for verdict in verdicts] == ["l0"]
    assert verdicts[0].meaningful is True
    assert verdicts[0].confidence == pytest.approx(0.97)
    assert {tool.name for tool in test_model.last_model_request_parameters.function_tools} == {
        "analyze_url_pattern",
        "identify_section_role",
        "check_junk_signals",
    }


@pytest.mark.asyncio
async def test_classifier_accepts_incomplete_structured_output_as_partial() -> None:
    test_model = TestModel(
        custom_output_args={
            "items": [
                {
                    "target_id": "l1",
                    "meaningful": False,
                    "importance": "low",
                    "reason": "Utility destination",
                    "confidence": 0.9,
                }
            ]
        }
    )
    classifier = SitemapClassifier(model=test_model)
    page = PageContent(
        url="https://example.com/",
        links=[
            LinkCandidate(
                id=f"l{index}",
                url=f"https://example.com/{index}",
                normalized_url=f"https://example.com/{index}",
            )
            for index in range(2)
        ],
    )

    verdicts = await classifier.classify(page)

    assert [verdict.target_id for verdict in verdicts] == ["l1"]


def test_non_fetching_tools_only_analyze_supplied_values() -> None:
    url_result = analyze_url_pattern("https://example.com/login?page=2", "Sign in")
    role_result = identify_section_role("footer", "Company links")
    junk_result = check_junk_signals({"is_auth": True, "is_pagination": True})

    assert url_result["is_auth"] is True
    assert role_result["usually_boilerplate"] is True
    assert junk_result["junk_signal_count"] == 2
