# ADR-002: Publish the source Alpha before hardware compatibility claims

## Status

Accepted

## Date

2026-07-21

## Context

ADR-001 isolated the reusable UI and local service adapters from private host
operations, model files and historical infrastructure. The repository has
since passed source-history cleanup, secret scanning, dependency review,
upload-boundary hardening, a network threat review and automated CI.

The project's immediate purpose is to preserve a clean public foundation for
future development. It is not a Windows installer, model distribution, hosted
voice-cloning service or production-readiness claim. Requiring access to one
specific Windows/GPU host before anyone can inspect or extend the source would
couple source availability to a separate runtime compatibility question.

## Decision

Publish the repository as `0.1.0-alpha.1` source code while stating four
independent statuses:

- source publication is approved
- target Windows/GPU compatibility remains unverified
- direct public-network deployment is unsupported
- production readiness is not claimed

No model weights, third-party runtimes, voice samples, generated audio or
host-specific evidence are published. Windows/GPU acceptance remains mandatory
before claiming that configuration as supported or distributing a runtime
artifact. GitHub visibility does not weaken the loopback-only deployment
default.

This ADR amends only the initial private-publication gate in ADR-001. The
UI-adapter-only architecture and separation from private host operations remain
accepted.

## Alternatives considered

### Wait for a target Windows/GPU host before publishing any source

Rejected because it conflates code review and reuse with hardware-specific
runtime evidence, delaying the repository's intended role as a development
foundation.

### Publish a stable or production-ready release immediately

Rejected because the repository has no target-host end-to-end evidence and
does not include authentication or a supported runtime bundle.

### Offer a public hosted demo

Rejected because voice-cloning access control, abuse handling, retention and
operational monitoring are outside this repository's current boundary.

## Consequences

- Users can inspect, fork and extend the source without interpreting it as a
  supported Windows package.
- README and project pages must keep the Alpha, local-only and unverified
  runtime labels visible.
- Future runtime claims require the sanitized Windows/GPU acceptance record.
- A public GitHub repository must enable private vulnerability reporting and
  keep Dependabot alerts active.
