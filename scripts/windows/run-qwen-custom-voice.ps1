param(
    [string]$RuntimeRoot = $env:QWEN_TTS_RUNTIME_ROOT,
    [string]$ModelPath = $env:QWEN_TTS_CUSTOM_VOICE_MODEL,
    [string]$DemoExecutable = $env:QWEN_TTS_DEMO_EXE,
    [int]$Port = 18000
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($RuntimeRoot)) {
    throw "Set QWEN_TTS_RUNTIME_ROOT or pass -RuntimeRoot."
}
if ([string]::IsNullOrWhiteSpace($ModelPath)) {
    $ModelPath = Join-Path $RuntimeRoot "models\Qwen3-TTS-12Hz-1.7B-CustomVoice"
}
if ([string]::IsNullOrWhiteSpace($DemoExecutable)) {
    $DemoExecutable = Join-Path $RuntimeRoot ".venv\Scripts\qwen-tts-demo.exe"
}
if (-not [string]::IsNullOrWhiteSpace($env:QWEN_TTS_SOX_BINARY)) {
    $env:Path = (Split-Path $env:QWEN_TTS_SOX_BINARY -Parent) + ";" + $env:Path
}
if ([string]::IsNullOrWhiteSpace($env:HF_HOME)) {
    $env:HF_HOME = Join-Path $RuntimeRoot "hf-cache"
}

$arguments = @(
    $ModelPath,
    "--device", "cuda:0",
    "--dtype", "bfloat16",
    "--no-flash-attn",
    "--ip", "127.0.0.1",
    "--port", $Port,
    "--concurrency", "1"
)
& $DemoExecutable @arguments
