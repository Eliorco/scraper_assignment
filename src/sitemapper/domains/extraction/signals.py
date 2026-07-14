"""Deterministic 'junk' detectors — the anti-naive-crawl signal layer.

These do NOT decide what to follow. They flag patterns a naive crawler blindly follows
(footers, login/auth, language switchers, pagination, permalinks, endless archive lists)
and hand those flags to the classification agent as hints. The agent makes the call; the
deterministic filter then acts on the agent's verdict. Pure functions, stdlib only.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from sitemapper.domains.extraction.models import PageContent, SignalMap

_AUTH_PATH = re.compile(
    r"(?:^|/)(login|log-in|signin|sign-in|signup|sign-up|register|logout|log-out|"
    r"account|auth|password|forgot|sso|oauth|my-account|subscribe|checkout|cart)(?:/|$)",
    re.IGNORECASE,
)
_AUTH_ANCHOR = re.compile(
    r"\b(log ?in|sign ?in|sign ?up|register|log ?out|my account|create account|subscribe)\b",
    re.IGNORECASE,
)

# 2-letter language or language-region path segment, e.g. /en/ or /en-us/ or /pt-BR/.
_LANG_SEGMENT = re.compile(r"^[a-z]{2}(?:[-_][a-z]{2})?$", re.IGNORECASE)
_LANG_QUERY_KEYS = frozenset({"lang", "language", "locale", "hl", "lr"})
_LANG_NAMES = frozenset(
    {
        "english",
        "espanol",
        "español",
        "deutsch",
        "français",
        "francais",
        "italiano",
        "portugues",
        "português",
        "日本語",
        "中文",
        "русский",
        "العربية",
        "nederlands",
        "svenska",
        "polski",
        "türkçe",
        "turkce",
        "한국어",
    }
)

_PAGINATION_PATH = re.compile(r"/(?:page|pg)/\d+", re.IGNORECASE)
_PAGINATION_KEYS = frozenset({"page", "p", "pg", "start", "offset", "from", "paged"})
_PAGINATION_ANCHOR = re.compile(
    r"^\s*(?:\d+|next|previous|prev|older|newer|»|«|>|<|…)\s*$", re.IGNORECASE
)

_ENDLESS_PATH = re.compile(
    r"(?:^|/)(tag|tags|category|categories|topic|topics|archive|archives|author|authors|"
    r"label|labels|search)(?:/|$)",
    re.IGNORECASE,
)
# Date-in-path, e.g. /2026/07/ or /2026/07/14/ — archive listings or dated article permalinks.
_DATE_PATH = re.compile(r"/(?:19|20)\d{2}/(?:0[1-9]|1[0-2])(?:/(?:0[1-9]|[12]\d|3[01]))?(?:/|$)")

_LEGAL_ANCHOR = re.compile(
    r"\b(privacy|terms|cookie|legal|imprint|gdpr|copyright|©|all rights reserved)\b",
    re.IGNORECASE,
)


def _path(url: str) -> str:
    return urlsplit(url).path or "/"


def path_depth(url: str) -> int:
    """Number of non-empty path segments; a rough proxy for how 'deep' a URL is."""
    return len([seg for seg in _path(url).split("/") if seg])


def is_auth(url: str, anchor_text: str = "") -> bool:
    return bool(_AUTH_PATH.search(_path(url)) or _AUTH_ANCHOR.search(anchor_text))


def is_language_switcher(url: str, anchor_text: str = "") -> bool:
    parts = urlsplit(url)
    first_seg = next((s for s in (parts.path or "").split("/") if s), "")
    if _LANG_SEGMENT.match(first_seg):
        return True
    query = parse_qs(parts.query)
    if any(k.lower() in _LANG_QUERY_KEYS for k in query):
        return True
    return anchor_text.strip().lower() in _LANG_NAMES


def is_pagination(url: str, anchor_text: str = "") -> bool:
    if _PAGINATION_PATH.search(_path(url)):
        return True
    query = parse_qs(urlsplit(url).query)
    if any(k.lower() in _PAGINATION_KEYS and _has_digit(v) for k, v in query.items()):
        return True
    return bool(anchor_text) and bool(_PAGINATION_ANCHOR.match(anchor_text))


def is_endless_list(url: str) -> bool:
    path = _path(url)
    return bool(_ENDLESS_PATH.search(path) or _DATE_PATH.search(path))


def is_permalink(url: str) -> bool:
    """A dated, deep article URL — the kind of endless per-article link to avoid following."""
    return bool(_DATE_PATH.search(_path(url))) and path_depth(url) >= 3


def _has_digit(values: list[str]) -> bool:
    return any(any(ch.isdigit() for ch in v) for v in values)


def link_signals(
    normalized_url: str,
    anchor_text: str,
    section_role: str,
    *,
    source_url: str | None = None,
) -> SignalMap:
    """Compute the full signal map for one link candidate."""
    role = (section_role or "").lower()
    target_parts = urlsplit(normalized_url)
    source_parts = urlsplit(source_url) if source_url else None
    query_only_variant = bool(
        source_parts
        and target_parts.scheme == source_parts.scheme
        and target_parts.netloc == source_parts.netloc
        and (target_parts.path or "/") == (source_parts.path or "/")
        and target_parts.query
        and target_parts.query != source_parts.query
    )
    return {
        "section_role": role,
        "in_footer": role == "footer",
        "in_header": role == "header",
        "in_nav": role == "nav",
        "path_depth": path_depth(normalized_url),
        "has_query": bool(target_parts.query),
        "is_query_only_variant": query_only_variant,
        "is_auth": is_auth(normalized_url, anchor_text),
        "is_language_switcher": is_language_switcher(normalized_url, anchor_text),
        "is_pagination": is_pagination(normalized_url, anchor_text),
        "is_endless_list": is_endless_list(normalized_url),
        "is_permalink": is_permalink(normalized_url),
        "is_legal_boilerplate": bool(_LEGAL_ANCHOR.search(anchor_text)),
    }


def section_signals(role: str, label: str) -> SignalMap:
    """Compute the signal map for one landmark section."""
    role_l = (role or "").lower()
    return {
        "role": role_l,
        "is_footer": role_l == "footer",
        "is_header": role_l == "header",
        "is_nav": role_l == "nav",
        "is_boilerplate": role_l in {"footer", "header"},
        "has_legal_label": bool(_LEGAL_ANCHOR.search(label)),
    }


def annotate(page: PageContent, source_url: str | None = None) -> PageContent:
    """Return a copy of ``page`` with every link/section's ``signals`` populated.

    Deterministic enrichment step run right before classification, so the agent sees the
    same structured hints on every run.
    """
    source = source_url or page.url
    for link in page.links:
        link.signals = link_signals(
            link.normalized_url,
            link.anchor_text,
            link.section_role,
            source_url=source,
        )
    for section in page.sections:
        section.signals = section_signals(section.role, section.label)
    return page
