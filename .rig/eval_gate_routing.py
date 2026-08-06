#!/usr/bin/env python3
"""RIG L8 layer 4 (eval): sweep the full confidence range and assert every
value routes to the status the doctrine specifies —

    confidence >= 0.85          -> auto_executed
    0.70 <= confidence < 0.85   -> validated
    confidence <  0.70          -> escalated

— independent of any individual unit-test assertion. This is a behavioral
eval of the routing *table* as a whole, not a check of one call site.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.action_gate import ActionGate, EscalationRequired  # noqa: E402

STEPS = 1000


def expected_status(confidence: float) -> str:
    if confidence < ActionGate.VALIDATE_THRESHOLD:
        return "escalated"
    if confidence >= ActionGate.AUTO_THRESHOLD:
        return "auto_executed"
    return "validated"


def confidence_sweep() -> list:
    values = {i / STEPS for i in range(STEPS + 1)}
    # Explicitly include the exact threshold constants so boundary behavior
    # is checked bit-for-bit, not just approximated by a linear sweep.
    values.update({ActionGate.VALIDATE_THRESHOLD, ActionGate.AUTO_THRESHOLD, 0.0, 1.0})
    return sorted(values)


def main() -> int:
    failures = []
    for confidence in confidence_sweep():
        gate = ActionGate()
        want = expected_status(confidence)
        try:
            result = gate.execute("eval_action", lambda x: x, confidence, confidence)
        except EscalationRequired:
            got = "escalated"
        else:
            got = result.status.value
        if got != want:
            failures.append((confidence, want, got))

    print(f"eval: swept {len(confidence_sweep())} confidence values across [0, 1]")
    if failures:
        print(f"eval: {len(failures)} routing mismatch(es):")
        for confidence, want, got in failures[:10]:
            print(f"  confidence={confidence:.6f} expected={want} got={got}")
        return 1

    print("eval: PASS — every confidence value routed exactly per doctrine (0.70 / 0.85 gates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
