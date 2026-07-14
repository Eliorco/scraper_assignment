# Project map

> Living document: update this file on every feature or architecture iteration.

## Pipeline

`CrawlPipeline` performs deterministic breadth-first traversal:

1. Check `robots.txt`, then render the URL through the `Renderer` protocol.
2. Parse HTML into page metadata and `l{i}` link / `s{i}` section candidates.
3. Add deterministic junk signals.
4. Classify all candidates in one Pydantic AI call. This is the only non-deterministic stage;
   the classifier receives extracted data and has no fetching tools.
5. Apply depth, scope, canonical deduplication, robots, and page-budget constraints.
6. Assemble validated sitemap models, write timestamped JSON, and print a summary.

## Modules

- `core`: shared enums, Pydantic settings, and stdout logging.
- `domains/crawling`: rendering and robots ports plus Playwright, robots, and rate-limit adapters.
- `domains/extraction`: HTML parsing, URL normalization, and junk-signal annotation.
- `domains/classification`: structured model verdicts and the Pydantic AI adapter.
- `domains/sitemap`: output models, assembly, JSON persistence, and summary formatting.
- `pipeline`: BFS orchestration and the pure follow policy.
- `cli.py`: composition root; it is the only module that chooses concrete adapters.

The pipeline imports protocols rather than concrete browser or model implementations. Tests replace
both network-facing adapters with deterministic fakes.

## Configuration

`Settings` reads environment variables with the `SCRAPER_` prefix. Defaults include depth `2`,
100 pages, same-registrable-domain scope, robots enforcement, concurrency `3`, a one-second
per-host delay, a 30-second navigation timeout, and model `openai:gpt-5`. `OPENAI_API_KEY` is read
by the OpenAI provider. Generated data defaults to `output/`.

## Output model

Each page records URL, depth, title, canonical URL, headings, sections, and links. Every classified
element includes meaningfulness, importance, reason, and confidence. Links additionally record
whether they were followed and the deterministic follow reason. Top-level metadata captures the
configuration, model, run ID, page count, duration, and UTC generation timestamp.

## Testing

Pure unit tests cover extraction signals/URLs, follow policy, sitemap assembly, and writing.
Integration tests use static HTML and fake renderer/classifier adapters to exercise the full
pipeline without Chromium or an API key. Agent wiring uses Pydantic AI test models; live model
baselines are marked `llm` and are opt-in.

Do not install Chromium as part of ordinary unit-test setup. Install it only for real browser runs.
