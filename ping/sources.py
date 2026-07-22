from __future__ import annotations

import os

from .extractors import BongThomExtractor, Extractor
from .logging import NULL_LOGGER, PingLogger
from .models import Source


def configured_sources(logger: PingLogger = NULL_LOGGER) -> dict[str, tuple[Source, Extractor]]:
    bongthom_seed = os.environ.get("PING_BONGTHOM_SEED_URL", "https://www.bongthom.com/rss.xml")
    bongthom = Source(
        name="bongthom",
        base_url="https://www.bongthom.com/",
        seed_urls=(bongthom_seed,),
        enabled=True,
        crawl_delay_ms=int(os.environ.get("PING_BONGTHOM_CRAWL_DELAY_MS", "1500")),
    )
    return {"bongthom": (bongthom, BongThomExtractor(logger=logger))}
