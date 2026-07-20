param(
    [string]$Python = "",
    [string]$ListenAddress = "127.0.0.1",
    [int]$Port = 18001
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if ([string]::IsNullOrWhiteSpace($Python)) {
    if (-not [string]::IsNullOrWhiteSpace($env:QWEN_TTS_PYTHON)) {
        $Python = $env:QWEN_TTS_PYTHON
    } else {
        $Python = (Get-Command python.exe -ErrorAction Stop).Source
    }
}

$env:NO_PROXY = "127.0.0.1,localhost"
$env:no_proxy = "127.0.0.1,localhost"
Set-Location $repoRoot

& $Python -m uvicorn app:app --app-dir $repoRoot --host $ListenAddress --port $Port
