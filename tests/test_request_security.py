import os
import unittest
from unittest.mock import patch

from request_security import configured_ui_hosts, is_same_origin_browser_request


class RequestSecurityTest(unittest.TestCase):
    def test_rejects_wildcard_host_configuration(self):
        with patch.dict(os.environ, {"QWEN_TTS_ALLOWED_HOSTS": "*"}):
            with self.assertRaises(ValueError):
                configured_ui_hosts()

    def test_allows_same_origin_browser_write(self):
        self.assertTrue(
            is_same_origin_browser_request(
                "http://localhost:18001", "localhost:18001", "same-origin"
            )
        )

    def test_allows_non_browser_local_client_without_origin(self):
        self.assertTrue(is_same_origin_browser_request(None, "localhost:18001", None))

    def test_rejects_cross_site_and_mismatched_origins(self):
        self.assertFalse(
            is_same_origin_browser_request(
                "https://attacker.example", "localhost:18001", "cross-site"
            )
        )
        self.assertFalse(
            is_same_origin_browser_request(
                "https://attacker.example", "localhost:18001", "same-site"
            )
        )

    def test_rejects_opaque_or_credentialed_origins(self):
        self.assertFalse(is_same_origin_browser_request("null", "localhost", None))
        self.assertFalse(
            is_same_origin_browser_request(
                "https://user:pass@localhost", "localhost", "same-origin"
            )
        )


if __name__ == "__main__":
    unittest.main()
