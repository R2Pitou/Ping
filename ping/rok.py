"""Rok searches the archive without changing it."""

from dataclasses import dataclass
import sqlite3

from .archivist import Archivist


@dataclass(frozen=True)
class Rok:
    sanya: Archivist

    def find(self, query: str, limit: int = 50) -> list[sqlite3.Row]:
        self.sanya.logger.info("Rok", f"Searching archive: {query!r}")
        results = self.sanya.find_jobs(query, limit=limit)
        self.sanya.logger.info("Rok", f"{len(results)} record(s) found")
        return results
