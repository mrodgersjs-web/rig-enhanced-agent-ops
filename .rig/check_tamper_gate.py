#!/usr/bin/env python3
"""RIG L8 layer 6 (gate): prove the tamper-detection gate itself works —
tamper a packet, confirm AuditTrail.verify() AND an independent Verifier
both refuse to certify the trail as intact, and both point at the same
tampered packet. Deliberately separate from L10's adaptive journal so the
gate's correctness never depends on accumulated hardening state.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.action_gate import ActionGate  # noqa: E402
from src.audit_trail import AuditTrail  # noqa: E402
from src.verifier import Verifier  # noqa: E402

SECRET = "gate-layer-check"
TARGET_INDEX = 2


def main() -> int:
    trail = AuditTrail(secret=SECRET)
    gate = ActionGate(audit_trail=trail)
    for i in range(5):
        gate.execute(f"action_{i}", lambda x: x, f"payload-{i}", 0.9)

    ok_before, reason_before = trail.verify()
    if not ok_before:
        print(f"gate: FAIL — clean trail did not verify before tampering: {reason_before}")
        return 1

    trail.tamper(TARGET_INDEX, output="TAMPERED")

    ok_after, reason = trail.verify()
    if ok_after:
        print("gate: FAIL — AuditTrail.verify() did not detect tampering")
        return 1

    report = Verifier(secret=SECRET).verify_json(trail.to_json())
    if report.valid:
        print("gate: FAIL — independent Verifier did not detect tampering")
        return 1

    if not any(f.index == TARGET_INDEX for f in report.findings):
        print("gate: FAIL — tampering detected but not attributed to the correct packet")
        return 1

    print(f"gate: PASS — tampering detected and correctly localized by both layers ({reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
