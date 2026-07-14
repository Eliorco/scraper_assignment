"""Environment-backed application configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from ``SCRAPER_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="SCRAPER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    start_url: str | None = None
    max_depth: int = Field(default=2, ge=0)
    max_pages: int = Field(default=100, ge=1)
    max_candidates_per_page: int = Field(default=400, ge=1)
    same_domain_only: bool = True
    respect_robots: bool = True
    concurrency: int = Field(default=3, ge=1)
    request_delay_s: float = Field(default=1.0, ge=0.0)
    nav_timeout_ms: int = Field(default=30_000, ge=1)
    llm_model: str = "openai:gpt-5"
    output_dir: Path = Path("output")
    log_level: str = "INFO"
    log_format: str = "json"
