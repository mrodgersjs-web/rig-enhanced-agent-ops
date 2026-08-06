"""Tests for the RIG-Enhanced Agent Ops proof-gate stack.

Run with:  pytest test/test_action_gate.py -v
Markers:   -m unit          fast, isolated component tests
           -m integration   full ActionGate -> AuditTrail -> Verifier pipeline
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.action_gate import (
    ActionGate,
    EscalationRequired,
    GateStatus,
    ValidationFailed,
)
from src.audit_trail import GENESIS_HASH, AuditTrail
from src.verifier import Verifier


def echo(value):
    """Deterministic mock agent action: returns what it was given."""
    return {"echo": value}


class CountingAction:
    """Mock agent action that records whether it was ever actually invoked —
    used to prove escalated actions never execute."""

    def __init__(self):
        self.calls = []

    def __call__(self, value):
        self.calls.append(value)
        return {"handled": value}


# ---------------------------------------------------------------------------
# unit: ActionGate routing
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_high_confidence_auto_executes():
    gate = ActionGate()
    result = gate.execute("deploy", echo, "release-42", 0.95)
    assert result.status == GateStatus.AUTO_EXECUTED
    assert result.result == {"echo": "release-42"}
    assert result.proof.status == GateStatus.AUTO_EXECUTED.value


@pytest.mark.unit
def test_auto_threshold_boundary_is_inclusive():
    """confidence == 0.85 (the auto threshold) must AUTO_EXECUTE, not validate."""
    gate = ActionGate()
    result = gate.execute("deploy", echo, "x", ActionGate.AUTO_THRESHOLD)
    assert result.status == GateStatus.AUTO_EXECUTED


@pytest.mark.unit
def test_mid_confidence_validates_without_validator():
    gate = ActionGate()
    result = gate.execute("send_email", echo, "hello@example.com", 0.75)
    assert result.status == GateStatus.VALIDATED
    assert result.proof.confidence == 0.75


@pytest.mark.unit
def test_validate_threshold_boundary_is_inclusive():
    """confidence == 0.70 (the validate threshold) must execute+validate, not escalate."""
    action = CountingAction()
    gate = ActionGate()
    result = gate.execute("notify", action, "x", ActionGate.VALIDATE_THRESHOLD)
    assert result.status == GateStatus.VALIDATED
    assert action.calls == ["x"]


@pytest.mark.unit
def test_low_confidence_escalates_and_never_executes():
    action = CountingAction()
    gate = ActionGate()
    with pytest.raises(EscalationRequired) as exc_info:
        gate.execute("delete_production_database", action, "prod-db", 0.40)

    assert action.calls == [], "escalated action must never be invoked"
    packet = exc_info.value.packet
    assert packet.status == GateStatus.ESCALATED.value
    assert packet.output is None
    assert packet.confidence == 0.40


@pytest.mark.unit
def test_validator_rejects_and_seals_rejected_packet():
    def always_reject(action, action_input, output):
        return False

    action = CountingAction()
    gate = ActionGate(validator=always_reject)
    with pytest.raises(ValidationFailed) as exc_info:
        gate.execute("post_tweet", action, "hot take", 0.80)

    # unlike escalation, the action DID run before validation caught it
    assert action.calls == ["hot take"]
    packet = exc_info.value.packet
    assert packet.status == GateStatus.REJECTED.value
    assert packet.output == {"handled": "hot take"}


@pytest.mark.unit
def test_validator_approves_mid_confidence_action():
    def always_approve(action, action_input, output):
        return True

    gate = ActionGate(validator=always_approve)
    result = gate.execute("refund_charge", echo, "chg_123", 0.72)
    assert result.status == GateStatus.VALIDATED


@pytest.mark.unit
def test_confidence_out_of_range_raises_value_error():
    gate = ActionGate()
    with pytest.raises(ValueError):
        gate.execute("deploy", echo, "x", 1.5)
    with pytest.raises(ValueError):
        gate.execute("deploy", echo, "x", -0.1)


@pytest.mark.unit
def test_invalid_threshold_configuration_raises_value_error():
    with pytest.raises(ValueError):
        ActionGate(auto_threshold=0.5, validate_threshold=0.8)


@pytest.mark.unit
def test_proof_packet_shape():
    gate = ActionGate()
    result = gate.execute("classify_ticket", echo, {"ticket": 99}, 0.9)
    packet = result.proof
    assert packet.action == "classify_ticket"
    assert packet.input == {"ticket": 99}
    assert packet.output == {"echo": {"ticket": 99}}
    assert packet.confidence == 0.9
    assert packet.timestamp  # non-empty ISO-8601 string
    assert packet.hash and len(packet.hash) == 64  # sha256 hexdigest length


# ---------------------------------------------------------------------------
# unit: AuditTrail hash chaining
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_first_packet_chains_to_genesis():
    trail = AuditTrail()
    packet = trail.append("action_a", "in", "out", 0.9, "auto_executed")
    assert packet.prev_hash == GENESIS_HASH
    assert packet.index == 0


@pytest.mark.unit
def test_each_packet_references_previous_hash():
    trail = AuditTrail()
    p0 = trail.append("a", 1, 1, 0.9, "auto_executed")
    p1 = trail.append("b", 2, 2, 0.9, "auto_executed")
    p2 = trail.append("c", 3, 3, 0.9, "auto_executed")

    assert p1.prev_hash == p0.hash
    assert p2.prev_hash == p1.hash
    assert p0.hash != p1.hash != p2.hash  # every hash is distinct


@pytest.mark.unit
def test_clean_trail_verifies_true():
    trail = AuditTrail()
    for i in range(5):
        trail.append(f"action_{i}", i, i * 2, 0.9, "auto_executed")
    ok, reason = trail.verify()
    assert ok is True
    assert reason is None


# ---------------------------------------------------------------------------
# unit + integration: tamper detection (the core requirement)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_tampering_output_breaks_verification():
    trail = AuditTrail()
    trail.append("a", 1, 1, 0.9, "auto_executed")
    trail.append("b", 2, 2, 0.9, "auto_executed")
    trail.append("c", 3, 3, 0.9, "auto_executed")

    trail.tamper(1, output=999)  # attacker rewrites history without resealing

    ok, reason = trail.verify()
    assert ok is False
    assert "packet #1" in reason


@pytest.mark.unit
def test_tampering_is_localized_to_one_finding_via_independent_verifier():
    """A single tampered field should surface as exactly one hash_mismatch,
    not cascade into false chain_break reports for every later packet —
    the hallmark of correctly-implemented block linkage."""
    trail = AuditTrail()
    for i in range(4):
        trail.append(f"action_{i}", i, i, 0.9, "auto_executed")
    trail.tamper(2, confidence=0.01)

    report = Verifier().verify_trail(trail)
    assert report.valid is False
    kinds = [f.kind for f in report.findings]
    assert kinds == ["hash_mismatch"]
    assert report.findings[0].index == 2


@pytest.mark.integration
def test_reordering_packets_breaks_the_chain():
    trail = AuditTrail()
    trail.append("a", 1, 1, 0.9, "auto_executed")
    trail.append("b", 2, 2, 0.9, "auto_executed")
    # swap positions without touching hashes -> prev_hash linkage now lies
    trail._packets[0], trail._packets[1] = trail._packets[1], trail._packets[0]

    ok, reason = trail.verify()
    assert ok is False


# ---------------------------------------------------------------------------
# integration: full pipeline, JSON round-trip, independent verifier, signing
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_full_pipeline_gate_to_independent_verifier():
    trail = AuditTrail(secret="integration-test-secret")
    gate = ActionGate(audit_trail=trail)

    gate.execute("deploy", echo, "v1", 0.99)
    gate.execute("send_notification", echo, "team-channel", 0.78)
    with pytest.raises(EscalationRequired):
        gate.execute("wipe_disk", echo, "sda1", 0.10)

    assert len(trail) == 3

    exported = trail.to_json()
    verifier = Verifier(secret="integration-test-secret")
    report = verifier.verify_json(exported)
    assert report.valid is True
    assert report.packet_count == 3


@pytest.mark.integration
def test_json_round_trip_preserves_verifiability():
    trail = AuditTrail()
    trail.append("a", 1, 1, 0.9, "auto_executed")
    trail.append("b", 2, 2, 0.9, "auto_executed")

    restored = AuditTrail.from_json(trail.to_json())
    ok, reason = restored.verify()
    assert ok is True, reason
    assert [p.hash for p in restored.packets] == [p.hash for p in trail.packets]


@pytest.mark.integration
def test_wrong_signing_key_is_detected_as_signature_mismatch():
    trail = AuditTrail(secret="correct-key")
    trail.append("a", 1, 1, 0.9, "auto_executed")
    trail.append("b", 2, 2, 0.9, "auto_executed")

    honest_report = Verifier(secret="correct-key").verify_trail(trail)
    assert honest_report.valid is True

    dishonest_report = Verifier(secret="wrong-key").verify_trail(trail)
    assert dishonest_report.valid is False
    assert all(f.kind == "signature_mismatch" for f in dishonest_report.findings)


@pytest.mark.integration
def test_verifier_never_touches_audit_trail_internal_state():
    """The verifier must only ever depend on exported dict data — proven by
    feeding it the same content through two independent transports (a
    direct in-process trail vs. its JSON string) and getting identical
    verdicts."""
    trail = AuditTrail(secret="s3cr3t")
    trail.append("a", 1, 1, 0.9, "auto_executed")
    trail.append("b", 2, 2, 0.9, "auto_executed")

    v = Verifier(secret="s3cr3t")
    from_object = v.verify_trail(trail)
    from_json = v.verify_json(trail.to_json())

    assert from_object.valid == from_json.valid is True
    assert from_object.packet_count == from_json.packet_count
