# syntax=docker/dockerfile:1
ARG PLAYWRIGHT_VERSION=1.61.0

FROM mcr.microsoft.com/playwright/python:v${PLAYWRIGHT_VERSION}-noble AS builder
ARG PLAYWRIGHT_VERSION
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python "playwright==${PLAYWRIGHT_VERSION}" .

FROM mcr.microsoft.com/playwright/python:v${PLAYWRIGHT_VERSION}-noble AS runtime
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    SCRAPER_OUTPUT_DIR=/app/output
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
RUN useradd --create-home --uid 10001 sitemapper && \
    mkdir -p /app/output && \
    chown -R sitemapper:sitemapper /app
USER sitemapper
VOLUME ["/app/output"]
ENTRYPOINT ["sitemapper"]
