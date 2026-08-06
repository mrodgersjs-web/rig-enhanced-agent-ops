#!/usr/bin/env python3
"""RIG L8 layer 5 (proof): every sealed ProofPacket must carry the required
evidentiary fields — action, input, output, confidence, timestamp, status,
prev_hash, hash — and its stored hash must match what an independent
recomputation produces. If a secret is configured, the packet must also be
signed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.action_gate import ActionGate  # noqa: E402
from src.audit_trail import AuditTrail  # noqa: E402

REQUIRED_FIELDS = (
    "index", "action", "input", "output", "confidence", "status",
    "timestamp", "prev_hash", "hash",
)


def main() -> int:
    trail = AuditTrail(secret="proof-layer-check")
    gate = ActionGate(audit_trail=trail)
    gate.execute("classify_ticket", lambda x: {"result": x}, {"ticket": 1}, 0.91)
    gate.execute("send_notification", lambda x: {"sent": x}, "channel", 0.77)

    problems = []
    for packet in trail.packets:
        data = packet.to_dict()

        for field_name in REQUIRED_FIELDS:
            if field_name not in data:
                problems.append(f"packet #{packet.index} is missing required field '{field_name}'")

        if not isinstance(data.get("hash"), str) or len(data["hash"]) != 64:
            problems.append(f"packet #{packet.index} hash is not a sha256 hexdigest")

        if data.get("signature") is None:
            problems.append(f"packet #{packet.index} was not signed despite a secret being configured")

        if packet.compute_hash() != packet.hash:
            problems.append(f"packet #{packet.index} stored hash does not match an independent recomputation")

        if not data.get("timestamp"):
            problems.append(f"packet #{packet.index} has no timestamp")

    if problems:
        print("proof: FAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"proof: PASS — {len(trail)} packet(s) carry every required evidentiary field and reseal-match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
