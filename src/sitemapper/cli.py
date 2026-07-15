"""Command-line composition root."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sitemapper.core.config import Settings
from sitemapper.core.logging import configure_logging
from sitemapper.domains.classification.agent import SitemapClassifier
from sitemapper.domains.crawling.playwright_renderer import PlaywrightRenderer
from sitemapper.domains.crawling.rate_limiter import RateLimiter
from sitemapper.domains.crawling.robots import RobotsTxtChecker
from sitemapper.domains.extraction.parser import parse
from sitemapper.domains.sitemap.builder import build
from sitemapper.domains.sitemap.models import SitemapConfig
from sitemapper.domains.sitemap.writer import summary, write
from sitemapper.pipeline.orchestrator import CrawlPipeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a selective, classified website sitemap.")
    parser.add_argument("url", nargs="?", help="HTTP(S) URL to crawl")
    parser.add_argument("--max-depth", type=int)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-candidates-per-page", type=int)
    parser.add_argument("--classification-batch-size", type=int)
    parser.add_argument("--classification-concurrency", type=int)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--request-delay", type=float, dest="request_delay_s")
    parser.add_argument("--nav-timeout-ms", type=int)
    parser.add_argument("--model", dest="llm_model")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--ignore-robots", action="store_true")
    parser.add_argument("--allow-external", action="store_true")
    return parser


def _settings(args: argparse.Namespace) -> Settings:
    settings = Settings()
    overrides = {
        key: value
        for key, value in vars(args).items()
        if key not in {"url", "ignore_robots", "allow_external"} and value is not None
    }
    if args.ignore_robots:
        overrides["respect_robots"] = False
    if args.allow_external:
        overrides["same_domain_only"] = False
    values = settings.model_dump()
    values.update(overrides)
    return Settings.model_validate(values)


async def _run(start_url: str, settings: Settings) -> Path:
    run_id = uuid4().hex
    limiter = RateLimiter(
        concurrency=settings.concurrency,
        delay_s=settings.request_delay_s,
    )
    renderer = PlaywrightRenderer(
        nav_timeout_ms=settings.nav_timeout_ms,
        limiter=limiter,
    )
    pipeline = CrawlPipeline(
        renderer=renderer,
        robots=RobotsTxtChecker(),
        classifier=SitemapClassifier(
            model=settings.llm_model,
            batch_size=settings.classification_batch_size,
            concurrency=settings.classification_concurrency,
        ),
        parser=parse,
        max_depth=settings.max_depth,
        max_pages=settings.max_pages,
        max_candidates_per_page=settings.max_candidates_per_page,
        same_domain_only=settings.same_domain_only,
        respect_robots=settings.respect_robots,
    )

    started = perf_counter()
    try:
        pages = await pipeline.run(start_url)
    finally:
        await renderer.aclose()
    sitemap = build(
        root_url=start_url,
        pages=pages,
        config=SitemapConfig(
            max_depth=settings.max_depth,
            max_pages=settings.max_pages,
            max_candidates_per_page=settings.max_candidates_per_page,
            classification_batch_size=settings.classification_batch_size,
            classification_concurrency=settings.classification_concurrency,
            same_domain_only=settings.same_domain_only,
            respect_robots=settings.respect_robots,
        ),
        llm_model=settings.llm_model,
        duration_s=perf_counter() - started,
        run_id=run_id,
    )
    path = write(sitemap, settings.output_dir)
    print(summary(sitemap, path))
    return path


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""

    args = _parser().parse_args(argv)
    settings = _settings(args)
    configure_logging(settings.log_level, settings.log_format)
    start_url = args.url or settings.start_url
    if not start_url:
        _parser().error("a URL argument or SCRAPER_START_URL is required")
    try:
        asyncio.run(_run(start_url, settings))
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except Exception:
        logging.getLogger(__name__).exception("Sitemap run failed")
        return 1
    return 0
