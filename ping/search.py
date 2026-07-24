"""Contracts for local, pluggable keyword and semantic search.

No embedding model is selected or downloaded here.  This establishes the
boundary so that indexing can be introduced without coupling Sanya to one
provider or vector database.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchQuery:
    text: str
    limit: int = 50
    source_id: int | None = None
    company: str | None = None
    location: str | None = None


@dataclass(frozen=True)
class SearchResult:
    job_id: int
    revision_id: int
    score: float
    keyword_score: float | None = None
    semantic_score: float | None = None


class EmbeddingModel(Protocol):
    name: str
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


class SearchBackend(Protocol):
    def search(self, query: SearchQuery) -> list[SearchResult]: ...
