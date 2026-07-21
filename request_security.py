"""Request-boundary helpers shared by the local UI and ASR service."""

from __future__ import annotations

import os
from urllib.parse import urlsplit


DEFAULT_ALLOWED_HOSTS = ("127.0.0.1", "localhost")


def configured_ui_hosts() -> list[str]:
    raw = os.getenv("QWEN_TTS_ALLOWED_HOSTS", "").strip()
    hosts = [host.strip().lower() for host in raw.split(",") if host.strip()]
    configured = hosts or list(DEFAULT_ALLOWED_HOSTS)
    if any("*" in host for host in configured):
        raise ValueError("QWEN_TTS_ALLOWED_HOSTS must contain exact hostnames, not wildcards")
    return configured


def is_same_origin_browser_request(
    origin: str | None, host: str | None, fetch_site: str | None
) -> bool:
    """Reject browser cross-site writes while allowing local non-browser clients."""
    if (fetch_site or "").lower() == "cross-site":
        return False
    if not origin:
        return True
    if not host:
        return False
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return False
    return parsed.netloc.lower() == host.lower()
