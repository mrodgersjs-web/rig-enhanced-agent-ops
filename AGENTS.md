# AGENTS.md — rig-enhanced-agent-ops

Tactical Agentic Coding (TAC) doctrine for any agent — human or AI —
working in this repository. This file is hierarchical context: read it
before touching anything under `src/`, `.rig/`, `spec/`, or `test/`.

## What this repo is

A reference implementation proving that agent observability can enforce
policy *before* an action runs, not just record it after. Three files are
the entire load-bearing surface:

- `src/action_gate.py` — the policy: confidence in, execute/validate/escalate out.
- `src/audit_trail.py` — the ledger: append-only, hash-chained, optionally signed.
- `src/verifier.py` — the auditor: trusts nothing it did not recompute itself.

Everything else (tests, BDD spec, L8/L10 harnesses) exists to keep those
three files honest.

## Prime directive

**The hash chain must always be real.** `prev_hash` on packet N must
always equal the actual `hash` of packet N-1, computed by the same
deterministic function `Verifier` uses independently. Any change here is
a security regression, not a refactor — treat it accordingly:

- Never let `ProofPacket.hash` or `.signature` be set anywhere except
  inside `seal()`.
- Never let `AuditTrail.append()` accept a caller-supplied `prev_hash` —
  it must always be `self.latest_hash()`.
- Never let `Verifier` import or call back into a live `AuditTrail`'s
  private state (`_packets`, `_secret`). It receives only exported plain
  data (`to_json()` / `to_dict()`), by design, forever. This is what makes
  it an *independent* verifier and not a rubber stamp.

## Builder ≠ Verifier

The person (or agent) who writes a change to `action_gate.py` or
`audit_trail.py` is not the one who gets to declare it correct.

1. **Builder** implements, and runs `.rig/smoke.sh` locally as a fast
   sanity check.
2. **Verifier** is `.rig/verify.sh` (L8) — a separate, mechanical process
   that recompiles, re-tests, and re-derives every guarantee from
   scratch. A Builder claiming "done" without a green `verify.sh` run is
   not done.
3. Nothing merges on a Builder's self-report. `.rig/gate-report.json` (the
   L8 sign-off artifact) is the only acceptable evidence of "this passes."

This mirrors the domain the repo demonstrates: an `ActionGate` doesn't
trust an agent's self-reported confidence blindly either — above 0.70 it
still seals a `ProofPacket`, and below 0.85 it still supports an
independent validator. Apply the same skepticism to your own changes that
this code applies to agent actions.

## Context hierarchy

1. This file (`AGENTS.md`) — repo-wide rules, read first.
2. `README.md` — architecture, quickstart, design notes.
3. Module docstrings in `src/*.py` — the authoritative behavior contract
   for that module; code comments explain *why*, not *what*.
4. `spec/features/gated-agent-actions.feature` — the behavior spec in
   plain language. If a change makes a scenario false, either the change
   or the scenario is wrong — resolve that explicitly, never silently.

## Rules for changes in this repo

- **Never weaken the confidence thresholds** (`0.85` / `0.70`) without
  updating `README.md`, the `.feature` file's Scenario Outline tables, and
  `.rig/eval_gate_routing.py` in the same change. They must always agree.
- **Never make `EscalationRequired` call the action.** The entire safety
  property of the ESCALATE band is that `fn` is never invoked. A test
  (`test_low_confidence_escalates_and_never_executes`) enforces this —
  keep it passing, don't rewrite it to stop checking `action.calls == []`.
- **Never add a way to construct a `ProofPacket` with a hand-set `hash` or
  `signature`.** The only legitimate path is `seal()`. If you need a test
  fixture with a "pre-tampered" packet, build it via `AuditTrail.tamper()`
  (which exists exactly for this and is clearly named as a test/demo
  helper, never called from production code paths).
- **No secrets in fixtures or history.** Test/demo signing keys
  (`"top-secret"`, `"integration-test-secret"`, etc.) are fine in
  `test/` and `.rig/check_*.py` — they exist to prove the mechanism
  works, not to protect anything real. Never commit a real
  `RIG_PROOF_SECRET` value anywhere in this repo.
- **Every new gated action path needs a new scenario**, not just a new
  unit test. If you add a new `GateStatus`, add the corresponding
  `Given`/`When`/`Then` to the `.feature` file and its step definitions —
  the BDD spec is meant to stay an accurate plain-language description of
  what the gate does, not fall behind the code.
- **L10 hardening state (`.rig/.smoke-journal.json`) is append-only
  history, not scratch space.** Don't hand-edit `hardening_level` down to
  "fix" a red run — that defeats the entire point of the harness. If a
  scenario is hardened and now flaky, fix the flakiness; don't erase the
  memory that it broke.

## Running the gates

```bash
.rig/smoke.sh     # L10 — fast, stdlib-only, self-evolving
.rig/verify.sh     # L8  — full eight-layer gate, needs pytest/behave (pip install -e .[dev])
```

Both exit non-zero on any failure. Neither should ever be "fixed" by
deleting the check that failed.

## RIG lattice contract (stamped)

This repository runs the shared RIG lattice: loops in `.rig/loop.yaml`, pre-tool
hooks in `.rig/hooks/`, CI gate in `.github/workflows/rig-lattice.yml`, execution
owner routing in `.rig/work-routing.yaml` (operator standard 2026-09-11), and a
results-driven MCP server at `mcp/server.py` returning verified results only.
D85 rules apply: every outward action needs a Gate-D request + typed approval;
durable builds need four ratios >= 0.85 and a sealed proof. Done-claims need TAC
close-gate sealed evidence. Shared agent substrate lives in Supabase schema
`rig_shared` (see PROGRAM.md in rig-lattice-retrofit).
