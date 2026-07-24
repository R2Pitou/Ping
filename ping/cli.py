from __future__ import annotations

import argparse
import json
from pathlib import Path

from .archivist import Archivist
from .app import CrawlApplication
from .fetcher import Fetcher
from .hasher import canonical_json, content_hash
from .inspection import render_job_detail, render_records, render_rows
from .inspection_service import ArchiveInspectionService
from .logging import PingLogger
from .models import CrawlSummary
from .sources import configured_sources
from .spider import Spider


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 1

    logger = PingLogger(level=_log_level(args))

    if args.command == "fetch":
        return _fetch(args, logger)
    if args.command == "hash":
        return _hash(args, logger)

    sources = configured_sources(logger=logger)

    if args.command == "extract":
        return _extract(args, logger, sources)

    with _open_archivist(args.db, logger) as archivist:
        if args.command in {"crawl", "resume", "sources"}:
            for source, _extractor in sources.values():
                archivist.upsert_source(source)

        if args.command == "sources":
            return _sources(archivist, sources)
        if args.command == "stats":
            return _stats(archivist)
        if args.command == "inspect":
            return _inspect(args, archivist)
        if args.command in {"jobs", "show", "pages", "companies", "crawl-history", "revisions", "search", "doctor", "dump"}:
            return _inspect_command(args, archivist)
        if args.command in {"crawl", "resume"}:
            return _crawl(args, archivist, sources)

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ping",
        description="Respectful web spider for labour market observatories",
    )
    parser.add_argument("--db", default="ping.sqlite3", type=Path, help="SQLite database path")
    parser.add_argument("--verbose", action="store_true", help="Log developer-level details")
    parser.add_argument("--trace", action="store_true", help="Log every observable internal decision")
    subparsers = parser.add_subparsers(dest="command")

    crawl = subparsers.add_parser("crawl", help="Start a new crawl")
    crawl.add_argument("source", nargs="?", default="bongthom", help="Source name")
    crawl.add_argument("--max-pages", type=int, default=None, help="Stop after this many fetched pages")

    resume = subparsers.add_parser("resume", help="Continue an interrupted crawl")
    resume.add_argument("source", nargs="?", default="bongthom", help="Source name")
    resume.add_argument("--max-pages", type=int, default=None, help="Stop after this many fetched pages")

    subparsers.add_parser("stats", help="Show archive statistics")
    subparsers.add_parser("sources", help="List configured websites")

    inspect = subparsers.add_parser("inspect", help="Inspect persisted Sanya records")
    inspect.add_argument("table", choices=("sources", "crawls", "pages", "jobs", "revisions", "queue"))
    inspect.add_argument("--id", type=int, help="Show a complete record by primary key")
    inspect.add_argument("--source", dest="source_id", type=int, help="Filter by source ID")
    inspect.add_argument("--crawl", dest="crawl_id", type=int, help="Filter by crawl ID")
    inspect.add_argument("--job", dest="job_id", type=int, help="Filter by job ID")
    inspect.add_argument("--limit", type=int, default=50, help="Maximum records to display (default: 50)")

    jobs = subparsers.add_parser("jobs", help="List archived jobs")
    jobs.add_argument("--source", dest="source_id", type=int, help="Filter by source ID")
    jobs.add_argument("--limit", type=int, default=50, help="Maximum records to display")

    show = subparsers.add_parser("show", help="Show a job and its immutable revision history")
    show.add_argument("id", type=int, help="Job ID")

    pages = subparsers.add_parser("pages", help="List fetched pages")
    pages.add_argument("--crawl", dest="crawl_id", type=int, help="Filter by crawl ID")
    pages.add_argument("--limit", type=int, default=50, help="Maximum records to display")

    companies = subparsers.add_parser("companies", help="List observed companies")
    companies.add_argument("query", nargs="?", default=None, help="Optional company-name filter")
    companies.add_argument("--limit", type=int, default=50, help="Maximum records to display")

    history = subparsers.add_parser("crawl-history", help="List crawl executions")
    history.add_argument("--source", dest="source_id", type=int, help="Filter by source ID")
    history.add_argument("--limit", type=int, default=50, help="Maximum records to display")

    revisions = subparsers.add_parser("revisions", help="List immutable job revisions")
    revisions.add_argument("--job", dest="job_id", type=int, help="Filter by job ID")
    revisions.add_argument("--limit", type=int, default=50, help="Maximum records to display")

    search = subparsers.add_parser("search", help="Search current jobs by keyword")
    search.add_argument("query", help="Keyword query")
    search.add_argument("--limit", type=int, default=50, help="Maximum records to display")

    subparsers.add_parser("doctor", help="Check archive integrity and table counts")

    dump = subparsers.add_parser("dump", help="Dump a Sanya table as JSON")
    dump.add_argument("table", choices=("sources", "crawls", "pages", "jobs", "revisions", "queue"))
    dump.add_argument("--limit", type=int, default=1000, help="Maximum records to emit")

    fetch = subparsers.add_parser("fetch", help="Run only the fetcher against one URL")
    fetch.add_argument("url", help="URL to fetch")

    extract = subparsers.add_parser("extract", help="Run only an extractor against one HTML file")
    extract.add_argument("html_file", type=Path, help="HTML file to parse")
    extract.add_argument("--source", default="bongthom", help="Extractor source name")
    extract.add_argument("--url", default=None, help="Source URL represented by the HTML file")

    hash_command = subparsers.add_parser("hash", help="Run only the hasher against one JSON file")
    hash_command.add_argument("json_file", type=Path, help="JSON object to normalize and hash")
    return parser


def _log_level(args: argparse.Namespace) -> str:
    if args.trace:
        return "trace"
    if args.verbose:
        return "verbose"
    return "normal"


class _open_archivist:
    def __init__(self, db_path: Path, logger: PingLogger) -> None:
        self.archivist = Archivist(db_path, logger=logger)

    def __enter__(self) -> Archivist:
        return self.archivist

    def __exit__(self, *_args: object) -> None:
        self.archivist.close()


def _sources(archivist: Archivist, sources: dict[str, object]) -> int:
    rows = archivist.list_sources()
    if not rows:
        print("No sources configured.")
        return 0
    for row in rows:
        status = "enabled" if row["enabled"] else "disabled"
        print(f"{row['name']}: {row['base_url']} ({status}, delay={row['crawl_delay_ms']}ms)")
    return 0


def _stats(archivist: Archivist) -> int:
    stats = archivist.aggregate_stats()
    print(f"pages visited: {stats['pages_visited']}")
    print(f"pages failed: {stats['pages_failed']}")
    print(f"jobs discovered: {stats['jobs_discovered']}")
    print(f"job revisions: {stats['job_revisions']}")
    print(f"crawls: {stats['crawls']}")
    return 0


def _inspect(args: argparse.Namespace, archivist: Archivist) -> int:
    try:
        rows = archivist.inspect_records(
            args.table,
            record_id=args.id,
            source_id=args.source_id,
            crawl_id=args.crawl_id,
            job_id=args.job_id,
            limit=args.limit,
        )
    except ValueError as error:
        print(f"Inspection rejected: {error}")
        return 2
    if args.table == "jobs" and args.id is not None and rows:
        revisions = archivist.inspect_records("revisions", job_id=args.id, limit=args.limit)
        print(render_job_detail(rows[0], revisions))
    else:
        print(render_records(args.table, rows, detailed=args.id is not None))
    return 0


def _inspect_command(args: argparse.Namespace, archivist: Archivist) -> int:
    service = ArchiveInspectionService(archivist)
    if args.command == "show":
        job, revisions = service.job(args.id)
        if job is None:
            print(f"No job found with id {args.id}.")
            return 1
        print(render_job_detail(job, revisions))
        return 0

    if args.command == "companies":
        print(render_rows(("company", "active_jobs", "last_observed"), service.companies(args.query, args.limit)))
        return 0

    if args.command == "search":
        print(render_rows(
            ("source_identifier", "title", "company", "location", "salary", "created_at"),
            service.search(args.query, args.limit),
        ))
        return 0

    if args.command == "doctor":
        report = service.doctor()
        print(f"Database: {report.database_path}")
        print(f"Integrity: {report.integrity}")
        print(f"Foreign key violations: {report.foreign_key_violations}")
        print("Table counts")
        for table, count in report.tables.items():
            print(f"  {table}: {count}")
        return 0 if report.healthy else 1

    if args.command == "dump":
        rows = service.records(args.table, limit=args.limit)
        print(json.dumps([dict(row) for row in rows], indent=2, sort_keys=True))
        return 0

    table_by_command = {
        "jobs": "jobs",
        "pages": "pages",
        "crawl-history": "crawls",
        "revisions": "revisions",
    }
    table = table_by_command[args.command]
    rows = service.records(
        table,
        source_id=getattr(args, "source_id", None),
        crawl_id=getattr(args, "crawl_id", None),
        job_id=getattr(args, "job_id", None),
        limit=args.limit,
    )
    print(render_records(table, rows))
    return 0


def _crawl(args: argparse.Namespace, archivist: Archivist, sources: dict[str, object]) -> int:
    if args.source not in sources:
        archivist.logger.info("Spider", f"Unknown source: {args.source}")
        return 2

    source, extractor = sources[args.source]
    if not source.enabled:
        archivist.logger.info("Spider", f"Source is disabled: {source.name}")
        return 2

    source_id = archivist.upsert_source(source)
    spider = Spider(
        archivist=archivist,
        source=source,
        source_id=source_id,
        extractor=extractor,
        logger=archivist.logger,
    )
    app = CrawlApplication(archivist=archivist, fetcher=Fetcher(logger=archivist.logger), spider=spider)

    if args.command == "crawl":
        crawl_id, summary = app.start(max_pages=args.max_pages)
    else:
        crawl_id, summary = app.resume(max_pages=args.max_pages)
        if crawl_id is None:
            archivist.logger.info("Spider", f"No resumable crawl found for {source.name}")
            return 1

    archivist.logger.info("Spider", f"Crawl id: {crawl_id}")
    _print_summary(summary)
    return 0


def _print_summary(summary: CrawlSummary) -> None:
    print("Summary")
    print(f"    Pages: {summary.pages_visited}")
    print(f"    Failed: {summary.pages_failed}")
    print(f"    Jobs: {summary.jobs_discovered}")
    print(f"    New: {summary.new_jobs}")
    print(f"    Updated: {summary.updated_jobs}")
    print(f"    Unchanged: {summary.unchanged_jobs}")


def _fetch(args: argparse.Namespace, logger: PingLogger) -> int:
    result = Fetcher(logger=logger).fetch(args.url)
    if result.html is None:
        logger.info("Fetcher", f"Fetch failed: {result.error or 'unknown error'}")
        return 1
    logger.verbose("Fetcher", f"Fetched characters: {len(result.html)}")
    return 0


def _extract(args: argparse.Namespace, logger: PingLogger, sources: dict[str, object]) -> int:
    if args.source not in sources:
        logger.info("Extractor", f"Unknown source: {args.source}")
        return 2

    html = args.html_file.read_text(encoding="utf-8", errors="replace")
    source, extractor = sources[args.source]
    page_url = args.url or f"{source.base_url.rstrip('/')}/{args.html_file.name}"
    logger.info("Extractor", f"Reading {args.html_file}")
    logger.info("Extractor", f"Assuming source URL: {page_url}")
    links = extractor.links(html, page_url)
    logger.info("Extractor", f"Parsed {len(links)} link(s)")
    for link in sorted(links):
        logger.trace("Extractor", f"Link: {link}")
    jobs = extractor.jobs(html, page_url)
    logger.info("Extractor", f"Parsed {len(jobs)} job(s)")
    if jobs:
        print(json.dumps([{"source_identifier": job.source_identifier, **job.revision_payload()} for job in jobs], indent=2))
    return 0


def _hash(args: argparse.Namespace, logger: PingLogger) -> int:
    payload = json.loads(args.json_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        logger.info("Hasher", "Rejected input: top-level JSON value must be an object")
        return 2

    normalized = json.loads(canonical_json(payload))
    logger.info("Hasher", "Normalized object")
    print(json.dumps(normalized, indent=2, sort_keys=True))
    logger.info("Hasher", f"SHA256 {content_hash(payload)}")
    return 0
