"""Source-plugin contracts.  Loading and discovery are a later milestone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .extractors.base import Extractor
from .models import Source


@dataclass(frozen=True)
class SourcePlugin:
    """Everything the core needs to crawl one source without source-specific code."""

    name: str
    source: Source
    extractor: Extractor
    allowed_domains: tuple[str, ...]
    robots_policy: str = "respect"


class PluginRegistry(Protocol):
    def get(self, name: str) -> SourcePlugin: ...

    def list(self) -> list[SourcePlugin]: ...
