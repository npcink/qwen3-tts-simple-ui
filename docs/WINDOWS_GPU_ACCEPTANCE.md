# Windows/GPU release acceptance

Run this checklist on the intended Windows inference host before claiming that
host configuration as supported, distributing a runtime package, or marking a
release production-ready. Publishing the Alpha source does not require this
hardware claim. Use only a voice sample for which the operator has explicit
permission. Do not copy the sample, its transcript, generated audio, hostnames,
usernames, absolute paths, tokens, or raw logs into this repository.

## Preconditions

- Check out the exact candidate commit with a clean worktree.
- Install the core and, when used, ASR dependencies from the repository.
- Keep the UI and all three model services bound to `127.0.0.1`.
- Use the generic launch scripts under `scripts/windows/`; keep host-specific
  paths in local environment configuration only.
- Confirm the test sample and target text are authorized and non-sensitive.

## Required checks

1. Start the compatible CustomVoice and Base services, then the optional ASR
   service and UI.
2. Confirm `GET http://127.0.0.1:18001/health` reports `ok` without disclosing
   backend addresses.
3. Generate and play one preset-voice result.
4. Generate and play one clone result from the authorized reference recording.
5. If ASR is part of the supported deployment, run one automatic Japanese-ASR
   clone and confirm the selected segment and generated result are usable.
6. Confirm temporary upload directories are empty after successful and failed
   requests. Confirm generated outputs follow the configured retention period.
7. Confirm ports `18000`, `18001`, `18002`, and `18003` listen only on loopback.
8. Open the UI in a browser and confirm an untrusted Host header and a
   cross-site POST are rejected; do not weaken `QWEN_TTS_ALLOWED_HOSTS` to `*`.
9. Restart each process and confirm the shared GPU lock recovers without stale
   lock failure.

## Sanitized evidence template

Store only a short result like this in the eventual release record:

```text
Candidate commit: <public commit SHA>
Test date (UTC): <date>
Windows version: <major release only>
GPU model / driver / CUDA: <non-identifying versions>
CustomVoice compatibility: PASS | FAIL
Base clone compatibility: PASS | FAIL
ASR compatibility: PASS | N/A | FAIL
Loopback listeners: PASS | FAIL
Upload cleanup and retention: PASS | FAIL
Restart / GPU lock recovery: PASS | FAIL
Authorized sample used: YES (sample not retained)
Overall: PASS | FAIL
```

Any failure keeps that Windows/GPU combination unverified until it is fixed and
the whole checklist is rerun. It does not require making the Alpha source
private again.

The first completed, sanitized record is available in
[WINDOWS_GPU_ACCEPTANCE_RESULT.md](WINDOWS_GPU_ACCEPTANCE_RESULT.md).
