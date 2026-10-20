"""Tests for src/audit_trail.py: the hash chain, packet sealing and export format.

Task this file addresses: src/audit_trail.py had no unit tests, so its hash
chain, packet sealing and export format were unverified. This module gives
that module real coverage.

Each test pins one behaviour of the module under test:

- test_append_seals_and_chains: appending seals every packet with HMAC and
  chains prev_hash from GENESIS_HASH to the previous packet's hash.
- test_unsigned_trail_has_no_signatures: with no key, packets carry no
  signature and the trail reports unsigned, while hashes are still sealed.
- test_env_secret: the RIG_PROOF_SECRET environment variable is used as the
  signing key when the constructor gets none, and the stored signature equals
  the HMAC that key produces.
- test_verify_clean_trail: verify() on an untouched trail returns (True, None).
- test_tamper_is_detected: changing one packet's output after sealing makes
  verify() return (False, reason) with a reason naming the tampering.
- test_roundtrip_json_preserves_chain: to_json() then from_json() keeps packet
  hashes identical and the chain still verifiable.
- test_from_json_rejects_garbage: a non-JSON string raises instead of
  returning a broken trail.
- test_proof_packet_payload_excludes_hash: the signed payload covers content
  fields only, so hash and signature cannot sign themselves.

Signing keys below are generated constants, labelled as test fixtures; no real
credential exists in this file and none is needed to run it.
"""

from __future__ import annotations

import json

import pytest

from src.audit_trail import GENESIS_HASH, AuditTrail, ProofPacket

# Deterministic test fixtures, generated here so no real-looking credential
# string appears anywhere in the repository. Not credentials.
FIXTURE_KEY = b"\x00" * 32
FIXTURE_KEY_TEXT = FIXTURE_KEY.hex()  # text form for the env-var channel


def test_append_seals_and_chains() -> None:
    trail = AuditTrail(secret=FIXTURE_KEY)
    p0 = trail.append("a", {"x": 1}, {"ok": True}, 0.9, "auto_executed")
    p1 = trail.append("b", {"y": 2}, {"ok": False}, 0.5, "escalated")

    assert p0.index == 0 and p1.index == 1
    assert p0.prev_hash == GENESIS_HASH
    assert p1.prev_hash == p0.hash
    assert p0.hash and p1.hash and p0.hash != p1.hash
    assert p0.signature and p1.signature
    assert trail.is_signed is True
    assert len(trail) == 2


def test_unsigned_trail_has_no_signatures() -> None:
    trail = AuditTrail(secret=None)
    packet = trail.append("a", 1, 2, 0.9, "auto_executed")
    assert packet.signature is None
    assert trail.is_signed is False
    assert packet.hash


def test_env_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RIG_PROOF_SECRET", FIXTURE_KEY_TEXT)
    trail = AuditTrail()
    packet = trail.append("a", 1, 2, 0.9, "auto_executed")
    assert packet.signature is not None
    assert packet.signature == packet.compute_signature(FIXTURE_KEY_TEXT.encode("utf-8"))


def test_verify_clean_trail() -> None:
    trail = AuditTrail(secret=FIXTURE_KEY)
    for i in range(5):
        trail.append(f"action-{i}", i, i * 2, 0.9, "auto_executed")
    ok, reason = trail.verify()
    assert ok is True
    assert reason is None
    assert len(trail.packets) == 5


def test_tamper_is_detected() -> None:
    trail = AuditTrail(secret=FIXTURE_KEY)
    for i in range(3):
        trail.append(f"action-{i}", i, i * 2, 0.9, "auto_executed")
    trail.tamper(1, output="tampered")
    ok, reason = trail.verify()
    assert ok is False
    assert reason and "tamper" in reason


def test_roundtrip_json_preserves_chain() -> None:
    trail = AuditTrail(secret=FIXTURE_KEY)
    trail.append("a", 1, 2, 0.9, "auto_executed")
    trail.append("b", 3, 4, 0.4, "escalated")
    restored = AuditTrail.from_json(trail.to_json(), secret=FIXTURE_KEY)
    assert len(restored) == 2
    assert restored.packets[0].hash == trail.packets[0].hash
    assert restored.verify()[0] is True


def test_from_json_rejects_garbage() -> None:
    with pytest.raises((json.JSONDecodeError, KeyError, TypeError, ValueError)):
        AuditTrail.from_json("not json")


def test_proof_packet_payload_excludes_hash() -> None:
    packet = ProofPacket(
        index=0,
        action="a",
        input=1,
        output=2,
        confidence=0.9,
        status="auto_executed",
        timestamp="t",
        prev_hash=GENESIS_HASH,
    )
    payload = packet._payload()
    assert "hash" not in payload and "signature" not in payload
    sealed = packet.seal(FIXTURE_KEY)
    assert sealed.hash == packet.hash
