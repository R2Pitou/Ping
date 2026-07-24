"""Read-only archive queries shared by the CLI, API, and future GUI.

This module is deliberately free of presentation and transport concerns.  It
keeps SQLite inspection logic out of command handlers and gives future FastAPI
and desktop clients the same evidence-backed view of Sanya.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from .archivist import Archivist
from .rok import Rok


@dataclass(frozen=True)
class DoctorReport:
    database_path: str
    integrity: str
    foreign_key_violations: int
    tables: dict[str, int]

    @property
    def healthy(self) -> bool:
        return self.integrity == "ok" and self.foreign_key_violations == 0


class ArchiveInspectionService:
    """Stable, read-only use cases for archive inspection."""

    def __init__(self, sanya: Archivist) -> None:
        self.sanya = sanya

    def records(self, table: str, **filters: Any) -> list[sqlite3.Row]:
        return self.sanya.inspect_records(table, **filters)

    def job(self, job_id: int) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
        jobs = self.sanya.inspect_records("jobs", record_id=job_id, limit=1)
        if not jobs:
            return None, []
        return jobs[0], self.sanya.inspect_records("revisions", job_id=job_id, limit=1000)

    def companies(self, query: str | None = None, limit: int = 50) -> list[sqlite3.Row]:
        conditions = ["company IS NOT NULL", "TRIM(company) <> ''"]
        values: list[object] = []
        if query and query.strip():
            conditions.append("company LIKE ?")
            values.append(f"%{query.strip()}%")
        values.append(limit)
        return list(
            self.sanya.connection.execute(
                f"""
                SELECT company, COUNT(*) AS active_jobs, MAX(created_at) AS last_observed
                FROM job_revisions
                WHERE id IN (
                    SELECT MAX(id) FROM job_revisions GROUP BY job_id
                ) AND {' AND '.join(conditions)}
                GROUP BY company
                ORDER BY active_jobs DESC, company COLLATE NOCASE
                LIMIT ?
                """,
                values,
            )
        )

    def search(self, query: str, limit: int = 50) -> list[sqlite3.Row]:
        return Rok(self.sanya).find(query, limit=limit)

    def doctor(self) -> DoctorReport:
        integrity = str(self.sanya.connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = len(list(self.sanya.connection.execute("PRAGMA foreign_key_check")))
        tables = {
            table: int(self.sanya.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
            for table, name in {
                "sources": "sources",
                "crawls": "crawls",
                "pages": "pages",
                "jobs": "jobs",
                "revisions": "job_revisions",
                "queue": "crawl_queue",
            }.items()
        }
        return DoctorReport(str(self.sanya.db_path), integrity, foreign_keys, tables)
