import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from fastapi import HTTPException


if "QWEN_TTS_DATA_DIR" not in os.environ:
    runtime = tempfile.TemporaryDirectory()
    os.environ["QWEN_TTS_DATA_DIR"] = runtime.name
    os.environ["QWEN_TTS_GPU_LOCK_FILE"] = str(Path(runtime.name) / "gpu-inference.lock")

fake_faster_whisper = types.ModuleType("faster_whisper")
fake_faster_whisper.WhisperModel = object
sys.modules.setdefault("faster_whisper", fake_faster_whisper)

from asr_service import choose_reference_segment


class ReferenceSegmentTest(unittest.TestCase):
    def test_prefers_confident_compact_segment(self):
        segments = [
            {
                "duration": 7.0,
                "text": "明瞭な音声",
                "avg_logprob": -0.15,
                "no_speech_prob": 0.01,
            },
            {
                "duration": 5.0,
                "text": "ノイズあり",
                "avg_logprob": -0.1,
                "no_speech_prob": 0.6,
            },
        ]
        self.assertEqual("明瞭な音声", choose_reference_segment(segments)["text"])

    def test_rejects_empty_transcription(self):
        with self.assertRaises(HTTPException):
            choose_reference_segment([])


if __name__ == "__main__":
    unittest.main()
