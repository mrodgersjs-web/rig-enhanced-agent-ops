# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-19

### Changed

- Documentation rewritten in plain English with runnable worked examples and real output.
- Removed superlative claims from code, docs, and CLI descriptions.
- Packaging completed: dev extras (pytest, pytest-cov, ruff), ruff configuration, coverage configuration.

### Added

- `test/test_audit_trail.py`: eight tests (packet chaining and sealing,
  unsigned trails, the environment-variable key path, clean verify,
  tamper detection, JSON export round trip, garbage rejection, and the
  signed payload excluding hash and signature).
- `test/test_verifier.py`: six tests for the independent verifier (clean
  trail passes, file round trip, wrong key fails, post-seal edit is
  detected, packet reorder is detected, and the documented
  tail-truncation limitation where only the packet count changes).
- CI workflow that runs lint and the test suite with coverage on push and pull request.
- Community files: security policy, code of conduct, contributing guide, issue and pull request templates.
- `docs/architecture.md` design notes and a runnable example under `examples/`.
