# Copilot instructions for rig-enhanced-agent-ops

## What this repo is

A small Python library for confidence-gated agent actions plus a tamper-evident
audit trail. An agent action is scored, then auto-executed, validated, or
escalated. Every decision, including refusals, is sealed into a hash chain that
an independent verifier can recompute without trusting the writer.

- `src/action_gate.py` thresholds and gate decisions.
- `src/audit_trail.py` ProofPacket, hash chain, HMAC signing, JSON export.
- `src/verifier.py` independent recomputation of the chain, including tamper
  detection (edit, reorder, delete).
- `src/cli.py` the `rig-agent-ops` command line: `demo`, `verify PATH`,
  `inspect PATH`.
- `mcp/server.py` exposes the gate and verifier to MCP clients.
- `spec/` behave feature files for the gated-action flow.

## Layout

`src/` is the package (typed, `py.typed` ships). `test/` is the pytest suite.
`docs/architecture.md` holds the design notes. `.rig/` holds the local proof
checks (`check_proof_shape.py`, `check_tamper_gate.py`, `verify.sh`, `smoke.sh`)
and the loop config. `.github/workflows/ci.yml` runs lint and the tests.

## Setup and test commands

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest -q --cov
```

Lint before every commit: `ruff check .`. Fast smoke path: `pytest -q test/`.
Run the README walkthrough with `rig-agent-ops demo` and check a trail with
`rig-agent-ops verify <exported-trail.json>`.

## Conventions

- Conventional commit prefixes: feat, fix, test, docs, ci, build, chore.
- Every behavior change lands with a test in the same commit.
- The audit trail is append-only and the verifier is the source of truth: never
  "fix" a chain by rewriting history, and never let the code that writes a
  packet decide whether it is valid.
- Determinism matters: same inputs, same verdicts and same hashes.
- No secrets in tracked files. `RIG_PROOF_SECRET` is read from the environment;
  tests use an ephemeral key. No machine paths in tracked files.

## Truth rule

Any number in a README, docstring, or comment must come from a command you ran
in this repo (for example `pytest -q`, `rig-agent-ops demo`, or `wc -l`).
Update the sentence in the same commit when the number changes. Never carry a
count over from an older run.
