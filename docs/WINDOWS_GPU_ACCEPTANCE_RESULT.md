# Windows/GPU acceptance result

This is the sanitized end-to-end evidence for the first verified runtime
configuration. It records only what is needed to scope the compatibility claim.
The authorized reference recording, transcript, generated speech, host details,
account details, absolute paths and raw logs are intentionally excluded.

```text
Candidate commit: cfae08cb18cdfb7d7804a900d1e1acbf72ed5371
Test date (UTC): 2026-07-21
Windows version: Windows 11
GPU model / driver / CUDA: NVIDIA GeForce RTX 4090 / 595.97 / 13.2
CustomVoice compatibility: PASS
Base clone compatibility: PASS
ASR compatibility: PASS
Loopback listeners: PASS
Upload cleanup and retention: PASS
Request-boundary controls: PASS
Restart / GPU lock recovery: PASS
Authorized sample used: YES (sample not retained)
Generated-output listening check: PASS
Overall: PASS
```

The candidate commit above is the code that ran on the target host. A later
documentation-only commit may carry this record and the release tag. This result
does not claim compatibility with every Windows or GPU configuration, does not
distribute a runtime package, and does not make public-network or production use
supported.
