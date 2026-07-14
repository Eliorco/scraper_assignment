"""Pure, non-fetching helpers available to the classification agent."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from sitemapper.domains.extraction.signals import (
    is_auth,
    is_endless_list,
    is_language_switcher,
    is_pagination,
    is_permalink,
    path_depth,
)


def analyze_url_pattern(url: str, anchor_text: str = "") -> dict[str, bool | int | str]:
    """Analyze a supplied URL's shape without opening it."""
    parts = urlsplit(url)
    return {
        "host": parts.hostname or "",
        "path_depth": path_depth(url),
        "has_query": bool(parts.query),
        "query_key_count": len(parse_qs(parts.query)),
        "is_auth": is_auth(url, anchor_text),
        "is_language_switcher": is_language_switcher(url, anchor_text),
        "is_pagination": is_pagination(url, anchor_text),
        "is_endless_list": is_endless_list(url),
        "is_permalink": is_permalink(url),
    }


def identify_section_role(role: str, label: str = "") -> dict[str, bool | str]:
    """Explain the likely structural purpose of an already-extracted landmark."""
    normalized = role.strip().lower() or "body"
    purposes = {
        "nav": "primary or secondary navigation",
        "main": "main page content",
        "header": "repeated page header",
        "footer": "repeated page footer",
        "aside": "secondary or tangential content",
        "body": "unscoped page content",
    }
    return {
        "normalized_role": normalized,
        "likely_purpose": purposes.get(normalized, "custom page region"),
        "usually_boilerplate": normalized in {"header", "footer"},
        "has_label": bool(label.strip()),
    }


def check_junk_signals(signals: dict[str, bool | int | str]) -> dict[str, object]:
    """Summarize supplied deterministic anti-crawl signals; performs no I/O."""
    junk_keys = (
        "in_footer",
        "is_footer",
        "is_boilerplate",
        "is_legal_boilerplate",
        "has_legal_label",
        "is_auth",
        "is_language_switcher",
        "is_pagination",
        "is_query_only_variant",
        "is_endless_list",
        "is_permalink",
    )
    active = [key for key in junk_keys if signals.get(key) is True]
    return {
        "active_junk_signals": active,
        "junk_signal_count": len(active),
        "has_strong_junk_evidence": bool(active),
    }
