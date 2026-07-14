"""Persist sitemap JSON and produce the human-readable run summary."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

from sitemapper.domains.extraction.url_tools import slugify_url
from sitemapper.domains.sitemap.models import ClassifiedLink, Sitemap


def output_path(sitemap: Sitemap, output_dir: Path) -> Path:
    """Derive the timestamped filename from root URL and generation time."""

    generated_at = sitemap.generated_at
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    timestamp = generated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return output_dir / f"{slugify_url(sitemap.root_url)}_{timestamp}.json"


def write(sitemap: Sitemap, output_dir: Path | str = Path("output")) -> Path:
    """Write pretty, UTF-8 sitemap JSON and return its path."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = output_path(sitemap, directory)
    path.write_text(sitemap.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def summary(sitemap: Sitemap, path: Path) -> str:
    """Build a concise summary suitable for CLI stdout."""

    elements = [element for page in sitemap.pages for element in [*page.links, *page.sections]]
    meaningful = sum(element.meaningful for element in elements)
    top_links: list[ClassifiedLink] = sorted(
        (link for page in sitemap.pages for link in page.links if link.meaningful),
        key=lambda link: link.confidence,
        reverse=True,
    )[:5]
    lines = [
        f"Root URL: {sitemap.root_url}",
        f"Output: {path}",
        f"Pages visited: {sitemap.run.pages_visited}",
        f"Elements: {meaningful} meaningful, {len(elements) - meaningful} non-meaningful",
    ]
    if top_links:
        lines.append("Top meaningful links:")
        lines.extend(
            f"  - {link.url} ({link.confidence:.2f}) — {link.reason}" for link in top_links
        )
    return "\n".join(lines)
