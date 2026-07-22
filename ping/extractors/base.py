from __future__ import annotations

from abc import ABC, abstractmethod

from ping.models import JobRecord


class Extractor(ABC):
    @abstractmethod
    def links(self, html: str, page_url: str) -> set[str]:
        """Return crawlable links discovered in the page."""

    @abstractmethod
    def jobs(self, html: str, page_url: str) -> list[JobRecord]:
        """Return structured job advertisements discovered in the page."""
