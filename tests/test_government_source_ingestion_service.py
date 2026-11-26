import unittest

from services.government_source_ingestion_service import (
    GovernmentSourceIngestionService,
    _PageTextParser,
)


class GovernmentSourceIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GovernmentSourceIngestionService(
            approved_urls=("https://www.gov.za", "https://www.dpsa.gov.za"),
        )
        self.addCleanup(self.service.close)

    def test_only_approved_https_hosts_are_allowed(self) -> None:
        self.service._validate_approved_url("https://www.gov.za/documents")
        self.service._validate_approved_url("https://dpsa.gov.za/circulars")

        with self.assertRaises(ValueError):
            self.service._validate_approved_url("https://example.com/policy")
        with self.assertRaises(ValueError):
            self.service._validate_approved_url("http://www.gov.za/policy")

    def test_html_extraction_ignores_navigation_and_scripts(self) -> None:
        parser = _PageTextParser()
        parser.feed(
            "<html><head><title>Public Service Regulations</title>"
            "<script>ignored script</script></head><body>"
            "<nav>ignored navigation</nav><main><h1>Leave rules</h1>"
            "<p>Annual leave provisions.</p></main></body></html>"
        )

        title, text = parser.result()

        self.assertEqual(title, "Public Service Regulations")
        self.assertIn("Leave rules", text)
        self.assertIn("Annual leave provisions.", text)
        self.assertNotIn("ignored navigation", text)
        self.assertNotIn("ignored script", text)


if __name__ == "__main__":
    unittest.main()
