from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Source:
    name: str
    base_url: str
    seed_urls: tuple[str, ...]
    enabled: bool = True
    crawl_delay_ms: int = 1500


@dataclass(frozen=True)
class FetchResult:
    url: str
    status_code: int | None
    html: str | None
    error: str | None = None


@dataclass(frozen=True)
class JobRecord:
    source_identifier: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    salary: str | None = None
    employment_type: str | None = None
    description: str | None = None
    application_url: str | None = None
    closing_date: str | None = None

    def revision_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "salary": self.salary,
            "employment_type": self.employment_type,
            "description": self.description,
            "application_url": self.application_url,
            "closing_date": self.closing_date,
        }


@dataclass(frozen=True)
class CrawlSummary:
    pages_visited: int = 0
    pages_failed: int = 0
    jobs_discovered: int = 0
    new_jobs: int = 0
    updated_jobs: int = 0
    unchanged_jobs: int = 0
