"""A constrained, Chinese-first control surface for the local Qwen3-TTS demo."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import httpx
from filelock import Timeout
from gradio_client import Client, handle_file
from dotenv import load_dotenv
from gpu_lock import get_gpu_lock
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def configured_path(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    candidate = Path(raw).expanduser() if raw else default
    return candidate if candidate.is_absolute() else ROOT / candidate


def find_sox_binary() -> Path | None:
    configured = os.getenv("QWEN_TTS_SOX_BINARY", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if candidate.is_absolute() else ROOT / candidate
    discovered = shutil.which("sox")
    return Path(discovered) if discovered else None


APP_VERSION = "0.1.0-alpha.1"
DATA_ROOT = configured_path("QWEN_TTS_DATA_DIR", ROOT / ".runtime")
OUTPUTS = DATA_ROOT / "outputs"
PREVIEWS = OUTPUTS / "previews"
UPLOADS = DATA_ROOT / "uploads"
AUDIT_LOG = DATA_ROOT / "clone_consent_audit.jsonl"
BACKEND_URL = os.getenv("QWEN_TTS_BACKEND_URL", "http://127.0.0.1:18000")
BASE_BACKEND_URL = os.getenv("QWEN_TTS_BASE_BACKEND_URL", "http://127.0.0.1:18002")
ASR_BACKEND_URL = os.getenv("QWEN_TTS_ASR_BACKEND_URL", "http://127.0.0.1:18003")
SOX_BINARY = find_sox_binary()
MAX_TEXT_LENGTH = int(os.getenv("QWEN_TTS_MAX_TEXT_LENGTH", "800"))
MAX_REFERENCE_AUDIO_BYTES = int(os.getenv("QWEN_TTS_MAX_REFERENCE_AUDIO_BYTES", str(30 * 1024 * 1024)))
OUTPUT_RETENTION_SECONDS = int(os.getenv("QWEN_TTS_OUTPUT_RETENTION_SECONDS", str(24 * 60 * 60)))
ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg"}
GENERATION_LOCK = threading.Lock()
GPU_LOCK = get_gpu_lock(ROOT)

DATA_ROOT.mkdir(parents=True, exist_ok=True)
LOGGER = logging.getLogger("qwen_tts_simple_ui")
if not LOGGER.handlers:
    LOGGER.setLevel(logging.INFO)
    handler = logging.FileHandler(DATA_ROOT / "clone_service.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)

# A local service must never be sent through a stale corporate proxy.
for proxy_name in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
):
    os.environ.pop(proxy_name, None)
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

VOICE_OPTIONS = {
    "Vivian": {"label": "Vivian", "note": "推荐试听"},
    "Serena": {"label": "Serena", "note": "推荐试听"},
    "Ryan": {"label": "Ryan", "note": "推荐试听"},
    "Uncle Fu": {"label": "Uncle Fu", "note": "推荐试听"},
    "Aiden": {"label": "Aiden", "note": "更多声音"},
    "Eric": {"label": "Eric", "note": "更多声音"},
    "Dylan": {"label": "Dylan", "note": "更多声音"},
    "Ono Anna": {"label": "Ono Anna", "note": "更多声音"},
    "Sohee": {"label": "Sohee", "note": "更多声音"},
}

STYLE_PRESETS = {
    "natural": ("自然", "自然、亲切、吐字清晰，停顿自然。"),
    "soft_cute": (
        "柔萌女声",
        "声音柔和、轻快，带一点自然可爱的俏皮感，但不过度夸张；保持成年女性普通话自然、清晰，不模仿任何具体人物。",
    ),
    "gentle": ("温柔", "温柔、放松、语气亲切，像在耐心交流。"),
    "broadcast": ("专业播报", "稳重、专业、吐字清晰，适合资讯播报。"),
    "story": ("讲故事", "生动、有叙事感，语气有适度起伏，停顿自然。"),
    "lively": ("活泼", "轻快、有活力，语调明亮但不过度夸张。"),
}

SPEED_PRESETS = {
    "slow": ("慢", "语速略慢，重要内容之间留出自然停顿。"),
    "normal": ("正常", "语速自然、节奏均衡。"),
    "fast": ("快", "语速略快，但每个字都要清晰可辨。"),
}


class SynthesisRequest(BaseModel):
    text: str
    voice: str = "Vivian"
    style: str = "natural"
    speed: str = "normal"


class PreviewRequest(BaseModel):
    voice: str


app = FastAPI(title="本地语音台", version=APP_VERSION, docs_url=None, redoc_url=None)
OUTPUTS.mkdir(parents=True, exist_ok=True)
PREVIEWS.mkdir(parents=True, exist_ok=True)
UPLOADS.mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=OUTPUTS), name="audio")


def clean_text(value: str) -> str:
    return " ".join(value.strip().split())


def validate_choice(value: str, choices: dict[str, object], field: str) -> str:
    if value not in choices:
        raise HTTPException(status_code=422, detail=f"不支持的{field}选项。")
    return value


def remove_expired_outputs() -> None:
    cutoff = time.time() - OUTPUT_RETENTION_SECONDS
    for candidate in OUTPUTS.glob("*.wav"):
        try:
            if candidate.stat().st_mtime < cutoff:
                candidate.unlink()
        except FileNotFoundError:
            continue


def generate_audio(text: str, voice: str, style: str, speed: str, destination: Path) -> None:
    instruction = f"请使用中文普通话。{STYLE_PRESETS[style][1]}{SPEED_PRESETS[speed][1]}"
    try:
        with GPU_LOCK, GENERATION_LOCK:
            try:
                client = Client(BACKEND_URL)
                source_path, status = client.predict(
                    text,
                    "Chinese",
                    voice,
                    instruction,
                    api_name="/run_instruct",
                )
            except Exception as error:  # Gradio exposes backend errors as different exception types.
                raise HTTPException(status_code=503, detail="语音服务暂时不可用，请稍后重试。") from error
    except Timeout as error:
        raise HTTPException(status_code=503, detail="GPU 正在处理其他语音请求，请稍后重试。") from error

    if not source_path or "Finished" not in str(status):
        raise HTTPException(status_code=502, detail="语音生成未完成，请重试。")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination)
    if not destination.is_file() or destination.stat().st_size <= 44:
        raise HTTPException(status_code=502, detail="生成结果为空，请重试。")
    LOGGER.info("Saved generated audio (name=%s bytes=%s).", destination.name, destination.stat().st_size)


def generate_clone_audio(
    text: str,
    reference_audio: Path,
    reference_text: str,
    destination: Path,
    *,
    x_vector_only: bool = False,
) -> None:
    """Generate Chinese speech from an explicitly authorized reference recording."""
    try:
        with GPU_LOCK, GENERATION_LOCK:
            try:
                client = Client(BASE_BACKEND_URL)
                source_path, status = client.predict(
                    handle_file(str(reference_audio)),
                    reference_text,
                    x_vector_only,
                    text,
                    "Chinese",
                    api_name="/run_voice_clone",
                )
            except Exception as error:
                LOGGER.exception(
                    "Clone backend request failed (reference_suffix=%s).", reference_audio.suffix
                )
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "授权声线服务不可用，或参考录音无法解析。请使用 WAV 或 MP3 "
                        "（建议 16-bit 单声道 WAV）后重试。"
                    ),
                ) from error
    except Timeout as error:
        raise HTTPException(status_code=503, detail="GPU 正在处理其他语音请求，请稍后重试。") from error

    if not source_path or "Finished" not in str(status):
        raise HTTPException(status_code=502, detail="授权声线生成未完成，请重试。")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination)
    if not destination.is_file() or destination.stat().st_size <= 44:
        raise HTTPException(status_code=502, detail="授权声线生成结果为空，请重试。")
    LOGGER.info("Saved cloned audio (name=%s bytes=%s).", destination.name, destination.stat().st_size)


def transcribe_japanese(reference_audio: Path) -> dict[str, object]:
    """Send an authorized temporary recording to the local-only ASR service."""
    try:
        with reference_audio.open("rb") as source, httpx.Client(timeout=600.0) as client:
            response = client.post(
                f"{ASR_BACKEND_URL}/transcribe",
                data={"language": "ja"},
                files={"audio": (reference_audio.name, source, "application/octet-stream")},
            )
        payload = response.json()
        if not response.is_success:
            raise HTTPException(
                status_code=503,
                detail=payload.get("detail", "日语自动转写暂时不可用，请稍后重试。"),
            )
        return payload
    except HTTPException:
        raise
    except Exception as error:
        LOGGER.exception("Japanese ASR request failed (reference_suffix=%s).", reference_audio.suffix)
        raise HTTPException(status_code=503, detail="日语自动转写暂时不可用，请稍后重试。") from error


def extract_reference_clip(
    reference_audio: Path, start: float, duration: float, destination: Path
) -> None:
    if SOX_BINARY is None or not SOX_BINARY.is_file():
        raise HTTPException(status_code=503, detail="参考录音处理服务暂时不可用，请稍后重试。")
    try:
        subprocess.run(
            [
                str(SOX_BINARY),
                str(reference_audio),
                str(destination),
                "trim",
                f"{start:.3f}",
                f"{duration:.3f}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as error:
        LOGGER.exception("Reference clip extraction failed (suffix=%s).", reference_audio.suffix)
        raise HTTPException(status_code=422, detail="无法从录音中提取清晰片段，请改用 WAV 或 MP3。") from error


def validate_reference_upload(
    filename: str | None, content: bytes
) -> tuple[str, str]:
    original_name = Path(filename or "reference.wav").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise HTTPException(
            status_code=422,
            detail="请上传 WAV、MP3、FLAC 或 OGG 格式的录音；M4A 请先导出为 WAV。",
        )
    if not content:
        raise HTTPException(status_code=422, detail="参考录音为空，请重新选择文件。")
    if len(content) > MAX_REFERENCE_AUDIO_BYTES:
        raise HTTPException(status_code=422, detail="参考录音请控制在 30MB 以内。")
    return original_name, suffix


def digest(value: bytes | str) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def record_clone_consent(
    filename: str, audio_content: bytes, reference_text: str, target_text: str
) -> None:
    """Store minimal proof of explicit consent without retaining source audio or text."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reference_suffix": Path(filename).suffix.lower(),
        "reference_audio_sha256": digest(audio_content),
        "reference_text_sha256": digest(reference_text),
        "target_text_sha256": digest(target_text),
        "consent_confirmed": True,
    }
    with AUDIT_LOG.open("a", encoding="utf-8") as audit:
        audit.write(json.dumps(record, ensure_ascii=False) + "\n")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": APP_VERSION,
    }


@app.post("/api/synthesize")
def synthesize(request: SynthesisRequest) -> dict[str, str]:
    text = clean_text(request.text)
    if not text:
        raise HTTPException(status_code=422, detail="请先输入需要朗读的文案。")
    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=422, detail=f"单次文案请控制在 {MAX_TEXT_LENGTH} 字以内。")

    voice = validate_choice(request.voice, VOICE_OPTIONS, "声音")
    style = validate_choice(request.style, STYLE_PRESETS, "风格")
    speed = validate_choice(request.speed, SPEED_PRESETS, "语速")
    remove_expired_outputs()

    filename = f"speech-{uuid.uuid4().hex}.wav"
    generate_audio(text, voice, style, speed, OUTPUTS / filename)
    return {"audio_url": f"/audio/{filename}", "message": "语音已生成"}


@app.post("/api/preview")
def preview(request: PreviewRequest) -> dict[str, str]:
    voice = validate_choice(request.voice, VOICE_OPTIONS, "声音")
    filename = f"{voice.lower().replace(' ', '-')}.wav"
    destination = PREVIEWS / filename
    if not destination.exists():
        generate_audio(
            "你好，这是本地语音台的声音试听。请选择你喜欢的表达方式。",
            voice,
            "natural",
            "normal",
            destination,
        )
    return {"audio_url": f"/audio/previews/{filename}", "message": f"{voice} 试听已准备好"}


@app.post("/api/clone")
async def clone_voice(
    text: str = Form(...),
    reference_text: str = Form(...),
    consent: bool = Form(False),
    reference_audio: UploadFile = File(...),
) -> dict[str, str]:
    target_text = clean_text(text)
    transcript = clean_text(reference_text)
    if not target_text:
        raise HTTPException(status_code=422, detail="请先输入需要朗读的中文文案。")
    if len(target_text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=422, detail=f"单次文案请控制在 {MAX_TEXT_LENGTH} 字以内。")
    if not transcript:
        raise HTTPException(status_code=422, detail="请填写参考录音对应的原文。")
    if not consent:
        raise HTTPException(status_code=422, detail="请先确认你拥有该参考声音的明确授权。")

    audio_content = await reference_audio.read(MAX_REFERENCE_AUDIO_BYTES + 1)
    original_name, suffix = validate_reference_upload(reference_audio.filename, audio_content)

    remove_expired_outputs()
    upload_path = UPLOADS / f"reference-{uuid.uuid4().hex}{suffix}"
    filename = f"clone-{uuid.uuid4().hex}.wav"
    try:
        upload_path.write_bytes(audio_content)
        record_clone_consent(original_name, audio_content, transcript, target_text)
        generate_clone_audio(target_text, upload_path, transcript, OUTPUTS / filename)
    finally:
        upload_path.unlink(missing_ok=True)

    return {"audio_url": f"/audio/{filename}", "message": "授权声线语音已生成"}


@app.post("/api/auto-clone")
async def auto_clone_voice(
    text: str = Form(...),
    consent: bool = Form(False),
    reference_audio: UploadFile = File(...),
) -> dict[str, object]:
    """Automatic Japanese-ASR + x-vector clone path for Japanese-to-Chinese."""
    target_text = clean_text(text)
    if not target_text:
        raise HTTPException(status_code=422, detail="请先输入需要朗读的中文文案。")
    if len(target_text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=422, detail=f"单次文案请控制在 {MAX_TEXT_LENGTH} 字以内。")
    if not consent:
        raise HTTPException(status_code=422, detail="请先确认你拥有该参考声音的明确授权。")

    audio_content = await reference_audio.read(MAX_REFERENCE_AUDIO_BYTES + 1)
    original_name, suffix = validate_reference_upload(reference_audio.filename, audio_content)
    remove_expired_outputs()

    upload_path = UPLOADS / f"reference-{uuid.uuid4().hex}{suffix}"
    clip_path = UPLOADS / f"clip-{uuid.uuid4().hex}.wav"
    filename = f"clone-{uuid.uuid4().hex}.wav"
    try:
        upload_path.write_bytes(audio_content)
        asr_result = transcribe_japanese(upload_path)
        best = asr_result.get("best_segment")
        if not isinstance(best, dict):
            raise HTTPException(status_code=502, detail="日语转写未返回可用片段，请换一段更清晰的录音。")
        start = float(best["start"])
        duration = float(best.get("clip_duration", best["duration"]))
        extract_reference_clip(upload_path, start, duration, clip_path)
        record_clone_consent(
            original_name,
            audio_content,
            str(best.get("text", "")),
            target_text,
        )
        generate_clone_audio(
            target_text,
            clip_path,
            "",
            OUTPUTS / filename,
            x_vector_only=True,
        )
    finally:
        upload_path.unlink(missing_ok=True)
        clip_path.unlink(missing_ok=True)

    return {
        "audio_url": f"/audio/{filename}",
        "message": "中文语音已生成（已自动识别日语参考录音）",
        "reference_seconds": round(duration, 1),
        "segment_count": int(asr_result.get("segment_count", 0)),
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>本地语音台</title>
  <style>
    :root { --ink:#182220; --paper:#f6f3ec; --muted:#69716c; --line:#d6d1c7; --amber:#db7a38; --amber-dark:#a74c17; --teal:#dce9e2; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--ink); background:linear-gradient(115deg,#17201e 0%,#263733 55%,#17201e 100%); font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif; }
    .shell { width:min(1100px,calc(100% - 32px)); margin:0 auto; padding:38px 0 52px; }
    .topbar { display:flex; align-items:flex-end; justify-content:space-between; color:#f9f3e9; margin-bottom:28px; }
    .brand { font-size:28px; font-weight:750; letter-spacing:-.04em; }
    .brand small { display:block; margin-top:6px; color:#b8c8c0; font-size:13px; font-weight:500; letter-spacing:0; }
    .status { color:#d5e8dc; font-size:13px; }
    .dot { display:inline-block; width:8px; height:8px; margin-right:7px; border-radius:50%; background:#79c99a; box-shadow:0 0 0 4px rgba(121,201,154,.14); }
    main { background:var(--paper); box-shadow:0 18px 70px rgba(0,0,0,.22); }
    .workspace { display:grid; grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr); }
    .composer { padding:40px; border-right:1px solid var(--line); }
    .side { padding:34px 32px; background:#eeece5; }
    .eyebrow { margin:0 0 9px; color:var(--amber-dark); font-size:12px; font-weight:750; letter-spacing:.09em; }
    h1 { margin:0; font-size:31px; letter-spacing:-.055em; line-height:1.13; }
    .hint { margin:11px 0 25px; color:var(--muted); font-size:14px; line-height:1.55; }
    textarea { width:100%; min-height:236px; resize:vertical; border:1px solid var(--line); border-radius:2px; outline:none; padding:18px; background:#fffdf8; color:var(--ink); font:16px/1.7 inherit; transition:border-color .2s,box-shadow .2s; }
    textarea:focus { border-color:var(--amber); box-shadow:0 0 0 3px rgba(219,122,56,.13); }
    input[type=file] { width:100%; border:1px dashed #aaa398; padding:12px; background:#fffdf8; color:var(--muted); font:13px inherit; }
    .counter { margin-top:7px; color:var(--muted); font-size:12px; text-align:right; }
    .section { border-top:1px solid var(--line); margin-top:27px; padding-top:23px; }
    .section-head { display:flex; justify-content:space-between; align-items:baseline; gap:12px; }
    h2 { margin:0; font-size:16px; letter-spacing:-.02em; }
    .section-head span { color:var(--muted); font-size:12px; }
    .voice-list { display:grid; grid-template-columns:1fr 1fr; gap:9px; margin-top:15px; }
    .voice-row { display:flex; align-items:center; min-width:0; }
    .voice { flex:1; min-height:52px; border:1px solid var(--line); background:transparent; color:var(--ink); padding:9px 12px; text-align:left; cursor:pointer; transition:.18s ease; }
    .voice strong,.voice em { display:block; }
    .voice strong { font-size:14px; }
    .voice em { color:var(--muted); font-size:11px; font-style:normal; margin-top:3px; }
    .voice.selected { border-color:var(--ink); background:var(--teal); box-shadow:inset 3px 0 0 var(--amber); }
    .listen { width:41px; align-self:stretch; border:1px solid var(--line); border-left:0; background:#fffdf8; color:var(--amber-dark); font-weight:800; cursor:pointer; }
    .chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
    .chip { min-height:37px; padding:0 13px; border:1px solid var(--line); border-radius:999px; background:transparent; color:var(--ink); cursor:pointer; font:13px inherit; transition:.18s ease; }
    .chip.selected { border-color:var(--ink); background:var(--ink); color:#fffdf8; }
    .mode-switch { display:flex; gap:7px; margin-top:14px; }
    .mode { flex:1; min-height:45px; border:1px solid var(--line); background:transparent; color:var(--ink); cursor:pointer; font:700 13px inherit; }
    .mode.selected { border-color:var(--ink); background:var(--teal); box-shadow:inset 3px 0 0 var(--amber); }
    .clone-panel { display:none; margin-top:27px; padding:19px; border:1px solid var(--line); background:#f0eee7; }
    .clone-panel.visible { display:block; animation:reveal .22s ease-out; }
    .clone-panel textarea { min-height:92px; margin-top:8px; padding:12px; font-size:14px; }
    .field-label { display:block; margin:17px 0 7px; font-size:13px; font-weight:700; }
    .field-note { margin:6px 0 0; color:var(--muted); font-size:12px; line-height:1.55; }
    .advanced { margin-top:18px; border-top:1px solid var(--line); padding-top:15px; }
    .advanced summary { color:var(--ink); cursor:pointer; font-size:13px; font-weight:700; }
    .advanced[open] summary { color:var(--amber-dark); }
    .consent { display:flex; align-items:flex-start; gap:9px; margin-top:17px; color:var(--ink); font-size:13px; line-height:1.5; cursor:pointer; }
    .consent input { width:16px; height:16px; margin-top:2px; accent-color:var(--amber-dark); }
    .preset-controls.hidden { display:none; }
    @keyframes reveal { from { opacity:0; transform:translateY(-5px); } to { opacity:1; transform:translateY(0); } }
    .generate { width:100%; margin-top:27px; min-height:54px; border:0; background:var(--amber); color:white; cursor:pointer; font:700 16px inherit; letter-spacing:.01em; transition:background .2s,transform .2s; }
    .generate:hover { background:var(--amber-dark); transform:translateY(-1px); }
    .generate:disabled { background:#b9b2a9; cursor:wait; transform:none; }
    .now-playing { min-height:134px; display:flex; flex-direction:column; justify-content:center; }
    .empty { color:var(--muted); font-size:14px; line-height:1.6; }
    .wave { display:flex; align-items:center; gap:4px; height:33px; margin:8px 0 18px; }
    .wave i { width:4px; border-radius:4px; background:var(--amber); animation:breathe 1.2s ease-in-out infinite; }
    .wave i:nth-child(1){height:10px}.wave i:nth-child(2){height:24px;animation-delay:.08s}.wave i:nth-child(3){height:16px;animation-delay:.16s}.wave i:nth-child(4){height:30px;animation-delay:.24s}.wave i:nth-child(5){height:12px;animation-delay:.32s}.wave i:nth-child(6){height:22px;animation-delay:.4s}.wave i:nth-child(7){height:8px;animation-delay:.48s}
    @keyframes breathe { 50% { transform:scaleY(.48); opacity:.5; } }
    audio { width:100%; margin-top:9px; }
    .message { min-height:20px; margin-top:14px; color:var(--muted); font-size:13px; }
    .message.error { color:#aa321e; }
    .quiet { margin-top:26px; padding-top:22px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; line-height:1.65; }
    @media (max-width:760px) { .shell{width:min(100% - 22px,650px);padding-top:22px}.topbar{margin-bottom:17px}.workspace{grid-template-columns:1fr}.composer{padding:27px 22px;border-right:0;border-bottom:1px solid var(--line)}.side{padding:25px 22px}.voice-list{grid-template-columns:1fr}h1{font-size:27px}.status{display:none} }
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar"><div class="brand">本地语音台<small>选声音 · 选风格 · 生成语音</small></div><div class="status"><span class="dot"></span>本机模型已连接</div></header>
    <main class="workspace">
      <section class="composer">
        <p class="eyebrow">开始创作</p><h1>把文字，变成好听的中文语音。</h1><p class="hint">输入需要朗读的内容，再从右侧选择声音和表达方式。</p>
        <textarea id="text" maxlength="800" placeholder="例如：欢迎来到本地语音台。今天我们一起试试新的中文配音效果。"></textarea><div class="counter"><span id="count">0</span> / 800</div>
        <section class="clone-panel" id="clone-panel" aria-live="polite">
          <h2>日语音色生成中文</h2><p class="field-note">上传授权日语录音即可。系统会自动转写、挑选清晰片段，并按左侧中文文案生成；你不用填写日语。</p>
          <label class="field-label" for="referenceAudio">参考录音</label><input id="referenceAudio" type="file" accept=".wav,.mp3,.flac,.ogg,audio/*"><p class="field-note">推荐 16-bit 单声道 WAV 或 MP3；M4A 请先导出为 WAV。</p>
          <details class="advanced"><summary>高相似度设置（可选）</summary><p class="field-note">仅当你拥有与录音逐字对应的日语原文时才开启。默认跨语言模式更优先保证朗读中文文案。</p><label class="field-label" for="referenceText">准确的日语原文</label><textarea id="referenceText" maxlength="2000" placeholder="可留空：系统将自动转写并以跨语言音色模式生成。"></textarea><label class="consent"><input id="useTranscript" type="checkbox"><span>我确认上述日语原文与整段参考录音逐字对应，使用高相似度模式。</span></label></details>
          <label class="consent"><input id="cloneConsent" type="checkbox"><span>我确认我拥有该参考声音用于语音克隆的明确授权，并同意仅将其用于本次内部生成。</span></label>
        </section>
        <button class="generate" id="generate">生成语音</button><div class="message" id="message" role="status"></div>
      </section>
      <aside class="side">
        <section><div class="section-head"><h2>生成方式</h2><span>默认最简单</span></div><div class="mode-switch" id="modes"><button class="mode selected" data-mode="preset">预设声音</button><button class="mode" data-mode="clone">授权声线克隆</button></div></section>
        <div class="preset-controls" id="preset-controls">
          <section class="section"><div class="section-head"><h2>1. 选择声音</h2><span>可先点击试听</span></div><div class="voice-list" id="voices"></div></section>
          <section class="section"><div class="section-head"><h2>2. 选择表达方式</h2><span>不用写提示词</span></div><div class="chips" id="styles"></div></section>
          <section class="section"><div class="section-head"><h2>3. 选择语速</h2><span>轻微调整</span></div><div class="chips" id="speeds"></div></section>
        </div>
        <section class="section now-playing" id="result"><div class="empty">生成完成后，音频会出现在这里。</div></section>
        <div class="quiet">音频在内网本机生成。授权克隆只记录授权确认和不可逆校验摘要，不保存参考录音或原文。单次生成排队执行，避免与其他 GPU 任务争抢资源。</div>
      </aside>
    </main>
  </div>
  <script>
    const voices=[['Vivian','推荐试听'],['Serena','推荐试听'],['Ryan','推荐试听'],['Uncle Fu','推荐试听'],['Aiden','更多声音'],['Eric','更多声音'],['Dylan','更多声音'],['Ono Anna','更多声音'],['Sohee','更多声音']];
    const styles=[['natural','自然'],['soft_cute','柔萌女声'],['gentle','温柔'],['broadcast','专业播报'],['story','讲故事'],['lively','活泼']];
    const speeds=[['slow','慢'],['normal','正常'],['fast','快']];
    const state={mode:'preset',voice:'Vivian',style:'natural',speed:'normal'};
    const text=document.querySelector('#text'), message=document.querySelector('#message'), result=document.querySelector('#result'), generate=document.querySelector('#generate');
    const clonePanel=document.querySelector('#clone-panel'), presetControls=document.querySelector('#preset-controls');
    function renderChoices(){
      document.querySelector('#voices').innerHTML=voices.map(([id,note])=>`<div class="voice-row"><button class="voice ${state.voice===id?'selected':''}" data-voice="${id}"><strong>${id}</strong><em>${note}</em></button><button class="listen" data-listen="${id}" aria-label="试听 ${id}">▶</button></div>`).join('');
      document.querySelector('#styles').innerHTML=styles.map(([id,label])=>`<button class="chip ${state.style===id?'selected':''}" data-style="${id}">${label}</button>`).join('');
      document.querySelector('#speeds').innerHTML=speeds.map(([id,label])=>`<button class="chip ${state.speed===id?'selected':''}" data-speed="${id}">${label}</button>`).join('');
      document.querySelectorAll('[data-mode]').forEach(button=>button.classList.toggle('selected',button.dataset.mode===state.mode));
      clonePanel.classList.toggle('visible',state.mode==='clone');
      presetControls.classList.toggle('hidden',state.mode==='clone');
    }
    function setMessage(value,error=false){message.textContent=value;message.className='message'+(error?' error':'');}
    async function readResponse(response){const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||'请求失败，请重试。');return data;}
    async function request(url,payload){return readResponse(await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}));}
    function showAudio(data,title){result.innerHTML=`<div class="wave"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><strong>${title}</strong><audio controls autoplay src="${data.audio_url}"></audio>`;}
    document.addEventListener('click',async(event)=>{
      const {voice,style,speed,listen,mode}=event.target.dataset;
      if(mode){state.mode=mode;renderChoices();return;}
      if(voice){state.voice=voice;renderChoices();}
      if(style){state.style=style;renderChoices();}
      if(speed){state.speed=speed;renderChoices();}
      if(listen){try{setMessage(`${listen} 正在生成试听…`);const data=await request('/api/preview',{voice:listen});showAudio(data,`${listen} 试听`);setMessage('试听已准备好');}catch(error){setMessage(error.message,true);}}
    });
    text.addEventListener('input',()=>document.querySelector('#count').textContent=text.value.length);
    generate.addEventListener('click',async()=>{
      const value=text.value.trim();
      if(!value){setMessage('请先输入需要朗读的文案。',true);text.focus();return;}
      generate.disabled=true;generate.textContent='正在生成…';
      try{
        let data;
        if(state.mode==='clone'){
          const file=document.querySelector('#referenceAudio').files[0];
          const referenceText=document.querySelector('#referenceText').value.trim();
          const consent=document.querySelector('#cloneConsent').checked;
          const useTranscript=document.querySelector('#useTranscript').checked;
          if(!file){throw new Error('请先选择拥有明确授权的参考录音。');}
          if(!consent){throw new Error('请先确认你拥有该参考声音的明确授权。');}
          if(useTranscript && !referenceText){throw new Error('高相似度模式需要填写与录音逐字对应的日语原文。');}
          setMessage(useTranscript?'正在使用高相似度模式生成中文语音，请稍候。':'正在自动识别日语录音并生成中文语音，请稍候。');
          const form=new FormData();form.append('text',value);form.append('consent',String(consent));form.append('reference_audio',file);
          if(useTranscript){form.append('reference_text',referenceText);data=await readResponse(await fetch('/api/clone',{method:'POST',body:form}));showAudio(data,'高相似度中文语音已生成');}
          else {data=await readResponse(await fetch('/api/auto-clone',{method:'POST',body:form}));showAudio(data,'中文语音已生成');}
        }else{
          setMessage('模型正在生成语音，请稍候。');
          data=await request('/api/synthesize',{text:value,voice:state.voice,style:state.style,speed:state.speed});
          showAudio(data,'生成完成');
        }
        setMessage('语音已生成，可以播放或重新生成。');
      }catch(error){setMessage(error.message,true);}finally{generate.disabled=false;generate.textContent='生成语音';}
    });
    renderChoices();
  </script>
</body>
</html>"""
