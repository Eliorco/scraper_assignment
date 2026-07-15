from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic_ai.models.test import TestModel

from sitemapper.domains.classification.agent import SitemapClassifier
from sitemapper.domains.classification.models import Classification, PageClassification
from sitemapper.domains.classification.tools import (
    analyze_url_pattern,
    check_junk_signals,
    identify_section_role,
)
from sitemapper.domains.extraction.models import LinkCandidate, PageContent


class RecordingAgent:
    def __init__(self, *, fail_first_id: str | None = None) -> None:
        self.calls: list[list[str]] = []
        self.active = 0
        self.max_active = 0
        self.fail_first_id = fail_first_id

    async def run(self, prompt: str) -> SimpleNamespace:
        payload = json.loads(prompt.split("\n", 1)[1])
        ids = [candidate["id"] for candidate in payload["candidates"]]
        self.calls.append(ids)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            if ids and ids[0] == self.fail_first_id:
                raise RuntimeError("simulated batch failure")
            items = [
                Classification(
                    target_id=target_id,
                    meaningful=True,
                    importance="high",
                    reason="Test classification",
                    confidence=0.9,
                )
                for target_id in ids
            ]
            return SimpleNamespace(output=PageClassification(items=items))
        finally:
            self.active -= 1


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


@pytest.mark.asyncio
async def test_classifier_runs_bounded_chunks_concurrently_and_preserves_order() -> None:
    agent = RecordingAgent()
    classifier = SitemapClassifier(
        agent=agent,  # type: ignore[arg-type]
        batch_size=100,
        concurrency=3,
    )
    page = PageContent(
        url="https://example.com/",
        links=[
            LinkCandidate(
                id=f"l{index}",
                url=f"https://example.com/{index}",
                normalized_url=f"https://example.com/{index}",
            )
            for index in range(250)
        ],
    )

    verdicts = await classifier.classify(page)

    assert [len(call) for call in agent.calls] == [100, 100, 50]
    assert agent.max_active == 3
    assert [verdict.target_id for verdict in verdicts] == [f"l{index}" for index in range(250)]


@pytest.mark.asyncio
async def test_classifier_retains_successful_chunks_when_one_request_fails() -> None:
    agent = RecordingAgent(fail_first_id="l100")
    classifier = SitemapClassifier(
        agent=agent,  # type: ignore[arg-type]
        batch_size=100,
        concurrency=3,
    )
    page = PageContent(
        url="https://example.com/",
        links=[
            LinkCandidate(
                id=f"l{index}",
                url=f"https://example.com/{index}",
                normalized_url=f"https://example.com/{index}",
            )
            for index in range(250)
        ],
    )

    verdicts = await classifier.classify(page)

    assert len(verdicts) == 150
    assert verdicts[0].target_id == "l0"
    assert verdicts[99].target_id == "l99"
    assert verdicts[100].target_id == "l200"


def test_non_fetching_tools_only_analyze_supplied_values() -> None:
    url_result = analyze_url_pattern("https://example.com/login?page=2", "Sign in")
    role_result = identify_section_role("footer", "Company links")
    junk_result = check_junk_signals({"is_auth": True, "is_pagination": True})

    assert url_result["is_auth"] is True
    assert role_result["usually_boilerplate"] is True
    assert junk_result["junk_signal_count"] == 2
