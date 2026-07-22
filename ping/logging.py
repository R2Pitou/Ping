from __future__ import annotations

import sys
from datetime import datetime
from time import perf_counter
from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Callable, Iterator
from typing import TextIO


LOG_LEVELS = {"normal": 0, "verbose": 1, "trace": 2}


@dataclass
class PingLogger:
    level: str = "normal"
    stream: TextIO = sys.stdout
    clock: Callable[[], datetime] = datetime.now

    def __post_init__(self) -> None:
        if self.level not in LOG_LEVELS:
            raise ValueError(f"Unknown log level: {self.level}")

    @property
    def trace_enabled(self) -> bool:
        return self._enabled("trace")

    def normal(self, subsystem: str, message: str) -> None:
        self._log("normal", subsystem, message)

    def info(self, subsystem: str, message: str) -> None:
        self.normal(subsystem, message)

    def verbose(self, subsystem: str, message: str) -> None:
        self._log("verbose", subsystem, message)

    def trace(self, subsystem: str, message: str) -> None:
        self._log("trace", subsystem, message)

    @contextmanager
    def timer(self, level: str, subsystem: str, message: str) -> Iterator[None]:
        started = perf_counter()
        try:
            yield
        finally:
            elapsed = perf_counter() - started
            self._log(level, subsystem, f"{message} in {format_duration(elapsed)}")

    def _log(self, level: str, subsystem: str, message: str) -> None:
        if self._enabled(level):
            timestamp = self.clock().strftime("%H:%M:%S")
            for line in str(message).splitlines() or [""]:
                print(f"{timestamp} {subsystem:<10} {line}", file=self.stream)

    def _enabled(self, level: str) -> bool:
        return LOG_LEVELS[self.level] >= LOG_LEVELS[level]


class NullLogger(PingLogger):
    def __init__(self) -> None:
        super().__init__(level="normal")

    def info(self, subsystem: str, message: str) -> None:
        return

    def normal(self, subsystem: str, message: str) -> None:
        return

    def verbose(self, subsystem: str, message: str) -> None:
        return

    def trace(self, subsystem: str, message: str) -> None:
        return


NULL_LOGGER = NullLogger()


def format_duration(seconds: float) -> str:
    milliseconds = seconds * 1000
    if milliseconds < 1000:
        return f"{milliseconds:.0f} ms"
    return f"{seconds:.1f} s"
