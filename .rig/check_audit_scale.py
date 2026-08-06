#!/usr/bin/env python3
"""RIG L8 layer 7 (audit): build a larger, mixed-outcome trail (auto,
validated, escalated, rejected actions interleaved) and confirm the full
chain verifies end to end — proving correctness holds at scale, not just
for the 2-4 packet examples used elsewhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.action_gate import ActionGate, EscalationRequired, ValidationFailed  # noqa: E402
from src.audit_trail import GENESIS_HASH, AuditTrail  # noqa: E402
from src.verifier import Verifier  # noqa: E402

SECRET = "audit-layer-check"
N = 30


def main() -> int:
    trail = AuditTrail(secret=SECRET)
    gate = ActionGate(audit_trail=trail, validator=lambda action, inp, out: inp % 5 != 0)

    for i in range(N):
        confidence = (i * 37 % 100) / 100.0  # deterministic pseudo-spread across [0, 1)
        try:
            gate.execute(f"action_{i}", lambda x: {"i": x}, i, confidence)
        except (EscalationRequired, ValidationFailed):
            pass  # still sealed into the trail — that is what this layer checks

    if len(trail) != N:
        print(f"audit: FAIL — expected {N} sealed packets, found {len(trail)}")
        return 1

    ok, reason = trail.verify()
    if not ok:
        print(f"audit: FAIL — {N}-packet trail did not verify: {reason}")
        return 1

    if trail.packets[0].prev_hash != GENESIS_HASH:
        print("audit: FAIL — first packet does not reference the genesis hash")
        return 1

    statuses = sorted({p.status for p in trail.packets})
    report = Verifier(secret=SECRET).verify_trail(trail)
    if not report.valid:
        print(f"audit: FAIL — independent verifier disagreed with in-process verify(): {report.findings}")
        return 1

    print(f"audit: PASS — {N}-packet mixed-outcome trail (statuses={statuses}) verified end to end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
