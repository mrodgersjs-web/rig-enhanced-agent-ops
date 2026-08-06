#!/usr/bin/env bash
# RIG L10 — self-evolving smoke test.
#
# Runs a mock agent through the ActionGate, checks the AuditTrail chains
# correctly, and verifies tamper detection actually catches tampering.
# State from every run is journaled to .rig/.smoke-journal.json: any
# scenario that has ever failed is permanently hardened (tested more
# thoroughly) on every subsequent run. No pip install required — the
# harness is pure standard library.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

echo "== RIG L10 smoke: rig-enhanced-agent-ops =="
status=0
"$PYTHON" ".rig/smoke_runner.py" || status=$?

if [ "$status" -eq 0 ]; then
  echo "L10 smoke: PASS"
else
  echo "L10 smoke: FAIL (see journal at .rig/.smoke-journal.json for lessons learned)"
fi

exit "$status"
