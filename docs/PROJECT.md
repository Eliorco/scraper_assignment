# Project map

> Living document: update this file on every feature or architecture iteration.

## Pipeline

`CrawlPipeline` performs deterministic breadth-first traversal:

1. Check `robots.txt`, then render the URL through the `Renderer` protocol.
2. Parse HTML into page metadata and `l{i}` link / `s{i}` section candidates.
3. Add deterministic junk signals.
4. Split the configured per-page candidate set into bounded chunks and classify several chunks
   concurrently with Pydantic AI. This is the only non-deterministic stage; the classifier receives
   extracted data and has no fetching tools.
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
100 pages, a 400-candidate per-page classification limit, 100 candidates per LLM request, four
concurrent LLM requests, same-registrable-domain scope, robots enforcement, renderer concurrency
`3`, a one-second per-host delay, a 30-second navigation timeout, and model `openai:gpt-5`.
`OPENAI_API_KEY` is read by the OpenAI provider. Generated data defaults to `output/`.

## Output model

Each page records URL, depth, title, canonical URL, headings, sections, and links. Every classified
element includes meaningfulness, importance, reason, and confidence. Links additionally record
whether they were followed and the deterministic follow reason. Top-level metadata captures the
configuration, model, run ID, page count, duration, and UTC generation timestamp.

## Oversized candidate batches

The current testing safeguard caps each page at 400 classification candidates so a large homepage
cannot invalidate the entire crawl by exceeding the model's structured-output capacity. Landmark
sections are retained first, followed by links in extraction order; excess links are dropped and
are neither classified nor followed.

The affected page remains in the sitemap as a partial result. Its JSON records `candidate_count`,
`classified_candidate_count`, `dropped_candidate_count`, and `classification_partial`. The runtime
also emits a warning when truncation happens, and the final CLI summary reports how many candidates
were dropped. Configure the limit with `SCRAPER_MAX_CANDIDATES_PER_PAGE` or
`--max-candidates-per-page`.

If the model still returns fewer verdicts than requested, the validated subset is retained and the
missing candidates are dropped under the same partial-result behavior. Duplicate or unexpected
candidate IDs remain hard errors because they cannot be matched safely.

Within the page cap, `SitemapClassifier` uses batches of 100 candidates and runs up to four model
requests concurrently. Successful batches are merged back into extraction order. If one request
fails after retries, successful batches remain available as partial results; if every request
fails, the classification error is raised. Configure this with `SCRAPER_CLASSIFICATION_BATCH_SIZE`
and `SCRAPER_CLASSIFICATION_CONCURRENCY`, or the matching CLI flags.

The page cap is a temporary testing behavior. A production implementation should also deduplicate
repeated candidates and adapt batch/concurrency limits to provider rate limits.

## Testing

Pure unit tests cover extraction signals/URLs, follow policy, sitemap assembly, and writing.
Integration tests use static HTML and fake renderer/classifier adapters to exercise the full
pipeline without Chromium or an API key. Agent wiring uses Pydantic AI test models; live model
baselines are marked `llm` and are opt-in.

Do not install Chromium as part of ordinary unit-test setup. Install it only for real browser runs.

## Planned runtime observability

Long crawls currently print only their final summary. A running container therefore confirms that
the process exists, but does not distinguish active work from a stalled browser or model request.
A future implementation should add:

- structured logs for each page and pipeline stage (`robots`, `render`, `extract`, `classify`,
  `follow`, and `write`), including URL, BFS depth, candidate count, queue size, and stage duration;
- elapsed-time progress after every completed page;
- periodic heartbeat logs while a slow render or LLM request is in flight, including the current
  stage and its elapsed time;
- configurable hard timeouts for each classification request and the overall crawl, with clear
  timeout errors and bounded retries;
- incremental/checkpoint output so completed pages survive a later timeout or failure; and
- Docker health reporting based on recent pipeline progress rather than merely process existence.

Logs and health data must never include API keys, full prompts, or other secrets.
