"""Selective web sitemapper.

Given a start URL, render pages with Playwright, let a Pydantic AI agent judge which
links/sections are *meaningful*, and emit a structured sitemap JSON. Every stage is
deterministic except the classification agent (the only LLM step); the LLM never fetches.
"""

__version__ = "0.1.0"
