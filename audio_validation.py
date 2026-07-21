"""Small, dependency-free checks for supported uploaded audio containers."""

from __future__ import annotations


def detect_audio_suffix(content: bytes) -> str | None:
    """Return the detected supported suffix, or ``None`` for unknown content.

    These checks validate the container header before an upload reaches SoX,
    Whisper, or another decoder. They intentionally do not claim that every
    frame in the file is decodable; the downstream decoder remains the final
    authority.
    """
    if _is_wave(content):
        return ".wav"
    if _is_flac(content):
        return ".flac"
    if _is_ogg_audio(content):
        return ".ogg"
    if _is_mp3(content):
        return ".mp3"
    return None


def _is_wave(content: bytes) -> bool:
    return (
        len(content) >= 12
        and content[:4] == b"RIFF"
        and content[8:12] == b"WAVE"
    )


def _is_flac(content: bytes) -> bool:
    if len(content) < 42 or content[:4] != b"fLaC":
        return False
    metadata_header = content[4:8]
    block_type = metadata_header[0] & 0x7F
    block_length = int.from_bytes(metadata_header[1:4], "big")
    return block_type == 0 and block_length == 34


def _is_ogg_audio(content: bytes) -> bool:
    if len(content) < 28 or content[:5] != b"OggS\x00":
        return False
    segment_count = content[26]
    segment_table_end = 27 + segment_count
    if segment_count == 0 or len(content) < segment_table_end:
        return False
    first_packet_length = sum(content[27:segment_table_end])
    first_packet_end = segment_table_end + first_packet_length
    if len(content) < first_packet_end:
        return False
    first_packet = content[segment_table_end:first_packet_end]
    return first_packet.startswith(
        (b"\x01vorbis", b"OpusHead", b"\x7fFLAC", b"Speex   ")
    )


def _is_mp3(content: bytes) -> bool:
    offset = 0
    if content.startswith(b"ID3"):
        if len(content) < 10 or any(byte & 0x80 for byte in content[6:10]):
            return False
        tag_size = (
            (content[6] << 21)
            | (content[7] << 14)
            | (content[8] << 7)
            | content[9]
        )
        footer_size = 10 if content[5] & 0x10 else 0
        offset = 10 + tag_size + footer_size
    if len(content) < offset + 4:
        return False
    header = int.from_bytes(content[offset : offset + 4], "big")
    version = (header >> 19) & 0b11
    layer = (header >> 17) & 0b11
    bitrate_index = (header >> 12) & 0b1111
    sample_rate_index = (header >> 10) & 0b11
    emphasis = header & 0b11
    return (
        header & 0xFFE00000 == 0xFFE00000
        and version != 0b01
        and layer != 0b00
        and bitrate_index not in (0, 0b1111)
        and sample_rate_index != 0b11
        and emphasis != 0b10
    )
