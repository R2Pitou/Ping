import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ping.archivist import Archivist
from ping.cli import main
from ping.models import JobRecord, Source


class InspectionTests(unittest.TestCase):
    def test_cli_lists_and_shows_sanya_records_without_sql(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "ping.sqlite3"
            archivist = Archivist(db_path)
            source_id = archivist.upsert_source(Source("test", "https://example.com", ("https://example.com",)))
            crawl_id = archivist.start_crawl(source_id, ("https://example.com",))
            archivist.store_job(crawl_id, source_id, JobRecord(source_identifier="test:1", title="Developer", company="Acme"))
            archivist.close()

            listed = io.StringIO()
            with redirect_stdout(listed):
                self.assertEqual(main(["--db", str(db_path), "inspect", "jobs"]), 0)
            self.assertIn("1", listed.getvalue())
            self.assertIn("SOURCE IDENTIFIER", listed.getvalue())
            self.assertIn("test:1", listed.getvalue())

            detailed = io.StringIO()
            with redirect_stdout(detailed):
                self.assertEqual(main(["--db", str(db_path), "inspect", "jobs", "--id", "1"]), 0)
            self.assertIn("Job #1", detailed.getvalue())
            self.assertIn("Source identifier: test:1", detailed.getvalue())
            self.assertIn("Current revision", detailed.getvalue())
            self.assertIn("Title: Developer", detailed.getvalue())
