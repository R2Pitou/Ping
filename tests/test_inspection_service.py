import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from ping.archivist import Archivist
from ping.cli import main
from ping.inspection_service import ArchiveInspectionService
from ping.models import JobRecord, Source


class InspectionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "ping.sqlite3"
        self.sanya = Archivist(self.db_path)
        source_id = self.sanya.upsert_source(Source("test", "https://example.com", ("https://example.com",)))
        crawl_id = self.sanya.start_crawl(source_id, ("https://example.com",))
        self.sanya.store_job(
            crawl_id,
            source_id,
            JobRecord(source_identifier="test:1", title="Developer", company="Acme"),
        )

    def tearDown(self) -> None:
        self.sanya.close()
        self.tmp.cleanup()

    def test_companies_and_doctor_use_archive_evidence(self) -> None:
        service = ArchiveInspectionService(self.sanya)
        companies = service.companies()
        self.assertEqual(companies[0]["company"], "Acme")
        self.assertEqual(companies[0]["active_jobs"], 1)
        self.assertTrue(service.doctor().healthy)

    def test_alias_commands_expose_the_inspection_interface(self) -> None:
        for command, expected in [
            (["jobs"], "SOURCE IDENTIFIER"),
            (["show", "1"], "Current revision"),
            (["companies"], "Acme"),
            (["crawl-history"], "running"),
            (["revisions"], "Developer"),
            (["search", "Acme"], "Developer"),
            (["doctor"], "Integrity: ok"),
            (["dump", "jobs"], '"source_identifier": "test:1"'),
        ]:
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--db", str(self.db_path), *command]), 0)
            self.assertIn(expected, output.getvalue())


if __name__ == "__main__":
    unittest.main()
