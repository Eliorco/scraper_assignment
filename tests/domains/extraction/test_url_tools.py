from __future__ import annotations

from sitemapper.domains.extraction.url_tools import (
    canonical_key,
    in_scope,
    normalize_url,
    registrable_domain,
    slugify_url,
)


def test_normalize_resolves_and_removes_tracking_and_fragment() -> None:
    assert (
        normalize_url(
            "https://Example.com/docs/start",
            "../guide?z=2&utm_source=test&a=1#intro",
        )
        == "https://example.com/guide?a=1&z=2"
    )


def test_normalize_rejects_non_web_targets() -> None:
    assert normalize_url("https://example.com", "mailto:hello@example.com") is None
    assert normalize_url("https://example.com", "#section") is None
    assert normalize_url("https://example.com", "") is None


def test_canonical_key_collapses_www_and_trailing_slash() -> None:
    assert canonical_key("https://www.example.com/docs/") == "https://example.com/docs"


def test_registrable_domain_handles_common_multilabel_suffix() -> None:
    assert registrable_domain("docs.example.co.uk") == "example.co.uk"


def test_scope_accepts_subdomains_but_rejects_other_domains() -> None:
    start = "https://www.example.com/"
    assert in_scope(start, "https://docs.example.com/guide", same_domain_only=True)
    assert not in_scope(start, "https://example.net/", same_domain_only=True)
    assert in_scope(start, "https://example.net/", same_domain_only=False)


def test_slugify_url_is_safe_and_bounded() -> None:
    assert slugify_url("https://Docs.Example.com/Guide/Intro?x=1") == (
        "docs-example-com_guide-intro"
    )
    assert len(slugify_url(f"https://example.com/{'a' * 200}")) <= 80
