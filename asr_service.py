"""Local-only Japanese ASR service used by the Qwen voice workbench."""

from __future__ import annotations

import logging
import os
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from filelock import Timeout
from faster_whisper import WhisperModel
from dotenv import load_dotenv
from gpu_lock import get_gpu_lock
from starlette.middleware.trustedhost import TrustedHostMiddleware

from audio_validation import detect_audio_suffix
from request_security import DEFAULT_ALLOWED_HOSTS, is_same_origin_browser_request


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def configured_path(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    candidate = Path(raw).expanduser() if raw else default
    return candidate if candidate.is_absolute() else ROOT / candidate


DATA_ROOT = configured_path("QWEN_TTS_DATA_DIR", ROOT / ".runtime")
UPLOADS = DATA_ROOT / "asr-uploads"
MODEL_NAME = os.getenv("ASR_MODEL", "large-v3-turbo")
MODEL_CACHE = str(configured_path("ASR_MODEL_CACHE", DATA_ROOT / "asr-cache"))
MODEL_DEVICE = os.getenv("ASR_DEVICE", "cuda")
MODEL_COMPUTE_TYPE = os.getenv("ASR_COMPUTE_TYPE", "float16")
MAX_AUDIO_BYTES = int(os.getenv("QWEN_TTS_MAX_REFERENCE_AUDIO_BYTES", str(30 * 1024 * 1024)))
ALLOWED_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg"}
MODEL_LOCK = threading.Lock()
GPU_LOCK = get_gpu_lock(ROOT)
MODEL: WhisperModel | None = None

LOGGER = logging.getLogger("qwen_tts_asr")
if not LOGGER.handlers:
    LOGGER.setLevel(logging.INFO)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(DATA_ROOT / "asr_service.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)

UPLOADS.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="本地日语转写", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(DEFAULT_ALLOWED_HOSTS))


@app.middleware("http")
async def reject_cross_site_writes(request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not is_same_origin_browser_request(
        request.headers.get("origin"),
        request.headers.get("host"),
        request.headers.get("sec-fetch-site"),
    ):
        return JSONResponse(status_code=403, content={"detail": "拒绝跨站请求。"})
    return await call_next(request)


def get_model() -> WhisperModel:
    global MODEL
    with MODEL_LOCK:
        if MODEL is None:
            LOGGER.info("Loading ASR model: %s", MODEL_NAME)
            MODEL = WhisperModel(
                MODEL_NAME,
                device=MODEL_DEVICE,
                compute_type=MODEL_COMPUTE_TYPE,
                download_root=MODEL_CACHE,
            )
            LOGGER.info("ASR model loaded")
    return MODEL


def choose_reference_segment(segments: list[dict[str, object]]) -> dict[str, object]:
    """Prefer a compact, confident utterance suitable for a clone prompt."""
    candidates = [
        segment
        for segment in segments
        if 2.5 <= float(segment["duration"]) <= 12.0 and str(segment["text"]).strip()
    ]
    if not candidates:
        candidates = [segment for segment in segments if str(segment["text"]).strip()]
    if not candidates:
        raise HTTPException(status_code=422, detail="没有识别到可用的日语语音片段。")

    def score(segment: dict[str, object]) -> tuple[float, float, float]:
        duration = float(segment["duration"])
        confidence = float(segment["avg_logprob"])
        silence = float(segment["no_speech_prob"])
        return (confidence - silence, -abs(duration - 7.0), duration)

    return max(candidates, key=score)


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "model": MODEL_NAME, "loaded": MODEL is not None}


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...), language: str = Form("ja")
) -> dict[str, object]:
    suffix = Path(audio.filename or "reference.wav").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=422, detail="仅支持 WAV、MP3、FLAC 或 OGG 录音。")
    content = await audio.read(MAX_AUDIO_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="录音为空，请重新选择文件。")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=422, detail="录音请控制在 30MB 以内。")
    detected_suffix = detect_audio_suffix(content)
    if detected_suffix is None:
        raise HTTPException(status_code=422, detail="无法识别录音格式，请上传有效的音频文件。")
    if detected_suffix != suffix:
        raise HTTPException(status_code=422, detail="录音内容与文件扩展名不一致，请重新导出后上传。")

    temporary = UPLOADS / f"asr-{uuid.uuid4().hex}{suffix}"
    try:
        temporary.write_bytes(content)
        try:
            try:
                with GPU_LOCK:
                    segments, info = get_model().transcribe(
                        str(temporary),
                        language=language,
                        task="transcribe",
                        beam_size=5,
                        vad_filter=True,
                        condition_on_previous_text=False,
                    )
            except Timeout as error:
                raise HTTPException(status_code=503, detail="GPU 正在处理其他语音请求，请稍后重试。") from error
            items = [
                {
                    "start": round(float(segment.start), 3),
                    "end": round(float(segment.end), 3),
                    "duration": round(float(segment.end - segment.start), 3),
                    "text": segment.text.strip(),
                    "avg_logprob": round(float(segment.avg_logprob), 4),
                    "no_speech_prob": round(float(segment.no_speech_prob), 4),
                }
                for segment in segments
            ]
        except HTTPException:
            raise
        except Exception as error:
            LOGGER.exception("Japanese ASR failed (suffix=%s).", suffix)
            raise HTTPException(status_code=503, detail="日语自动转写暂时不可用，请稍后重试。") from error

        best = dict(choose_reference_segment(items))
        best["clip_duration"] = round(min(float(best["duration"]), 10.0), 3)
        return {
            "language": getattr(info, "language", language),
            "duration": round(float(getattr(info, "duration", 0.0)), 3),
            "best_segment": best,
            "segment_count": len(items),
        }
    finally:
        temporary.unlink(missing_ok=True)
