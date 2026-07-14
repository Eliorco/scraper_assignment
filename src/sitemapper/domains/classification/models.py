"""Classification output models — the agent's structured verdict."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from sitemapper.core.types import CandidateId, Importance


class Classification(BaseModel):
    """The agent's verdict for one candidate (link or section)."""

    model_config = ConfigDict(extra="forbid")

    target_id: CandidateId = Field(description="Echo the candidate's id, e.g. 'l3' or 's1'.")
    meaningful: bool = Field(
        description="True if this element is part of the site's meaningful structure/content; "
        "False for boilerplate (footers, login, language switchers, pagination, permalinks)."
    )
    importance: Importance = Field(description="high, medium, or low.")
    reason: str = Field(min_length=1, description="One concise sentence justifying the verdict.")
    confidence: float = Field(ge=0.0, le=1.0, description="0.0-1.0 certainty in this verdict.")


class PageClassification(BaseModel):
    """The agent's verdicts for every candidate on one page (structured output root)."""

    model_config = ConfigDict(extra="forbid")

    items: list[Classification] = Field(default_factory=list)
