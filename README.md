# Selective Sitemapper

A Python 3.12 CLI that renders a website with Playwright, extracts links and landmark
sections, asks a Pydantic AI classifier which elements are meaningful, and follows only
the useful in-scope links. Robots rules, a page budget, crawl depth, concurrency, and a
per-host delay bound the crawl.

## Local setup

```bash
uv sync --extra dev
uv run playwright install chromium
cp .env.example .env
```

Set `OPENAI_API_KEY` in the environment or `.env`, then run:

```bash
uv run sitemapper https://example.com --max-depth 2
# equivalent:
uv run python -m sitemapper https://example.com
```

The command writes `output/<url-slug>_<UTC timestamp>.json` and prints a short summary.
Run deterministic tests with `uv run pytest -m "not llm"` and quality checks with
`uv run ruff check .` and `uv run mypy`.

Configuration is available through `SCRAPER_*` variables shown in `.env.example`.
CLI options override environment values. Use `sitemapper --help` for all options.

## Docker

```bash
docker build -t selective-sitemapper .
docker run --rm \
  -e OPENAI_API_KEY \
  -v "$PWD/output:/app/output" \
  selective-sitemapper https://example.com
```

The image runs as an unprivileged user and uses the Playwright Chromium bundled in the
matching base image. Review a site's terms and robots policy before crawling it.

See `docs/PROJECT.md` for architecture and extension guidance.
