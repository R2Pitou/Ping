import io
import unittest
from datetime import datetime

from ping.logging import PingLogger, format_duration


class LoggingTests(unittest.TestCase):
    def test_subsystem_label_is_aligned(self) -> None:
        stream = io.StringIO()
        logger = PingLogger(stream=stream, clock=lambda: datetime(2026, 1, 2, 9, 12, 18))

        logger.info("Spider", "Starting crawl: bongthom")

        self.assertEqual(stream.getvalue(), "09:12:18 Spider     Starting crawl: bongthom\n")

    def test_verbose_and_trace_messages_are_gated(self) -> None:
        stream = io.StringIO()
        logger = PingLogger(stream=stream, clock=lambda: datetime(2026, 1, 2, 9, 12, 18))

        logger.verbose("Archivist", "SQL transaction committed")
        logger.trace("Archivist", "SQL SELECT 1")
        self.assertEqual(stream.getvalue(), "")

        logger.level = "verbose"
        logger.verbose("Archivist", "SQL transaction committed")
        logger.trace("Archivist", "SQL SELECT 1")
        self.assertEqual(stream.getvalue(), "09:12:18 Archivist  SQL transaction committed\n")

        logger.level = "trace"
        logger.trace("Archivist", "SQL SELECT 1")
        self.assertEqual(
            stream.getvalue(),
            "09:12:18 Archivist  SQL transaction committed\n09:12:18 Archivist  SQL SELECT 1\n",
        )

    def test_duration_formatting(self) -> None:
        self.assertEqual(format_duration(0.412), "412 ms")
        self.assertEqual(format_duration(2.1), "2.1 s")

    def test_multiline_messages_get_timestamped_per_line(self) -> None:
        stream = io.StringIO()
        logger = PingLogger(stream=stream, clock=lambda: datetime(2026, 1, 2, 9, 12, 18))

        logger.info("Archivist", "SQL SELECT\nFROM jobs")

        self.assertEqual(
            stream.getvalue(),
            "09:12:18 Archivist  SQL SELECT\n09:12:18 Archivist  FROM jobs\n",
        )


if __name__ == "__main__":
    unittest.main()
