import io
import unittest
import wave

from audio_validation import detect_audio_suffix


def make_wave() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\x00\x00" * 160)
    return output.getvalue()


class AudioValidationTest(unittest.TestCase):
    def test_detects_real_wave_container(self):
        self.assertEqual(".wav", detect_audio_suffix(make_wave()))

    def test_detects_supported_container_headers(self):
        flac = b"fLaC" + b"\x80\x00\x00\x22" + (b"\x00" * 34)
        ogg_vorbis = (
            b"OggS\x00"
            + (b"\x00" * 21)
            + b"\x01"
            + b"\x07"
            + b"\x01vorbis"
        )
        mp3 = bytes.fromhex("FF FB 90 00") + (b"\x00" * 32)

        self.assertEqual(".flac", detect_audio_suffix(flac))
        self.assertEqual(".ogg", detect_audio_suffix(ogg_vorbis))
        self.assertEqual(".mp3", detect_audio_suffix(mp3))

    def test_detects_supported_ogg_audio_codecs(self):
        for packet_header in (b"\x01vorbis", b"OpusHead", b"\x7fFLAC", b"Speex   "):
            ogg = (
                b"OggS\x00"
                + (b"\x00" * 21)
                + b"\x01"
                + bytes([len(packet_header)])
                + packet_header
            )
            with self.subTest(packet_header=packet_header):
                self.assertEqual(".ogg", detect_audio_suffix(ogg))

    def test_rejects_text_and_incomplete_headers(self):
        self.assertIsNone(detect_audio_suffix(b"<html>not audio</html>"))
        self.assertIsNone(detect_audio_suffix(b"RIFF\x00\x00\x00\x00"))
        self.assertIsNone(detect_audio_suffix(b"ID3\x04\x00\x00\x00\x00\x00\x00"))


if __name__ == "__main__":
    unittest.main()
