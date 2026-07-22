import tempfile
import unittest
from pathlib import Path

from ping import Ping, Rok, Sanya, Tra, Yok
from ping.models import JobRecord, Source
from ping.spider import Spider


class ComponentNameTests(unittest.TestCase):
    def test_named_components_preserve_descriptive_implementations(self) -> None:
        self.assertIs(Ping, Spider)
        self.assertTrue(callable(Yok().fetch))
        self.assertEqual(Tra.hash(JobRecord(source_identifier="job:1", title="Developer")), Tra.hash({"title": "Developer"}))

    def test_sanya_commits_and_rok_finds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sanya = Sanya(Path(tmp) / "ping.sqlite3")
            source_id = sanya.upsert_source(Source("test", "https://example.com", ("https://example.com",)))
            crawl_id = sanya.start_crawl(source_id, ("https://example.com",))
            sanya.commit(crawl_id, source_id, JobRecord(source_identifier="test:1", title="Developer", company="Acme"))
            results = Rok(sanya).find("Acme")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["title"], "Developer")
            sanya.close()


if __name__ == "__main__":
    unittest.main()
