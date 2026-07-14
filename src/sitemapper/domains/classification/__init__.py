"""Classification domain: the LLM agent that judges link/section meaningfulness.

This is the ONLY non-deterministic part of the pipeline. The agent classifies
already-extracted data; it never fetches or scrapes (its tools have no network access).
"""
