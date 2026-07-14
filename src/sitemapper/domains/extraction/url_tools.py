"""Deterministic URL helpers: normalization, canonical dedup keys, domain scoping, slugify.

Pure functions, stdlib only. These decide *which URLs are the same* and *which are in
scope* — the backbone of dedup and same-domain crawling — so they are unit-tested heavily.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_DEFAULT_PORTS = {"http": "80", "https": "443"}

# Query params that never identify a distinct resource — dropped during normalization so
# ``?utm_source=x`` permalinks collapse onto the canonical URL.
_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "igshid",
        "ref",
        "ref_src",
        "ref_url",
        "source",
        "_ga",
        "yclid",
        "_hsenc",
        "_hsmi",
    }
)

# Multi-label public suffixes so ``registrable_domain`` yields eTLD+1 for common ccTLDs
# without shipping the full Public Suffix List (kept intentionally small; extend as needed).
_MULTI_SUFFIXES = frozenset(
    {
        "co.uk",
        "org.uk",
        "gov.uk",
        "ac.uk",
        "me.uk",
        "ltd.uk",
        "com.au",
        "org.au",
        "net.au",
        "edu.au",
        "gov.au",
        "co.jp",
        "or.jp",
        "ne.jp",
        "go.jp",
        "co.nz",
        "org.nz",
        "govt.nz",
        "co.in",
        "org.in",
        "net.in",
        "gov.in",
        "com.br",
        "org.br",
        "gov.br",
        "co.za",
        "org.za",
        "com.cn",
        "com.mx",
        "com.sg",
        "com.hk",
        "com.tr",
    }
)

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def normalize_url(base: str, href: str) -> str | None:
    """Resolve ``href`` against ``base`` into a canonical absolute URL.

    Returns ``None`` for anything that isn't a real navigable http(s) page
    (``mailto:``, ``tel:``, ``javascript:``, ``data:``, empty/fragment-only hrefs).
    Lowercases scheme+host, drops the default port, strips the fragment, removes
    tracking params, and sorts the remaining query so equivalent URLs compare equal.
    """
    cleaned_href = href.strip()
    if (
        not cleaned_href
        or cleaned_href.startswith("#")
        or cleaned_href.lower().startswith(("javascript:", "mailto:", "tel:", "data:"))
    ):
        return None

    absolute = urljoin(base, cleaned_href)
    parts = urlsplit(absolute)
    if parts.scheme.lower() not in _ALLOWED_SCHEMES or not parts.hostname:
        return None

    host = parts.hostname.lower()
    port = parts.port
    if port is not None and str(port) != _DEFAULT_PORTS.get(parts.scheme.lower()):
        netloc = f"{host}:{port}"
    else:
        netloc = host

    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(sorted(query_pairs))

    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def canonical_key(url: str) -> str:
    """A dedup key: two URLs pointing at the same resource share a key.

    Normalizes away a leading ``www.`` and a trailing slash (except the root), on top of
    what :func:`normalize_url` already did. Callers should prefer a page's ``rel=canonical``
    when present and only fall back to this.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = parts.port
    netloc = f"{host}:{port}" if port else host
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def registrable_domain(host: str) -> str:
    """eTLD+1 for a host, using a small multi-label suffix table (heuristic, not full PSL)."""
    host = host.lower().strip(".")
    if not host:
        return ""
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    last_two = ".".join(labels[-2:])
    if last_two in _MULTI_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last_two


def in_scope(start_url: str, candidate_url: str, *, same_domain_only: bool) -> bool:
    """Whether ``candidate_url`` is allowed by the configured crawl scope.

    With ``same_domain_only`` (the default), the candidate must share the start URL's
    registrable domain (subdomains of that domain are in scope). Otherwise any http(s)
    URL is allowed.
    """
    if not same_domain_only:
        return True
    start_reg = registrable_domain(host_of(start_url))
    cand_reg = registrable_domain(host_of(candidate_url))
    return bool(start_reg) and start_reg == cand_reg


def slugify_url(url: str) -> str:
    """A filesystem-safe slug from a URL's host+path, for output filenames.

    ``https://docs.example.com/guide/intro?x=1`` -> ``docs-example-com_guide-intro``.
    """
    parts = urlsplit(url)
    host = _SLUG_STRIP.sub("-", (parts.hostname or "site").lower()).strip("-")
    path = _SLUG_STRIP.sub("-", (parts.path or "").lower()).strip("-")
    slug = f"{host}_{path}" if path else host
    slug = slug.strip("-_") or "site"
    return slug[:80]
