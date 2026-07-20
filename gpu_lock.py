"""A process-shared lock for the single local GPU inference queue."""

from __future__ import annotations

import os
from pathlib import Path

from filelock import FileLock
from dotenv import load_dotenv


MODULE_ROOT = Path(__file__).resolve().parent
load_dotenv(MODULE_ROOT / ".env")


def get_gpu_lock(root: Path) -> FileLock:
    configured = os.getenv("QWEN_TTS_GPU_LOCK_FILE", "").strip()
    lock_path = Path(configured).expanduser() if configured else root / ".runtime" / "gpu-inference.lock"
    if not lock_path.is_absolute():
        lock_path = root / lock_path
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    timeout = float(os.getenv("QWEN_TTS_GPU_LOCK_TIMEOUT_SECONDS", "900"))
    return FileLock(str(lock_path), timeout=timeout)
