# Security

This application can synthesize speech and clone an authorized voice. A local deployment can still cause harm if it is exposed without access control.

## Deployment requirements

- Bind the UI and all model services to 127.0.0.1 by default.
- If LAN access is required, place the UI behind authentication and restrict allowed users.
- Never expose the CustomVoice, Base or ASR backend ports directly.
- Keep .env and .runtime/ outside Git and backups shared with unauthorized users.
- Set a short output retention period and monitor that temporary uploads are deleted.
- Do not treat the consent checkbox as proof that an uploader is authorized.
- Keep model weights and third-party binaries outside this repository.

The health endpoint intentionally omits backend addresses. Logs and audit records must not contain source audio or transcription text. The audit log stores timestamps, cryptographic digests and file suffixes; short text digests can still be sensitive and require restricted access.

Before changing source visibility, scan every reachable Git ref for secrets, review upload validation against real file formats, and complete a threat review for the intended network boundary. This source-publication review has passed; evidence is tracked in [docs/PUBLIC_RELEASE_REVIEW.md](docs/PUBLIC_RELEASE_REVIEW.md). Target Windows/GPU acceptance is still required before claiming runtime compatibility or production readiness, but it does not block publication of the Alpha source.

Report vulnerabilities privately to the repository owner. Do not attach real voice samples or generated impersonation content.
