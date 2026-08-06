"""Step definitions for gated-agent-actions.feature.

Makes the BDD spec executable via `behave` (optional dev dependency —
see pyproject.toml [project.optional-dependencies].dev). This is the same
production code exercised by test/test_action_gate.py; the feature file is
not decorative, it drives src/ directly.

Run with:  behave spec/features/gated-agent-actions.feature
"""
from __future__ import annotations

import sys
from pathlib import Path

from behave import given, then, when

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.action_gate import ActionGate, EscalationRequired, ValidationFailed
from src.audit_trail import GENESIS_HASH, AuditTrail
from src.verifier import Verifier


def _mock_action(action_input):
    return {"handled": action_input}


# --- Background -------------------------------------------------------------


@given("a fresh audit trail")
def step_fresh_trail(context):
    context.trail = AuditTrail()


@given("an action gate wired to that audit trail")
def step_gate_wired(context):
    context.gate = ActionGate(
        audit_trail=context.trail, validator=getattr(context, "validator", None)
    )


@given("the auto-execute threshold is {threshold:f}")
def step_auto_threshold(context, threshold):
    assert context.gate.auto_threshold == threshold


@given("the validate threshold is {threshold:f}")
def step_validate_threshold(context, threshold):
    assert context.gate.validate_threshold == threshold


# --- Single-action scenarios --------------------------------------------------


@given('an agent action "{action}" with confidence {confidence:f}')
def step_single_action(context, action, confidence):
    context.action_name = action
    context.confidence = confidence
    context.action_called = False

    def tracked(action_input):
        context.action_called = True
        return _mock_action(action_input)

    context.action_fn = tracked


@given("a validator that always rejects")
def step_validator_always_rejects(context):
    context.validator = lambda action, action_input, output: False
    context.gate = ActionGate(audit_trail=context.trail, validator=context.validator)


@when("the action gate processes the action")
def step_process_action(context):
    context.exception = None
    try:
        context.result = context.gate.execute(
            context.action_name, context.action_fn, "payload", context.confidence
        )
    except (EscalationRequired, ValidationFailed) as exc:
        context.exception = exc
        context.result = None


@then("the action is executed")
def step_action_executed(context):
    assert context.action_called is True


@then("the action is NEVER executed")
def step_action_never_executed(context):
    assert context.action_called is False


@then('the gate status is "{status}"')
def step_gate_status(context, status):
    if context.result is not None:
        assert context.result.status.value == status
    else:
        assert context.exception.packet.status == status


@then("a proof packet is sealed recording the action, input, output, "
      "confidence, and timestamp")
def step_packet_full_shape(context):
    packet = context.result.proof
    assert packet.action == context.action_name
    assert packet.input == "payload"
    assert packet.output is not None
    assert packet.confidence == context.confidence
    assert packet.timestamp


@then("a proof packet is sealed recording the outcome")
def step_packet_outcome(context):
    assert context.result.proof.hash


@then("the proof packet is appended to the audit trail")
def step_packet_appended(context):
    assert context.result.proof in context.trail.packets


@then("an escalation is raised")
def step_escalation_raised(context):
    assert isinstance(context.exception, EscalationRequired)


@then("a proof packet is sealed recording the escalation itself")
def step_escalation_packet(context):
    packet = context.exception.packet
    assert packet.status == "escalated"
    assert packet.output is None
    assert packet in context.trail.packets


@then("the validation fails")
def step_validation_fails(context):
    assert isinstance(context.exception, ValidationFailed)


@then("the proof packet recording the rejection remains on the audit trail")
def step_rejection_recorded(context):
    packet = context.exception.packet
    assert packet.status == "rejected"
    assert packet in context.trail.packets


# --- Multi-action chain scenarios --------------------------------------------


@given("three agent actions have been processed by the gate")
def step_three_actions(context):
    if not hasattr(context, "trail") or context.trail is None:
        context.trail = AuditTrail()
    if not hasattr(context, "gate") or context.gate is None:
        context.gate = ActionGate(audit_trail=context.trail)
    for i in range(3):
        context.gate.execute(f"action_{i}", _mock_action, f"payload-{i}", 0.9)


@given("the audit trail currently verifies as intact")
def step_trail_currently_intact(context):
    ok, reason = context.trail.verify()
    assert ok, reason


@then("each proof packet's prev_hash equals the previous packet's hash")
def step_chain_linkage(context):
    packets = context.trail.packets
    for i in range(1, len(packets)):
        assert packets[i].prev_hash == packets[i - 1].hash


@then("the first proof packet's prev_hash equals the genesis hash")
def step_genesis_linkage(context):
    assert context.trail.packets[0].prev_hash == GENESIS_HASH


@then("the audit trail verifies as intact")
def step_trail_verifies_intact(context):
    ok, reason = context.trail.verify()
    assert ok, reason


@when("an attacker mutates the output field of the second proof packet "
      "without resealing it")
def step_tamper_second_output(context):
    context.tampered_index = 1
    context.trail.tamper(1, output={"echo": "HACKED"})


@when("an attacker mutates the confidence field of the first proof packet "
      "without resealing it")
def step_tamper_first_confidence(context):
    context.tampered_index = 0
    context.trail.tamper(0, confidence=0.01)


@then("the audit trail no longer verifies as intact")
def step_trail_broken(context):
    ok, reason = context.trail.verify()
    assert ok is False
    context.verify_reason = reason


@then("the verification failure identifies the second proof packet")
def step_failure_identifies_second(context):
    assert "#1" in context.verify_reason


@then("the verification failure identifies the first proof packet")
def step_failure_identifies_first(context):
    assert "#0" in context.verify_reason


@then("no other proof packet is falsely reported as broken")
def step_no_false_cascade(context):
    report = Verifier().verify_trail(context.trail)
    assert len(report.findings) == 1
    assert report.findings[0].index == context.tampered_index


@then("an independent verifier, given only the exported trail, also "
      "detects the tampering")
def step_independent_verifier_detects(context):
    report = Verifier().verify_json(context.trail.to_json())
    assert report.valid is False
    assert any(f.index == context.tampered_index for f in report.findings)


# --- Signed trail scenario ----------------------------------------------------


@given("an audit trail signed with a secret key")
def step_signed_trail(context):
    context.secret = "the-real-secret"
    context.trail = AuditTrail(secret=context.secret)
    context.gate = ActionGate(audit_trail=context.trail)


@when("an independent verifier checks the trail with the wrong key")
def step_verify_wrong_key(context):
    context.wrong_key_report = Verifier(secret="not-the-secret").verify_trail(context.trail)


@when("an independent verifier checks the trail with the correct key")
def step_verify_correct_key(context):
    context.correct_key_report = Verifier(secret=context.secret).verify_trail(context.trail)


@then("the verification fails with a signature mismatch")
def step_signature_mismatch(context):
    assert context.wrong_key_report.valid is False
    assert all(f.kind == "signature_mismatch" for f in context.wrong_key_report.findings)


@then("the verification succeeds")
def step_verification_succeeds(context):
    assert context.correct_key_report.valid is True
