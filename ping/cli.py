from __future__ import annotations

import argparse
from pathlib import Path

from .archivist import Archivist
from .app import CrawlApplication
from .fetcher import Fetcher
from .logging import PingLogger
from .models import CrawlSummary
from .sources import configured_sources
from .spider import Spider


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = PingLogger(verbose_enabled=args.verbose)
    sources = configured_sources(logger=logger)

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
    parser.add_argument("--verbose", action="store_true", help="Log every runtime decision")
    subparsers = parser.add_subparsers(dest="command")

    crawl = subparsers.add_parser("crawl", help="Start a new crawl")
    crawl.add_argument("source", nargs="?", default="bongthom", help="Source name")
    crawl.add_argument("--max-pages", type=int, default=None, help="Stop after this many fetched pages")

    resume = subparsers.add_parser("resume", help="Continue an interrupted crawl")
    resume.add_argument("source", nargs="?", default="bongthom", help="Source name")
    resume.add_argument("--max-pages", type=int, default=None, help="Stop after this many fetched pages")

    subparsers.add_parser("stats", help="Show archive statistics")
    subparsers.add_parser("sources", help="List configured websites")
    return parser


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
    print(f"pages visited: {summary.pages_visited}")
    print(f"pages failed: {summary.pages_failed}")
    print(f"jobs discovered: {summary.jobs_discovered}")
    print(f"new jobs: {summary.new_jobs}")
    print(f"updated jobs: {summary.updated_jobs}")
    print(f"unchanged jobs: {summary.unchanged_jobs}")
