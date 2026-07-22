from __future__ import annotations

import random
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .logging import NULL_LOGGER, PingLogger
from .models import FetchResult


TEMPORARY_STATUS_CODES = {429, 503, 504}


@dataclass
class Fetcher:
    user_agent: str = "Ping/0.1 respectful web spider"
    timeout_seconds: float = 20.0
    max_retries: int = 3
    backoff_base_seconds: float = 1.0
    jitter_seconds: float = 0.25
    logger: PingLogger = field(default_factory=lambda: NULL_LOGGER)

    def fetch(self, url: str) -> FetchResult:
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            self.logger.info("Fetcher", f"GET {url}")
            try:
                request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    body = response.read()
                    charset = response.headers.get_content_charset() or "utf-8"
                    html = body.decode(charset, errors="replace")
                    self.logger.info("Fetcher", f"HTTP {response.status} ({_format_size(len(body))})")
                    return FetchResult(url=url, status_code=response.status, html=html)
            except urllib.error.HTTPError as exc:
                if exc.code not in TEMPORARY_STATUS_CODES or attempt >= self.max_retries:
                    self.logger.info("Fetcher", f"HTTP {exc.code} {exc.reason}")
                    return FetchResult(url=url, status_code=exc.code, html=None, error=str(exc))
                self.logger.info("Fetcher", f"HTTP {exc.code} {exc.reason}")
                last_error = str(exc)
            except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
                if attempt >= self.max_retries:
                    self.logger.info("Fetcher", f"Request failed: {exc}")
                    return FetchResult(url=url, status_code=None, html=None, error=str(exc))
                self.logger.info("Fetcher", f"Request failed: {exc}")
                last_error = str(exc)

            self._sleep_before_retry(attempt)

        return FetchResult(url=url, status_code=None, html=None, error=last_error or "unknown fetch error")

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = self.backoff_base_seconds * (2**attempt)
        delay += random.uniform(0, self.jitter_seconds)
        self.logger.info("Fetcher", f"Retry {attempt + 1} of {self.max_retries}")
        self.logger.info("Fetcher", f"Waiting {delay:.1f} seconds")
        time.sleep(delay)


def _format_size(byte_count: int) -> str:
    if byte_count < 1024:
        return f"{byte_count} B"
    return f"{byte_count / 1024:.0f} KB"
