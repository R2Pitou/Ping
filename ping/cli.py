from __future__ import annotations

import argparse
import json
from pathlib import Path

from .archivist import Archivist
from .app import CrawlApplication
from .fetcher import Fetcher
from .hasher import canonical_json, content_hash
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
        for source, _extractor in sources.values():
            archivist.upsert_source(source)

        if args.command == "sources":
            return _sources(archivist, sources)
        if args.command == "stats":
            return _stats(archivist)
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
