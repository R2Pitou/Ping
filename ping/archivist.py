from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .hasher import content_hash
from .logging import NULL_LOGGER, PingLogger
from .models import CrawlSummary, JobRecord, Source, utc_now


class Archivist:
    def __init__(self, db_path: str | Path, logger: PingLogger = NULL_LOGGER) -> None:
        self.logger = logger
        self.db_path = Path(db_path)
        if self.db_path.parent != Path("."):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        if self.logger.trace_enabled:
            self.connection.set_trace_callback(lambda statement: self.logger.trace("Archivist", f"SQL {statement}"))
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.logger.verbose("Archivist", f"Opened database: {self.db_path}")
        self.initialize()

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                base_url TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                crawl_delay_ms INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS crawls (
                id INTEGER PRIMARY KEY,
                source_id INTEGER NOT NULL REFERENCES sources(id),
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                pages_visited INTEGER NOT NULL DEFAULT 0,
                pages_failed INTEGER NOT NULL DEFAULT 0,
                jobs_discovered INTEGER NOT NULL DEFAULT 0,
                new_jobs INTEGER NOT NULL DEFAULT 0,
                updated_jobs INTEGER NOT NULL DEFAULT 0,
                unchanged_jobs INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY,
                crawl_id INTEGER NOT NULL REFERENCES crawls(id),
                url TEXT NOT NULL,
                http_status INTEGER,
                fetched_at TEXT NOT NULL,
                html_hash TEXT,
                UNIQUE(crawl_id, url)
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY,
                source_id INTEGER NOT NULL REFERENCES sources(id),
                source_identifier TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(source_id, source_identifier)
            );

            CREATE TABLE IF NOT EXISTS job_revisions (
                id INTEGER PRIMARY KEY,
                job_id INTEGER NOT NULL REFERENCES jobs(id),
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                title TEXT,
                company TEXT,
                location TEXT,
                salary TEXT,
                employment_type TEXT,
                description TEXT,
                application_url TEXT,
                closing_date TEXT,
                UNIQUE(job_id, content_hash)
            );

            CREATE TABLE IF NOT EXISTS crawl_queue (
                id INTEGER PRIMARY KEY,
                crawl_id INTEGER NOT NULL REFERENCES crawls(id),
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                discovered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_error TEXT,
                UNIQUE(crawl_id, url)
            );
            """
        )
        self.connection.commit()
        self.logger.verbose("Archivist", "SQL transaction committed: schema initialized")

    def upsert_source(self, source: Source) -> int:
        now = utc_now()
        self.connection.execute(
            """
            INSERT INTO sources (name, base_url, enabled, crawl_delay_ms, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                base_url = excluded.base_url,
                enabled = excluded.enabled,
                crawl_delay_ms = excluded.crawl_delay_ms
            """,
            (source.name, source.base_url, int(source.enabled), source.crawl_delay_ms, now),
        )
        self.connection.commit()
        self.logger.verbose("Archivist", f"SQL transaction committed: source upserted {source.name}")
        row = self.connection.execute("SELECT id FROM sources WHERE name = ?", (source.name,)).fetchone()
        self.logger.verbose("Archivist", f"Source ready: {source.name} id={row['id']}")
        return int(row["id"])

    def start_crawl(self, source_id: int, seed_urls: Iterable[str]) -> int:
        seeds = tuple(seed_urls)
        now = utc_now()
        cursor = self.connection.execute(
            "INSERT INTO crawls (source_id, started_at, status) VALUES (?, ?, 'running')",
            (source_id, now),
        )
        crawl_id = int(cursor.lastrowid)
        self.logger.verbose("Archivist", f"Created crawl {crawl_id}")
        for url in seeds:
            self.enqueue(crawl_id, url)
        self.connection.commit()
        self.logger.verbose("Archivist", f"Queued {len(seeds)} seed URL(s)")
        self.logger.verbose("Archivist", f"SQL transaction committed: crawl {crawl_id} started")
        self._log_queue_size(crawl_id)
        return crawl_id

    def resume_crawl(self, source_id: int) -> int | None:
        row = self.connection.execute(
            """
            SELECT id FROM crawls
            WHERE source_id = ? AND status IN ('running', 'interrupted')
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (source_id,),
        ).fetchone()
        if row is None:
            self.logger.info("Archivist", "No resumable crawl found")
            return None
        self.logger.info("Archivist", f"Resuming crawl {row['id']}")
        self._log_queue_size(int(row["id"]))
        return int(row["id"])

    def enqueue(self, crawl_id: int, url: str) -> bool:
        now = utc_now()
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO crawl_queue (crawl_id, url, status, discovered_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?)
            """,
            (crawl_id, url, now, now),
        )
        queued = cursor.rowcount == 1
        if queued:
            self.logger.trace("Archivist", f"Queued URL: {url}")
        else:
            self.logger.trace("Spider", f"URL already visited or queued: {url}")
        return queued

    def enqueue_many(self, crawl_id: int, urls: Iterable[str]) -> int:
        queued_count = 0
        for url in urls:
            if self.enqueue(crawl_id, url):
                queued_count += 1
        self.connection.commit()
        self.logger.trace("Archivist", f"Queue mutation committed: {queued_count} URL(s) queued")
        self._log_queue_size(crawl_id)
        return queued_count

    def next_url(self, crawl_id: int) -> str | None:
        row = self.connection.execute(
            """
            SELECT url FROM crawl_queue
            WHERE crawl_id = ? AND status = 'queued'
            ORDER BY id
            LIMIT 1
            """,
            (crawl_id,),
        ).fetchone()
        if row is None:
            self.logger.info("Spider", "No queued URLs remain")
            return None
        self.logger.verbose("Spider", f"Next URL: {row['url']}")
        return str(row["url"])

    def mark_page_visited(self, crawl_id: int, url: str, status_code: int | None, page_hash: str | None) -> None:
        now = utc_now()
        self.connection.execute(
            """
            INSERT OR IGNORE INTO pages (crawl_id, url, http_status, fetched_at, html_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (crawl_id, url, status_code, now, page_hash),
        )
        self.connection.execute(
            """
            UPDATE crawl_queue
            SET status = 'visited', attempts = attempts + 1, updated_at = ?, last_error = NULL
            WHERE crawl_id = ? AND url = ?
            """,
            (now, crawl_id, url),
        )
        self.connection.execute(
            "UPDATE crawls SET pages_visited = pages_visited + 1 WHERE id = ?",
            (crawl_id,),
        )
        self.connection.commit()
        self.logger.verbose("Archivist", f"Stored page: HTTP {status_code or 'unknown'} {url}")
        self.logger.verbose("Archivist", "SQL transaction committed: page marked visited")
        self._log_queue_size(crawl_id)

    def mark_page_failed(self, crawl_id: int, url: str, status_code: int | None, error: str) -> None:
        now = utc_now()
        self.connection.execute(
            """
            INSERT OR IGNORE INTO pages (crawl_id, url, http_status, fetched_at, html_hash)
            VALUES (?, ?, ?, ?, NULL)
            """,
            (crawl_id, url, status_code, now),
        )
        self.connection.execute(
            """
            UPDATE crawl_queue
            SET status = 'failed', attempts = attempts + 1, updated_at = ?, last_error = ?
            WHERE crawl_id = ? AND url = ?
            """,
            (now, error, crawl_id, url),
        )
        self.connection.execute(
            "UPDATE crawls SET pages_failed = pages_failed + 1 WHERE id = ?",
            (crawl_id,),
        )
        self.connection.commit()
        self.logger.info("Archivist", f"Stored failed page: {url}")
        self.logger.info("Archivist", f"Failure reason: {error}")
        self.logger.verbose("Archivist", "SQL transaction committed: page marked failed")
        self._log_queue_size(crawl_id)

    def store_job(self, crawl_id: int, source_id: int, job: JobRecord) -> str:
        now = utc_now()
        digest = content_hash(job.revision_payload())
        self.logger.verbose("Hasher", f"SHA256 {digest}")
        row = self.connection.execute(
            """
            SELECT id FROM jobs
            WHERE source_id = ? AND source_identifier = ?
            """,
            (source_id, job.source_identifier),
        ).fetchone()

        if row is None:
            self.logger.verbose("Archivist", f"New job found: {job.source_identifier}")
            cursor = self.connection.execute(
                """
                INSERT INTO jobs (source_id, source_identifier, first_seen, last_seen, active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (source_id, job.source_identifier, now, now),
            )
            job_id = int(cursor.lastrowid)
            self._insert_revision(job_id, digest, job)
            self.connection.execute(
                """
                UPDATE crawls
                SET jobs_discovered = jobs_discovered + 1,
                    new_jobs = new_jobs + 1
                WHERE id = ?
                """,
                (crawl_id,),
            )
            self.connection.commit()
            self.logger.verbose("Archivist", "INSERT revision")
            self.logger.trace("Archivist", "SQL transaction committed: new job revision stored")
            return "new"

        job_id = int(row["id"])
        self.logger.verbose("Archivist", f"Existing job found: {job.source_identifier}")
        self.connection.execute(
            "UPDATE jobs SET last_seen = ?, active = 1 WHERE id = ?",
            (now, job_id),
        )
        latest = self.connection.execute(
            """
            SELECT content_hash FROM job_revisions
            WHERE job_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        self.connection.execute(
            "UPDATE crawls SET jobs_discovered = jobs_discovered + 1 WHERE id = ?",
            (crawl_id,),
        )
        if latest and latest["content_hash"] == digest:
            self.logger.verbose("Archivist", "Content unchanged")
            self.connection.execute(
                "UPDATE crawls SET unchanged_jobs = unchanged_jobs + 1 WHERE id = ?",
                (crawl_id,),
            )
            self.connection.commit()
            self.logger.verbose("Archivist", "UPDATE last_seen")
            self.logger.trace("Archivist", "SQL transaction committed: job last_seen updated")
            return "unchanged"

        self.logger.verbose("Archivist", "Content changed; creating revision")
        self._insert_revision(job_id, digest, job)
        self.connection.execute(
            "UPDATE crawls SET updated_jobs = updated_jobs + 1 WHERE id = ?",
            (crawl_id,),
        )
        self.connection.commit()
        self.logger.verbose("Archivist", "INSERT revision")
        self.logger.trace("Archivist", "SQL transaction committed: updated job revision stored")
        return "updated"

    def _insert_revision(self, job_id: int, digest: str, job: JobRecord) -> None:
        payload = job.revision_payload()
        self.connection.execute(
            """
            INSERT OR IGNORE INTO job_revisions (
                job_id, content_hash, created_at, title, company, location, salary,
                employment_type, description, application_url, closing_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                digest,
                utc_now(),
                payload["title"],
                payload["company"],
                payload["location"],
                payload["salary"],
                payload["employment_type"],
                payload["description"],
                payload["application_url"],
                payload["closing_date"],
            ),
        )

    def finish_crawl(self, crawl_id: int, status: str) -> None:
        self.connection.execute(
            "UPDATE crawls SET finished_at = ?, status = ? WHERE id = ?",
            (utc_now(), status, crawl_id),
        )
        self.connection.commit()
        self.logger.verbose("Archivist", f"Crawl {crawl_id} finished with status: {status}")
        self.logger.verbose("Archivist", "SQL transaction committed: crawl finished")

    def crawl_summary(self, crawl_id: int) -> CrawlSummary:
        row = self.connection.execute(
            """
            SELECT pages_visited, pages_failed, jobs_discovered, new_jobs, updated_jobs, unchanged_jobs
            FROM crawls
            WHERE id = ?
            """,
            (crawl_id,),
        ).fetchone()
        if row is None:
            return CrawlSummary()
        return CrawlSummary(**dict(row))

    def aggregate_stats(self) -> dict[str, int]:
        pages = self.connection.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN html_hash IS NULL THEN 1 ELSE 0 END) AS failed FROM pages"
        ).fetchone()
        jobs = self.connection.execute("SELECT COUNT(*) AS total FROM jobs").fetchone()
        revisions = self.connection.execute("SELECT COUNT(*) AS total FROM job_revisions").fetchone()
        crawls = self.connection.execute("SELECT COUNT(*) AS total FROM crawls").fetchone()
        return {
            "crawls": int(crawls["total"] or 0),
            "pages_visited": int((pages["total"] or 0) - (pages["failed"] or 0)),
            "pages_failed": int(pages["failed"] or 0),
            "jobs_discovered": int(jobs["total"] or 0),
            "job_revisions": int(revisions["total"] or 0),
        }

    def list_sources(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT name, base_url, enabled, crawl_delay_ms, created_at FROM sources ORDER BY name"
            )
        )

    def _log_queue_size(self, crawl_id: int) -> None:
        row = self.connection.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) AS queued,
                SUM(CASE WHEN status = 'visited' THEN 1 ELSE 0 END) AS visited,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM crawl_queue
            WHERE crawl_id = ?
            """,
            (crawl_id,),
        ).fetchone()
        self.logger.verbose(
            "Archivist",
            (
                f"Queue size: queued={row['queued'] or 0} "
                f"visited={row['visited'] or 0} failed={row['failed'] or 0}"
            ),
        )
