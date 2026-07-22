import unittest

from ping.extractors import BongThomExtractor


class BongThomExtractorTests(unittest.TestCase):
    def test_extracts_same_host_links_and_job_from_detail_page(self) -> None:
        html = """
        <html>
          <head>
            <title>Software Developer - BongThom</title>
            <meta name="description" content="Company: Acme Location: Phnom Penh Salary: Negotiable Closing Date: 2026-08-01">
          </head>
          <body>
            <a href="/job_detail/84722">same</a>
            <a href="https://other.example/job_detail/1">other</a>
          </body>
        </html>
        """
        extractor = BongThomExtractor()

        links = extractor.links(html, "https://www.bongthom.com/jobs")
        jobs = extractor.jobs(html, "https://www.bongthom.com/job_detail/84722")

        self.assertEqual(links, {"https://www.bongthom.com/job_detail/84722"})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source_identifier, "bongthom:84722")
        self.assertEqual(jobs[0].title, "Software Developer")
        self.assertEqual(jobs[0].company, "Acme")
        self.assertEqual(jobs[0].location, "Phnom Penh")


if __name__ == "__main__":
    unittest.main()
