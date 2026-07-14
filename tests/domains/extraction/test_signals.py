from __future__ import annotations

from sitemapper.domains.extraction.models import (
    LinkCandidate,
    PageContent,
    SectionCandidate,
)
from sitemapper.domains.extraction.signals import (
    annotate,
    is_auth,
    is_endless_list,
    is_language_switcher,
    is_pagination,
    is_permalink,
    link_signals,
)


def test_detects_auth_from_url_or_anchor() -> None:
    assert is_auth("https://example.com/login")
    assert is_auth("https://example.com/", "Sign in")
    assert not is_auth("https://example.com/docs", "Documentation")


def test_detects_language_switchers_without_matching_arbitrary_words() -> None:
    assert is_language_switcher("https://example.com/fr/docs")
    assert is_language_switcher("https://example.com/docs?locale=fr")
    assert is_language_switcher("https://example.com/docs", "Deutsch")
    assert not is_language_switcher("https://example.com/encryption")


def test_detects_pagination_patterns() -> None:
    assert is_pagination("https://example.com/blog?page=2")
    assert is_pagination("https://example.com/blog/page/3")
    assert is_pagination("https://example.com/blog", "Next")
    assert not is_pagination("https://example.com/docs", "Getting started")


def test_detects_archive_and_dated_permalink_patterns() -> None:
    assert is_endless_list("https://example.com/tags/python")
    assert is_endless_list("https://example.com/2026/07/")
    assert is_permalink("https://example.com/2026/07/14/story")
    assert not is_permalink("https://example.com/docs/install")


def test_link_signals_include_location_and_junk_hints() -> None:
    signals = link_signals(
        "https://example.com/login?page=2",
        "Sign in",
        "footer",
        source_url="https://example.com/login",
    )
    assert signals["in_footer"] is True
    assert signals["is_auth"] is True
    assert signals["is_pagination"] is True
    assert signals["has_query"] is True
    assert signals["is_query_only_variant"] is True


def test_annotate_populates_every_candidate() -> None:
    page = PageContent(
        url="https://example.com/",
        links=[
            LinkCandidate(
                id="l0",
                url="https://example.com/docs",
                normalized_url="https://example.com/docs",
                anchor_text="Docs",
                section_role="nav",
            )
        ],
        sections=[SectionCandidate(id="s0", role="footer", label="Legal")],
    )

    result = annotate(page)

    assert result.links[0].signals["in_nav"] is True
    assert result.sections[0].signals["is_footer"] is True
