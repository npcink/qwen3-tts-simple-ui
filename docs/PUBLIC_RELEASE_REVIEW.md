# Public source release review

## Decision

**GO for public source Alpha.** This decision approves public visibility of the
source repository. It does not approve an internet-facing service, a Windows
runtime package, a supported GPU matrix or production use. ADR-002 records why
those runtime claims are evaluated separately.

Current status:

| Surface | Status |
| --- | --- |
| Source repository visibility | GO — public Alpha |
| Target Windows/GPU compatibility | PENDING — no claim yet |
| Direct public-network deployment | UNSUPPORTED |
| Production readiness | NOT CLAIMED |

## Supported runtime boundaries

1. **Default:** one trusted user, with the UI and every backend bound to
   `127.0.0.1`.
2. **Conditional:** a restricted LAN, with the UI behind an authenticated
   reverse proxy, an explicit `QWEN_TTS_ALLOWED_HOSTS` value, and model
   backends still bound to loopback.

Direct internet exposure and direct LAN exposure without authentication are
unsupported.

## Assets and trust boundaries

Protected assets include uploaded voice recordings, generated speech, consent
audit digests, model/GPU availability, backend endpoints, and host filesystem
paths. Untrusted data crosses the browser-to-UI boundary through text and file
uploads. The UI then crosses a second boundary to locally configured model and
ASR services. Runtime files cross a third boundary onto local storage.

## Threat review

| Threat | Current controls | Residual requirement |
| --- | --- | --- |
| Untrusted host routing or DNS rebinding | The UI accepts loopback Host headers by default; additional proxy hosts require explicit configuration. The ASR service accepts loopback Host headers only. | Preserve the original Host header at an authenticated reverse proxy and keep backend ports private. |
| Cross-site browser requests to local services | State-changing UI and ASR requests reject cross-site Fetch Metadata and mismatched Origin/Host values. Non-browser clients without Origin remain supported. | Authentication is still required for every multi-user deployment. |
| Unauthorized voice cloning | A consent confirmation is required and the audit record retains only timestamp, suffix and digests. | The confirmation is not identity verification. The deployment owner must control users and handle abuse reports. |
| Disguised or malformed uploads | Upload size, suffix, container signature and suffix/signature agreement are checked before the file is written or decoded. Temporary uploads are deleted in `finally` blocks. | SoX, Whisper and model services remain parsers of untrusted media and must be patched. A valid header does not prove every frame is decodable. |
| Resource exhaustion | Text and upload sizes are bounded, generation is serialized, and the GPU lock has a timeout. | Authenticated LAN proxies should also impose request-rate and body-size limits. |
| Sensitive runtime retention | Uploads are deleted after each request; outputs expire; logs omit source text and audio; model weights and runtime data are ignored by Git. | Output cleanup must be monitored. Short-text digests can be sensitive and audit files require restricted access. |
| Backend or internal-address disclosure | Backend URLs come from operator configuration, are not accepted from requests, and are omitted from health responses. | Never expose model or ASR backend ports directly. |
| Misleading or abusive output | The UI states the authorization requirement and the repository ships an authorized-use policy. | Policy text cannot prevent impersonation by an already authorized operator; deployment governance remains necessary. |

## Verification record — 2026-07-21

- The GitHub repository was rebuilt from a clean reachable-history clone and
  contains only the two reviewed commits that precede this publication change.
- The pre-sanitization commit object is absent from the local object database,
  a fresh remote mirror and the GitHub commit API.
- The reachable history and current tree passed Gitleaks with no findings.
- The current tree was checked for private host paths, user paths, email
  addresses, credentials and real voice artifacts; only documented loopback
  addresses remain.
- GitHub Dependabot vulnerability alerts and private vulnerability reporting
  are enabled.
- Anonymous GitHub page, API and mirror-clone checks confirm that the repository
  is public, defaults to `main`, exposes only the reviewed history and does not
  resolve the pre-sanitization commit object.
- `pip-audit` found no known vulnerabilities in either the core or optional
  ASR requirement set at review time.
- Automated tests cover valid WAV generation, supported container headers,
  disguised HTML, truncated headers, extension mismatches, untrusted Host
  headers and cross-site requests.
- Format detection was exercised without retaining files against these
  upstream `jiaaro/pydub` test blobs:

| Format | Upstream fixture | Git blob | SHA-256 |
| --- | --- | --- | --- |
| OGG | `test/data/bach.ogg` | `144696e8a8eeb27c2e2f5eb65fca15d73eaae6d6` | `771acfec9d9e6cdcb00e0c49f559f5490b112711a0a07006d444b13ef8298eb0` |
| MP3 | `test/data/test1.mp3` | `5ff32361f647c9c3c3d126b96acc06be3561003d` | `c73480949234135a7c3e63a8c890ad9bf5c94d7b020f8158bbe8ae7fb6dc78a4` |
| FLAC | `test/data/test-192khz-32bit.flac` | `61458fb21686fa4d5bf18070aa5e6ae29409f997` | `13f49b449f823e79242c46700f24aa65b9b27fe22cdf384e3a1d6aa54b0e3543` |
| WAV | `test/data/test1-8bit.wav` | `040c4a320102741ffdee080c979ba3edbd484799` | `6868dcaf999822d9e7d66a085596f6765fb4a244a6b24282679b5a9c5ae0b173` |

The fixtures are public upstream compatibility evidence and are not committed
to this repository.

## Runtime follow-up

- Complete [the target Windows/GPU acceptance](WINDOWS_GPU_ACCEPTANCE.md)
  before claiming that configuration as supported or publishing a runtime
  artifact.
- Keep direct public-network deployment unsupported until authentication,
  rate limiting, abuse handling and operational monitoring have their own
  reviewed implementation.
- Do not create a stable or production-ready release from this Alpha decision.
