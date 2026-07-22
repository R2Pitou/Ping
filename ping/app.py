from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .archivist import Archivist
from .fetcher import Fetcher
from .hasher import html_hash
from .logging import format_duration
from .models import CrawlSummary
from .spider import Spider


@dataclass
class CrawlApplication:
    archivist: Archivist
    fetcher: Fetcher
    spider: Spider
    max_consecutive_failures: int = 5

    def start(self, max_pages: int | None = None) -> tuple[int, CrawlSummary]:
        crawl_id = self.spider.start()
        return crawl_id, self._run(crawl_id, max_pages=max_pages)

    def resume(self, max_pages: int | None = None) -> tuple[int | None, CrawlSummary]:
        crawl_id = self.spider.resume()
        if crawl_id is None:
            return None, CrawlSummary()
        return crawl_id, self._run(crawl_id, max_pages=max_pages)

    def _run(self, crawl_id: int, max_pages: int | None) -> CrawlSummary:
        processed = 0
        consecutive_failures = 0

        while max_pages is None or processed < max_pages:
            self.archivist.logger.verbose("Spider", "Looking for next queued URL")
            url = self.spider.next_url(crawl_id)
            if url is None:
                self.archivist.finish_crawl(crawl_id, "finished")
                self.archivist.logger.info("Spider", "Crawl complete")
                return self.archivist.crawl_summary(crawl_id)

            self.archivist.logger.info("Spider", f"Visiting page {processed + 1}: {url}")
            self.spider.wait_for_next_request()
            result = self.fetcher.fetch(url)
            processed += 1

            if result.html is None:
                consecutive_failures += 1
                self.archivist.mark_page_failed(crawl_id, url, result.status_code, result.error or "fetch failed")
                if consecutive_failures >= self.max_consecutive_failures:
                    self.archivist.logger.info(
                        "Spider",
                        f"Stopping crawl after {consecutive_failures} consecutive failure(s)",
                    )
                    self.archivist.finish_crawl(crawl_id, "stopped_after_failures")
                    return self.archivist.crawl_summary(crawl_id)
                self.archivist.logger.info("Spider", "Continuing with next queued URL")
                continue

            consecutive_failures = 0
            archive_started = perf_counter()
            self.archivist.mark_page_visited(crawl_id, url, result.status_code, html_hash(result.html))
            self.archivist.logger.verbose(
                "Archivist",
                f"Stored page in {format_duration(perf_counter() - archive_started)}",
            )
            discover_started = perf_counter()
            self.spider.discover(crawl_id, result.html, url)
            self.archivist.logger.verbose(
                "Spider",
                f"Discovery completed in {format_duration(perf_counter() - discover_started)}",
            )
            extract_started = perf_counter()
            jobs = self.spider.extractor.jobs(result.html, url)
            self.archivist.logger.info(
                "Extractor",
                f"{len(jobs)} job(s) parsed in {format_duration(perf_counter() - extract_started)}",
            )
            archive_jobs_started = perf_counter()
            job_results = {"new": 0, "updated": 0, "unchanged": 0}
            for job in jobs:
                job_results[self.archivist.store_job(crawl_id, self.spider.source_id, job)] += 1
            if jobs:
                self.archivist.logger.info(
                    "Archivist",
                    (
                        f"{job_results['new']} inserted, {job_results['updated']} updated, "
                        f"{job_results['unchanged']} unchanged in "
                        f"{format_duration(perf_counter() - archive_jobs_started)}"
                    ),
                )
            self.archivist.logger.info("Spider", "Continuing with next queued URL")

        self.archivist.logger.info("Spider", f"Reached max page limit: {max_pages}")
        self.archivist.logger.info("Spider", "Crawl remains resumable")
        return self.archivist.crawl_summary(crawl_id)
