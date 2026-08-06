#!/usr/bin/env bash
# RIG L8 — eight-layer verification gate for rig-enhanced-agent-ops.
#
#   1. syntax       every module compiles
#   2. unit         pytest -m unit  (isolated component behavior)
#   3. integration  pytest -m integration  (full gate -> trail -> verifier)
#   4. eval         confidence-routing table swept across [0, 1]
#   5. proof        every sealed ProofPacket carries the required fields
#   6. gate         the tamper-detection gate itself is proven to fire
#   7. audit        a larger, mixed-outcome trail verifies end to end
#   8. sign-off     hard AND of layers 1-7, written to .rig/gate-report.json
#                   (HMAC-signed if RIG_PROOF_SECRET is set)
#
# Every layer runs regardless of earlier failures — verify.sh reports the
# full picture, not just the first break. Exit code is 0 only if layers
# 1-7 all passed (sign-off, layer 8, mirrors that same hard AND).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

echo "== RIG L8 verify: rig-enhanced-agent-ops =="

if [ "${RIG_SKIP_INSTALL:-0}" != "1" ]; then
  "$PYTHON" -m pip install -q -e ".[dev]" >/dev/null 2>&1 || true
fi

RESULTS=()

run_layer() {
  local name="$1"
  shift
  echo "-- layer: ${name} --"
  if "$@"; then
    echo "[${name}] PASS"
    RESULTS+=("0")
  else
    echo "[${name}] FAIL"
    RESULTS+=("1")
  fi
}

# 1. syntax
run_layer "syntax" "$PYTHON" -m py_compile \
  src/action_gate.py src/audit_trail.py src/verifier.py src/__init__.py \
  test/test_action_gate.py .rig/smoke_runner.py

# 2 + 3. unit / integration (require pytest — installed above if network allows)
if "$PYTHON" -m pytest --version >/dev/null 2>&1; then
  run_layer "unit" "$PYTHON" -m pytest test/test_action_gate.py -m unit -q
  run_layer "integration" "$PYTHON" -m pytest test/test_action_gate.py -m integration -q
else
  echo "-- layer: unit / integration --"
  echo "pytest not available (offline / not installed) — install with: pip install -e .[dev]"
  echo "[unit] FAIL"
  echo "[integration] FAIL"
  RESULTS+=("1" "1")
fi

# 4. eval
run_layer "eval" "$PYTHON" .rig/eval_gate_routing.py

# 5. proof
run_layer "proof" "$PYTHON" .rig/check_proof_shape.py

# 6. gate
run_layer "gate" "$PYTHON" .rig/check_tamper_gate.py

# 7. audit
run_layer "audit" "$PYTHON" .rig/check_audit_scale.py

# 8. sign-off — hard AND of everything above, written to .rig/gate-report.json
"$PYTHON" .rig/signoff.py "${RESULTS[@]}"
exit $?
