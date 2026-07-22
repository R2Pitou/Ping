import tempfile
import unittest
from pathlib import Path

from ping.archivist import Archivist
from ping.models import JobRecord, Source


class ArchivistTests(unittest.TestCase):
    def test_append_only_revisions_for_meaningful_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archivist = Archivist(Path(tmp) / "ping.sqlite3")
            source_id = archivist.upsert_source(Source("bongthom", "https://example.com", ("https://example.com",)))
            crawl_id = archivist.start_crawl(source_id, ("https://example.com",))

            first = JobRecord(source_identifier="bongthom:1", title="Developer", company="Acme")
            same = JobRecord(source_identifier="bongthom:1", title=" Developer ", company="Acme")
            changed = JobRecord(source_identifier="bongthom:1", title="Senior Developer", company="Acme")

            self.assertEqual(archivist.store_job(crawl_id, source_id, first), "new")
            self.assertEqual(archivist.store_job(crawl_id, source_id, same), "unchanged")
            self.assertEqual(archivist.store_job(crawl_id, source_id, changed), "updated")

            revisions = archivist.connection.execute("SELECT COUNT(*) AS total FROM job_revisions").fetchone()
            jobs = archivist.connection.execute("SELECT COUNT(*) AS total FROM jobs").fetchone()
            self.assertEqual(jobs["total"], 1)
            self.assertEqual(revisions["total"], 2)
            archivist.close()


if __name__ == "__main__":
    unittest.main()
