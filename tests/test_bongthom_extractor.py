import unittest

from ping.extractors import BongThomExtractor


class BongThomExtractorTests(unittest.TestCase):
    def test_extracts_each_position_from_a_grouped_announcement(self) -> None:
        html = """
        <html><body>
          <h1 class="title">Various Positions</h1>
          <a class="clearfix sub-title">Australia Young Leaders Academy Co., LTD.</a>
          <div>BTDC-ID: <em>39416</em></div>
          <time datetime="2026-05-16">16-May-2026</time>
          <h3 id="position-47960">Frontend Developer</h3>
          <div id="job-detail-pos-47960">
            <a href="https://account.bongthom.com/apply_now?position=47960&amp;advertisement=39416">Apply Now</a>
            <ul><li>Location: Phnom Penh</li><li>Schedule: Full-time</li><li>Salary: Negotiable</li></ul>
            <p>Build accessible web applications.</p>
          </div>
          <h3 id="position-47961">Fullstack Developer</h3>
          <div id="job-detail-pos-47961">
            <a href="https://account.bongthom.com/apply_now?position=47961&amp;advertisement=39416">Apply Now</a>
            <ul><li>Location: Phnom Penh</li><li>Schedule: Full-time</li><li>Salary: Negotiable</li></ul>
            <p>Build full-stack applications.</p>
          </div>
        </body></html>
        """
        extractor = BongThomExtractor()

        jobs = extractor.jobs(html, "https://www.bongthom.com/job_detail/various_positions_39416.html")

        self.assertEqual([job.source_identifier for job in jobs], ["bongthom:39416:47960", "bongthom:39416:47961"])
        self.assertEqual(jobs[0].title, "Frontend Developer")
        self.assertEqual(jobs[0].company, "Australia Young Leaders Academy Co., LTD.")
        self.assertEqual(jobs[0].location, "Phnom Penh")
        self.assertEqual(jobs[0].employment_type, "Full-time")
        self.assertEqual(jobs[0].salary, "Negotiable")
        self.assertEqual(jobs[0].closing_date, "2026-05-16")
        self.assertIn("position=47960", jobs[0].application_url or "")

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

    def test_discovers_job_detail_urls_from_the_bongthom_rss_feed(self) -> None:
        rss = """
        <rss><channel>
          <link>https://www.bongthom.com/rss.xml</link>
          <item><link>https://www.bongthom.com/job_detail/teacher_40686.html</link></item>
          <item><link>https://www.bongthom.com/job_detail/view_detail_40683.html</link></item>
          <item><link>https://www.bongthom.com/blog/announcement_123.html</link></item>
        </channel></rss>
        """

        links = BongThomExtractor().links(rss, "https://www.bongthom.com/rss.xml")

        self.assertEqual(
            links,
            {
                "https://www.bongthom.com/job_detail/teacher_40686.html",
                "https://www.bongthom.com/job_detail/view_detail_40683.html",
            },
        )


if __name__ == "__main__":
    unittest.main()
