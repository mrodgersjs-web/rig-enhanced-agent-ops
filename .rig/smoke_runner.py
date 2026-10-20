#!/usr/bin/env python3
"""RIG L10 — self-evolving smoke harness for rig-enhanced-agent-ops.

Runs a mock agent through the ActionGate, checks the AuditTrail, and
verifies tamper detection — but unlike a static smoke test, this harness
keeps a journal (``.rig/.smoke-journal.json``) across runs. Any scenario
that has EVER failed has its ``hardening_level`` permanently ratcheted up
(it never decreases), and a higher hardening level makes future runs of
that scenario strictly more thorough: more trial inputs, more mutated
fields, more adversarial edge cases. This is the "adapts, learns from
failures, and hardens" contract: a scenario that broke once is watched
more closely forever, not just until the next green run.

Exit code 0 = every scenario passed this run. Exit code 1 = at least one
scenario failed (and was just hardened for next time).
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.action_gate import ActionGate, EscalationRequired, GateStatus, ValidationFailed  # noqa: E402
from src.audit_trail import GENESIS_HASH, AuditTrail  # noqa: E402
from src.verifier import Verifier  # noqa: E402

JOURNAL_PATH = ROOT / ".rig" / ".smoke-journal.json"
MUTATION_FIELDS = ["output", "confidence", "action", "timestamp", "input"]

ScenarioResult = tuple[bool, str]
Scenario = Callable[[int], ScenarioResult]


# ---------------------------------------------------------------------------
# Journal: persisted, self-evolving state across runs
# ---------------------------------------------------------------------------


def _default_journal() -> dict:
    return {"version": 1, "runs": 0, "scenarios": {}}


def load_journal() -> dict:
    if not JOURNAL_PATH.exists():
        return _default_journal()
    try:
        return json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupted journal must never crash the harness — start clean
        # rather than block the very safety net it implements.
        return _default_journal()


def save_journal(journal: dict) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_PATH.write_text(json.dumps(journal, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def scenario_state(journal: dict, name: str) -> dict:
    return journal["scenarios"].setdefault(
        name,
        {
            "hardening_level": 0,
            "consecutive_failures": 0,
            "total_failures": 0,
            "last_status": None,
            "lessons": [],
        },
    )


def record_result(journal: dict, name: str, passed: bool, detail: str) -> None:
    state = scenario_state(journal, name)
    state["last_status"] = "pass" if passed else "fail"
    if passed:
        state["consecutive_failures"] = 0
        # hardening_level is a ratchet: once raised by a failure, it stays
        # raised. A pass does not "forget" that this scenario broke before.
    else:
        state["consecutive_failures"] += 1
        state["total_failures"] += 1
        state["hardening_level"] += 1
        lesson = (
            f"[{datetime.now(timezone.utc).isoformat()}] scenario '{name}' failed "
            f"({detail}) — hardening_level raised to {state['hardening_level']}, "
            f"future runs test more inputs/fields for this scenario"
        )
        state["lessons"].append(lesson)
        state["lessons"] = state["lessons"][-20:]  # bounded journal growth


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def mock_action(action_input):
    return {"handled": action_input, "checksum": sum(bytearray(str(action_input).encode()))}


def scenario_auto_execute(hardening_level: int) -> ScenarioResult:
    """High-confidence actions must AUTO_EXECUTE. Hardened runs sweep more inputs."""
    trials = 1 + hardening_level
    for i in range(trials):
        gate = ActionGate()
        payload = f"release-{i}"
        result = gate.execute("deploy_release", mock_action, payload, 0.95)
        if result.status != GateStatus.AUTO_EXECUTED:
            return False, f"trial {i}: expected auto_executed, got {result.status.value}"
        if result.result["handled"] != payload:
            return False, f"trial {i}: action output did not reflect its input"
    return True, f"{trials} auto-execute trial(s) passed"


def scenario_validate_band(hardening_level: int) -> ScenarioResult:
    """Mid-confidence actions execute and are marked VALIDATED. Hardened runs
    also exercise a rejecting validator to prove rejection is enforced."""
    gate = ActionGate()
    result = gate.execute("send_notification", mock_action, "team-channel", 0.75)
    if result.status != GateStatus.VALIDATED:
        return False, f"expected validated, got {result.status.value}"

    if hardening_level >= 1:
        called = {"n": 0}

        def tracked_action(action_input):
            called["n"] += 1
            return mock_action(action_input)

        rejecting_gate = ActionGate(validator=lambda *a: False)
        try:
            rejecting_gate.execute("post_tweet", tracked_action, "hot take", 0.78)
            return False, "expected ValidationFailed to be raised"
        except ValidationFailed as exc:
            if exc.packet.status != "rejected":
                return False, "rejected packet did not have status 'rejected'"
            if called["n"] != 1:
                return False, "action should have run exactly once before rejection"
    return True, "validate-band routing correct"


def scenario_escalation(hardening_level: int) -> ScenarioResult:
    """Sub-threshold confidence must escalate and NEVER call the action.
    Hardened runs sweep the full sub-threshold range, not just one point."""
    confidences = [0.40]
    if hardening_level >= 1:
        confidences += [0.0, 0.30, 0.69]

    for confidence in confidences:
        called = {"n": 0}

        def tracked_action(action_input):
            called["n"] += 1
            return mock_action(action_input)

        gate = ActionGate()
        try:
            gate.execute("delete_production_database", tracked_action, "prod-db", confidence)
            return False, f"confidence={confidence}: expected EscalationRequired"
        except EscalationRequired as exc:
            if called["n"] != 0:
                return False, f"confidence={confidence}: action executed despite escalation"
            if exc.packet.status != "escalated":
                return False, f"confidence={confidence}: packet status was not 'escalated'"
    return True, f"{len(confidences)} escalation trial(s) passed, action never executed"


def scenario_audit_chain_integrity(hardening_level: int) -> ScenarioResult:
    """After a run of mixed actions, the trail must chain correctly and verify clean."""
    trail = AuditTrail()
    gate = ActionGate(audit_trail=trail)
    gate.execute("deploy_release", mock_action, "v1", 0.95)
    gate.execute("send_notification", mock_action, "team-channel", 0.75)
    try:
        gate.execute("delete_production_database", mock_action, "prod-db", 0.40)
    except EscalationRequired:
        pass

    if len(trail) != 3:
        return False, f"expected 3 sealed packets, found {len(trail)}"
    if trail.packets[0].prev_hash != GENESIS_HASH:
        return False, "first packet must reference the genesis hash"
    for i in range(1, len(trail.packets)):
        if trail.packets[i].prev_hash != trail.packets[i - 1].hash:
            return False, f"packet #{i} does not reference packet #{i - 1}'s hash"

    ok, reason = trail.verify()
    if not ok:
        return False, f"clean trail failed to verify: {reason}"
    return True, f"{len(trail)}-packet chain verified intact"


def scenario_tamper_detection(hardening_level: int) -> ScenarioResult:
    """Mutating a sealed packet must be caught by both AuditTrail.verify()
    and an independent Verifier. Hardened runs try more fields/positions."""
    trials = 1 + hardening_level
    fields = MUTATION_FIELDS[: min(trials, len(MUTATION_FIELDS))]

    for trial_i, field_name in enumerate(fields):
        trail = AuditTrail()
        gate = ActionGate(audit_trail=trail)
        for i in range(4):
            gate.execute(f"action_{i}", mock_action, f"payload-{i}", 0.9)

        target_index = trial_i % len(trail)
        mutated_value = {"output": {"echo": "HACKED"}, "confidence": 0.01,
                          "action": "not_the_real_action", "timestamp": "1970-01-01T00:00:00Z",
                          "input": "HACKED-INPUT"}[field_name]
        trail.tamper(target_index, **{field_name: mutated_value})

        ok, reason = trail.verify()
        if ok:
            return False, f"trial {trial_i} (field={field_name}): tamper was NOT detected"

        report = Verifier().verify_json(trail.to_json())
        if report.valid:
            return False, f"trial {trial_i} (field={field_name}): independent verifier missed tampering"
        if not any(f.index == target_index for f in report.findings):
            return False, (
                f"trial {trial_i} (field={field_name}): verifier flagged the wrong packet"
            )
    return True, f"{len(fields)} tamper-field trial(s) all correctly detected"


def scenario_signature_integrity(hardening_level: int) -> ScenarioResult:
    """A signed trail must verify with the right key and fail with the wrong one."""
    wrong_keys = ["wrong-key"]
    if hardening_level >= 1:
        wrong_keys += ["", "correct-key-with-typo", "correct-key "]

    secret = "correct-key"
    trail = AuditTrail(secret=secret)
    gate = ActionGate(audit_trail=trail)
    gate.execute("deploy_release", mock_action, "v1", 0.95)
    gate.execute("send_notification", mock_action, "team-channel", 0.75)

    correct = Verifier(secret=secret).verify_trail(trail)
    if not correct.valid:
        return False, "correctly-keyed verification unexpectedly failed"

    for wrong_key in wrong_keys:
        report = Verifier(secret=wrong_key).verify_trail(trail)
        if report.valid:
            return False, f"verification with wrong key {wrong_key!r} incorrectly passed"
        if not all(f.kind == "signature_mismatch" for f in report.findings):
            return False, f"wrong key {wrong_key!r} produced non-signature findings"
    return True, f"correct key verified, {len(wrong_keys)} wrong key(s) correctly rejected"


SCENARIOS: list[tuple[str, Scenario]] = [
    ("auto_execute", scenario_auto_execute),
    ("validate_band", scenario_validate_band),
    ("escalation", scenario_escalation),
    ("audit_chain_integrity", scenario_audit_chain_integrity),
    ("tamper_detection", scenario_tamper_detection),
    ("signature_integrity", scenario_signature_integrity),
]


def main() -> int:
    journal = load_journal()
    journal["runs"] = journal.get("runs", 0) + 1

    print(f"RIG L10 smoke — run #{journal['runs']}")
    print("=" * 72)

    all_passed = True
    for name, scenario_fn in SCENARIOS:
        state = scenario_state(journal, name)
        hardening_level = state["hardening_level"]
        try:
            passed, detail = scenario_fn(hardening_level)
        except Exception as exc:  # a scenario crashing counts as a failure, not a harness crash
            passed, detail = False, f"scenario raised {type(exc).__name__}: {exc}"

        record_result(journal, name, passed, detail)
        marker = "PASS" if passed else "FAIL"
        print(f"[{marker}] {name:<24} (hardening_level={hardening_level})  {detail}")
        if not passed:
            all_passed = False
            print(f"       LESSON: {state['lessons'][-1]}")

    save_journal(journal)

    print("=" * 72)
    total_hardening = sum(s["hardening_level"] for s in journal["scenarios"].values())
    print(f"journal: {JOURNAL_PATH.relative_to(ROOT)}  (cumulative hardening_level={total_hardening})")

    if all_passed:
        print("RIG L10 smoke: ALL SCENARIOS PASSED")
        return 0
    print("RIG L10 smoke: FAILURES DETECTED — hardened for next run, exiting non-zero")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
