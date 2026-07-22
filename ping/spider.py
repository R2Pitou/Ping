from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from .archivist import Archivist
from .extractors import Extractor
from .logging import NULL_LOGGER, PingLogger
from .models import Source


@dataclass
class Spider:
    archivist: Archivist
    source: Source
    source_id: int
    extractor: Extractor
    logger: PingLogger = field(default_factory=lambda: NULL_LOGGER)

    def start(self) -> int:
        self.logger.info("Spider", f"Starting crawl: {self.source.name}")
        return self.archivist.start_crawl(self.source_id, self.source.seed_urls)

    def crawl(self) -> int:
        """Begin a crawl.

        This is the small public verb used by the Ping facade; orchestration
        remains the responsibility of ``CrawlApplication``.
        """
        return self.start()

    def resume(self) -> int | None:
        self.logger.info("Spider", f"Resuming crawl: {self.source.name}")
        return self.archivist.resume_crawl(self.source_id)

    def next_url(self, crawl_id: int) -> str | None:
        return self.archivist.next_url(crawl_id)

    def discover(self, crawl_id: int, html: str, page_url: str) -> set[str]:
        links = self.extractor.links(html, page_url)
        self.logger.info("Spider", f"{len(links)} links discovered")
        for link in sorted(links):
            self.logger.trace("Spider", f"Discovered URL: {link}")
        queued_count = self.archivist.enqueue_many(crawl_id, links)
        self.logger.verbose("Spider", f"{queued_count} new URL(s) queued")
        return links

    def wait_for_next_request(self) -> None:
        base = self.source.crawl_delay_ms / 1000
        jitter = random.uniform(0, min(base, 0.5))
        delay = base + jitter
        self.logger.info("Spider", f"Sleeping {delay:.1f} s")
        time.sleep(delay)
