import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException


RUNTIME = tempfile.TemporaryDirectory()
os.environ["QWEN_TTS_DATA_DIR"] = RUNTIME.name
os.environ["QWEN_TTS_GPU_LOCK_FILE"] = str(Path(RUNTIME.name) / "gpu-inference.lock")

import app


class AppHelpersTest(unittest.TestCase):
    def test_clean_text_collapses_whitespace(self):
        self.assertEqual("你好 世界", app.clean_text("  你好\n  世界  "))

    def test_validate_reference_upload_rejects_unsupported_and_empty_files(self):
        with self.assertRaises(HTTPException):
            app.validate_reference_upload("reference.m4a", b"audio")
        with self.assertRaises(HTTPException):
            app.validate_reference_upload("reference.wav", b"")

    def test_consent_audit_omits_original_filename_and_text(self):
        app.record_clone_consent("speaker-private-name.wav", b"audio", "参考原文", "目标文案")

        record = json.loads(app.AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(".wav", record["reference_suffix"])
        self.assertNotIn("reference_filename", record)
        self.assertNotIn("speaker-private-name", json.dumps(record, ensure_ascii=False))
        self.assertNotIn("参考原文", json.dumps(record, ensure_ascii=False))
        self.assertNotIn("目标文案", json.dumps(record, ensure_ascii=False))

    def test_health_does_not_disclose_backend_addresses(self):
        payload = app.health()
        self.assertEqual("ok", payload["status"])
        self.assertNotIn("backend", payload)
        self.assertNotIn("base_backend", payload)
        self.assertNotIn("asr_backend", payload)


if __name__ == "__main__":
    unittest.main()
