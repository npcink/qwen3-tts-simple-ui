# ADR-001: Publish the UI adapter without models or host operations

## Status

Accepted

## Date

2026-07-20

## Context

The original prototype combined reusable UI code with one Windows inference host's paths, model layout, ports and acceptance notes. Bundling those details would make the project hard to reuse and could expose internal infrastructure.

## Decision

The independent repository owns only:

- the FastAPI UI and local API surface
- temporary audio handling and output retention
- the optional ASR adapter
- the process-shared GPU queue lock
- generic launch templates and public-safe documentation

It does not distribute models, Qwen3-TTS, SoX, CUDA, voice samples or a production authentication layer. Real host operations and end-to-end evidence remain in private internal documentation.

The initial release is a private alpha. Default listeners remain loopback-only.

## Alternatives considered

### Bundle a complete Windows runtime

Rejected because model, CUDA and binary licensing and hardware compatibility need separate release work.

### Import the full private source history

Rejected because it contains unrelated internal infrastructure and historical security material.

### Expose all backend services to the LAN

Rejected because only the authenticated UI should become a network surface.

## Consequences

- Users must prepare compatible Qwen3-TTS backends separately.
- Backend API compatibility must be tested for each supported upstream version.
- Public distribution can be reviewed independently from private host documentation.
- Authentication remains a deployment responsibility until a later product decision adds it to the application.
