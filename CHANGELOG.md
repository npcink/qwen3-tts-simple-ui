# Changelog

## Unreleased

### Added

- Validate uploaded WAV, MP3, FLAC and OGG container signatures before decoding.
- Reject untrusted Host headers and cross-site browser writes at the local HTTP boundary.
- Record the public-source threat review, real-format compatibility evidence and remaining release gates.

## 0.1.0-alpha.1 - 2026-07-20

### Added

- Extracted the UI, local ASR adapter and GPU queue lock into an independent repository.
- Added generic Windows launch templates, package metadata, offline tests and security documentation.
- Recorded sanitized source provenance without importing private internal Git history.

### Changed

- Removed host-specific Windows paths from the reusable launch templates.
- Moved outputs, uploads, logs, caches and audit records under a configurable runtime directory.
- Removed original reference filenames from consent audit records.
- Changed the default UI listener from LAN-wide to loopback-only.
