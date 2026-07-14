"""Classification port consumed by the crawl pipeline."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sitemapper.domains.classification.models import Classification
from sitemapper.domains.extraction.models import PageContent


@runtime_checkable
class Classifier(Protocol):
    """Judges already-extracted candidates without fetching any web content."""

    async def classify(self, page: PageContent) -> list[Classification]:
        """Return one verdict for every link and section in ``page``."""
        ...
