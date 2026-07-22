from __future__ import annotations

from time import perf_counter
from dataclasses import dataclass

from .archivist import Archivist
from .fetcher import Fetcher
from .hasher import html_hash
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
                return self.archivist.crawl_summary(crawl_id)

            self.archivist.logger.info("Spider", f"Visiting {url}")
            self.spider.wait_for_next_request()
            fetch_started = perf_counter()
            result = self.fetcher.fetch(url)
            self.archivist.logger.verbose(
                "Fetcher",
                f"Elapsed {perf_counter() - fetch_started:.3f} seconds",
            )
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
                f"Elapsed {perf_counter() - archive_started:.3f} seconds",
            )
            discover_started = perf_counter()
            self.spider.discover(crawl_id, result.html, url)
            self.archivist.logger.verbose(
                "Spider",
                f"Elapsed {perf_counter() - discover_started:.3f} seconds",
            )
            extract_started = perf_counter()
            jobs = self.spider.extractor.jobs(result.html, url)
            self.archivist.logger.verbose(
                "Extractor",
                f"Elapsed {perf_counter() - extract_started:.3f} seconds",
            )
            self.archivist.logger.info("Extractor", f"{len(jobs)} job(s) parsed")
            for job in jobs:
                self.archivist.store_job(crawl_id, self.spider.source_id, job)
            self.archivist.logger.info("Spider", "Continuing with next queued URL")

        self.archivist.logger.info("Spider", f"Reached max page limit: {max_pages}")
        self.archivist.logger.info("Spider", "Crawl remains resumable")
        return self.archivist.crawl_summary(crawl_id)
