import io
import unittest

from ping.logging import PingLogger


class LoggingTests(unittest.TestCase):
    def test_subsystem_label_is_aligned(self) -> None:
        stream = io.StringIO()
        logger = PingLogger(stream=stream)

        logger.info("Spider", "Starting crawl: bongthom")

        self.assertEqual(stream.getvalue(), "Spider     Starting crawl: bongthom\n")

    def test_verbose_messages_are_gated(self) -> None:
        stream = io.StringIO()
        logger = PingLogger(stream=stream)

        logger.verbose("Archivist", "SQL transaction committed")
        self.assertEqual(stream.getvalue(), "")

        logger.verbose_enabled = True
        logger.verbose("Archivist", "SQL transaction committed")
        self.assertEqual(stream.getvalue(), "Archivist  SQL transaction committed\n")


if __name__ == "__main__":
    unittest.main()
