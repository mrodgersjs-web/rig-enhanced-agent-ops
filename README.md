# RIG-Enhanced Agent Ops

**Proof-gated agent operations with tamper-evident audit trail.**

Every agent action is gated, signed, and auditable. This is what
[AgentOps](https://www.agentops.ai/)-style observability looks like once
the [RIG doctrine overlay](../rig-doctrine-overlay) is applied to it: agent
actions don't just get *logged*, they get *judged* before they run, and
*sealed* into a chain that proves — to a party who trusts nothing but math
— exactly what happened, in what order, and that nothing was edited after
the fact.

```
  agent action + confidence
          │
          ▼
   ┌─────────────┐     >= 0.85            run it, seal AUTO_EXECUTED
   │  ActionGate │ ──  0.70 .. 0.85  ──▶   run it, seal VALIDATED (optional
   └─────────────┘     <  0.70            independent validator)
          │                                never run it, seal ESCALATED
          ▼
   ProofPacket #N
     prev_hash  = hash of packet #N-1
     hash       = sha256(action, input, output, confidence, status, ...)
     signature  = HMAC(hash, secret)            [optional, authenticity]
          │
          ▼
   AuditTrail — blockchain-style chain of every ProofPacket
          │
          ▼
   Verifier — independent, recomputes every hash + signature from scratch
```

## Why this is not "just logging"

Traditional agent observability records *what happened, after it
happened*. That's necessary but not sufficient for agents that can take
real-world actions — send money, delete data, message customers, deploy
code. RIG-Enhanced Agent Ops adds two things a log file cannot give you:

1. **A gate, not just a record.** [`ActionGate`](src/action_gate.py) sits
   *in front of* every action. An action below the escalation threshold
   never runs — full stop. Its refusal is sealed just as rigorously as an
   execution would have been.
2. **Tamper evidence, not just storage.** [`AuditTrail`](src/audit_trail.py)
   chains every [`ProofPacket`](src/audit_trail.py) to the one before it,
   blockchain-style. Edit any field of any packet after the fact — the
   output, the confidence, even the timestamp — and every hash from that
   point forward stops matching. An independent [`Verifier`](src/verifier.py)
   that only ever sees an *exported* copy of the trail can prove this
   without trusting the process that produced it.

## The confidence gate

```
confidence >= 0.85            AUTO_EXECUTE   run it, seal the proof
0.70 <= confidence < 0.85     VALIDATE       run it, optionally confirm with
                                              an independent validator, seal
                                              the proof either way
confidence <  0.70            ESCALATE       never run it — seal the refusal
                                              and hand off to a human/process
```

Both thresholds are configurable per `ActionGate` instance, but the
default 0.85 / 0.70 split is the RIG doctrine baseline: better than
9-in-10 confidence to act alone, better than 7-in-10 to act with a second
opinion, and below that, no autonomy at all.

## Quickstart

```python
from src.action_gate import ActionGate, EscalationRequired
from src.audit_trail import AuditTrail
from src.verifier import Verifier

# an audit trail that also HMAC-signs every packet it seals
trail = AuditTrail(secret="use-a-real-secret-in-production")
gate = ActionGate(audit_trail=trail)


def deploy(release_id: str) -> dict:
    return {"deployed": release_id, "region": "us-east-1"}


# high confidence -> runs immediately
result = gate.execute("deploy_release", deploy, "release-42", confidence=0.96)
print(result.status)          # GateStatus.AUTO_EXECUTED
print(result.proof.hash)      # sha256 hexdigest sealed for this action

# low confidence -> never runs, escalates instead
try:
    gate.execute("delete_production_database", deploy, "prod-db", confidence=0.40)
except EscalationRequired as exc:
    print(exc)  # action was never called; the refusal itself is on the record

# ship the trail to an auditor who has never seen this process
exported = trail.to_json()
report = Verifier(secret="use-a-real-secret-in-production").verify_json(exported)
assert report.valid
```

Try it yourself: attempt to quietly rewrite history and watch the
verifier catch it.

```python
trail.tamper(0, output={"deployed": "not-what-actually-happened"})
ok, reason = trail.verify()
assert not ok
print(reason)  # "tamper detected at packet #0: stored hash ... does not
               #  match recomputed ..."
```

## Package layout

| Path                              | What it is                                                              |
| ---------------------------------- | ------------------------------------------------------------------------ |
| `src/action_gate.py`               | `ActionGate` — confidence-gated execution wrapper                       |
| `src/audit_trail.py`               | `AuditTrail` / `ProofPacket` — the hash-chained, HMAC-signable ledger    |
| `src/verifier.py`                  | `Verifier` — independent, from-scratch chain + signature recomputation  |
| `AGENTS.md`                        | TAC doctrine for agents (human or AI) working in this repo               |
| `.rig/smoke.sh` + `smoke_runner.py`| **L10** self-evolving smoke harness (see below)                          |
| `.rig/verify.sh` + `check_*.py`    | **L8** eight-layer verification gate (see below)                        |
| `spec/features/*.feature`          | Executable Gherkin behavior spec (OpenSpec BDD, driven by `behave`)     |
| `test/test_action_gate.py`         | pytest suite (20 tests: unit + integration)                             |

## L10 — self-evolving smoke harness

```bash
.rig/smoke.sh
```

Runs a mock agent through the gate across six scenarios (auto-execute,
validate, escalate, chain integrity, tamper detection, signature
integrity) and journals the result of every run to
`.rig/.smoke-journal.json`. Any scenario that has **ever** failed has its
`hardening_level` permanently ratcheted up — future runs of that scenario
test strictly more inputs, more mutated fields, and more edge cases than
before. Hardening never regresses on a pass; only a failure raises it. The
harness learns what broke and watches it more closely forever, not just
until the next green run.

## L8 — eight-layer verification gate

```bash
.rig/verify.sh
```

| # | Layer         | What it checks                                                          |
| - | ------------- | -------------------------------------------------------------------------|
| 1 | syntax        | every module compiles                                                    |
| 2 | unit          | `pytest -m unit` — isolated component behavior                           |
| 3 | integration   | `pytest -m integration` — full gate → trail → verifier pipeline          |
| 4 | eval          | confidence-routing table swept across `[0, 1]` (1000+ points, doctrine-exact boundaries) |
| 5 | proof         | every sealed `ProofPacket` carries all required evidentiary fields       |
| 6 | gate          | the tamper-detection gate itself is proven to fire, on a fresh trail     |
| 7 | audit         | a 30-packet, mixed-outcome trail verifies end to end                     |
| 8 | sign-off      | hard `AND` of layers 1–7 → `.rig/gate-report.json` (HMAC-signed if `RIG_PROOF_SECRET` is set) |

`verify.sh` exits `0` only if **all seven** upstream layers pass — sign-off
is never a majority vote.

## OpenSpec BDD

[`spec/features/gated-agent-actions.feature`](spec/features/gated-agent-actions.feature)
is executable, not decorative:

```bash
pip install -e ".[dev]"
behave spec/features/gated-agent-actions.feature
```

Scenarios cover the confidence-routing contract (auto-execute /
validate-with-rejection / escalate), the blockchain-style chain linkage,
and — the scenario that matters most — **tampered audit trail detected**,
including the case where an attacker tampers a packet whose downstream
chain otherwise still looks correct.

## Design notes

- **Integrity vs. authenticity are separate guarantees.** The hash chain
  alone (no secret required) proves nothing in the trail has changed since
  it was sealed. The HMAC signature (requires the secret) additionally
  proves *who* sealed it. `Verifier` checks whichever guarantee you give it
  the material to check.
- **A single tampered packet is one finding, not a cascade.** Verification
  advances the expected `prev_hash` using each packet's *stored* hash, so
  editing packet #2 without resealing it is reported once, at #2 — not as
  N chain-break findings for every packet after it.
- **The verifier trusts nothing it didn't recompute itself.** `Verifier`
  never calls back into a live `AuditTrail`'s internal state; it only ever
  looks at exported plain dicts and recomputes every hash and signature
  from first principles, the way a real external auditor would.
- **Escalation means the action never ran.** `EscalationRequired` is raised
  *before* `fn` is invoked. `ValidationFailed` is different: the action DID
  run and was retroactively judged invalid by an independent validator —
  both outcomes are sealed, but only one of them means "this never
  happened."

## License

MIT — see [`LICENSE`](LICENSE).
