# Contributing

This repository is a source-only Alpha for a constrained local Qwen3-TTS UI.
Changes should preserve the boundary documented in `docs/decisions/`: no model
weights, third-party runtimes, host-specific operations or production identity
system belong here.

## Local checks

Use Python 3.12 and install the core project in a virtual environment. Before
submitting a change, run:

```text
python -m compileall -q app.py asr_service.py audio_validation.py request_security.py gpu_lock.py tests
python -m unittest discover -s tests -v
```

Tests must not download models, call a GPU service or retain voice data.

## Pull requests

- Keep each change focused and explain the user-visible or boundary impact.
- Add regression tests for behavior changes.
- Do not commit `.env`, `.runtime/`, model files, logs, audit records, voice
  samples, generated audio, real hostnames, usernames or absolute host paths.
- Treat the UI and every backend as loopback-only unless an authenticated LAN
  deployment is being reviewed explicitly.

## Security and authorized voice use

Report vulnerabilities privately through GitHub rather than opening a public
Issue. Never attach real voice samples or generated impersonation content.
Voice-cloning changes must preserve the authorized-use policy in
`docs/USAGE_POLICY.md`.
