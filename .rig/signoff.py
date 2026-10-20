#!/usr/bin/env python3
"""RIG L8 layer 8 (sign-off): aggregate every layer's result into a single
gate-report.json. The gate as a whole passes only on a hard AND of all
seven prior layers — sign-off is never a majority vote. If RIG_PROOF_SECRET
is set, the report itself is HMAC-signed with the same primitive the audit
trail uses, so the L8 gate report is exactly as tamper-evident as the
trails it exists to verify.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / ".rig" / "gate-report.json"

LAYER_NAMES = ["syntax", "unit", "integration", "eval", "proof", "gate", "audit"]


def main(argv: list) -> int:
    if len(argv) != len(LAYER_NAMES) + 1:
        sys.stderr.write(
            f"usage: signoff.py <{'> <'.join(LAYER_NAMES)}>  (each arg: 0=pass, nonzero=fail)\n"
        )
        return 2

    results = {name: (code == "0") for name, code in zip(LAYER_NAMES, argv[1:], strict=False)}
    all_pass = all(results.values())

    report = {
        "gate": "L8",
        "repo": "rig-enhanced-agent-ops",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "layers": results,
        "pass": all_pass,
    }

    secret = os.environ.get("RIG_PROOF_SECRET")
    if secret:
        payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
        report["signature"] = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("=" * 72)
    for name in LAYER_NAMES:
        marker = "PASS" if results[name] else "FAIL"
        print(f"  [{marker}] {name}")
    print("=" * 72)
    print(f"L8 sign-off: {'PASS' if all_pass else 'FAIL'} -> {REPORT_PATH.relative_to(ROOT)}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
