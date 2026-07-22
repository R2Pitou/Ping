from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO


@dataclass
class PingLogger:
    verbose_enabled: bool = False
    stream: TextIO = sys.stdout

    def info(self, subsystem: str, message: str) -> None:
        print(f"{subsystem:<10} {message}", file=self.stream)

    def verbose(self, subsystem: str, message: str) -> None:
        if self.verbose_enabled:
            self.info(subsystem, message)


class NullLogger(PingLogger):
    def __init__(self) -> None:
        super().__init__(verbose_enabled=False)

    def info(self, subsystem: str, message: str) -> None:
        return

    def verbose(self, subsystem: str, message: str) -> None:
        return


NULL_LOGGER = NullLogger()
