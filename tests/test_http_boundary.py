import logging
import sys
import types
import unittest
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from fastapi.testclient import TestClient

import app

fake_faster_whisper = types.ModuleType("faster_whisper")
fake_faster_whisper.WhisperModel = object
sys.modules.setdefault("faster_whisper", fake_faster_whisper)

import asr_service  # noqa: E402 - dependency stub must be installed first


class HttpBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app.app, base_url="http://localhost")
        cls.asr_client = TestClient(asr_service.app, base_url="http://localhost")

    def test_rejects_untrusted_host(self):
        response = self.client.post(
            "/api/synthesize", json={}, headers={"host": "attacker.example"}
        )
        self.assertEqual(400, response.status_code)

    def test_file_logs_open_lazily(self):
        for logger in (app.LOGGER, asr_service.LOGGER):
            handlers = [
                handler
                for handler in logger.handlers
                if isinstance(handler, logging.FileHandler)
            ]
            self.assertTrue(handlers)
            self.assertTrue(all(handler.delay for handler in handlers))

    def test_rejects_cross_site_browser_write(self):
        response = self.client.post(
            "/api/synthesize",
            json={},
            headers={
                "host": "localhost",
                "origin": "https://attacker.example",
                "sec-fetch-site": "cross-site",
            },
        )
        self.assertEqual(403, response.status_code)

    def test_allows_same_origin_request_to_reach_validation(self):
        response = self.client.post(
            "/api/synthesize",
            json={},
            headers={
                "host": "localhost",
                "origin": "http://localhost",
                "sec-fetch-site": "same-origin",
            },
        )
        self.assertEqual(422, response.status_code)

    def test_asr_rejects_cross_site_browser_write(self):
        response = self.asr_client.post(
            "/transcribe",
            headers={
                "host": "localhost",
                "origin": "https://attacker.example",
                "sec-fetch-site": "cross-site",
            },
        )
        self.assertEqual(403, response.status_code)


if __name__ == "__main__":
    unittest.main()
