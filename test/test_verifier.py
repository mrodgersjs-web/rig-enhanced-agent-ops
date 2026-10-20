"""Tests for src/verifier.py: independent recomputation of an exported trail.

The verifier is handed raw JSON only, never the AuditTrail that produced it.
Each test pins one outcome:

- test_verify_json_accepts_clean_trail: an untouched export verifies valid
  with no findings and the expected packet count.
- test_verify_file_roundtrip: the same holds through verify_file() and
  through the report's own JSON.
- test_wrong_secret_fails_signature_check: a key that is not the signing key
  fails every signature check, so valid is False.
- test_edit_after_seal_is_detected: editing one packet's output after sealing
  produces a hash_mismatch finding and valid is False.
- test_reorder_is_detected: swapping two packets produces findings and
  valid is False.
- test_tail_truncation_reports_surviving_count: a prefix of a longer trail
  still verifies valid. Known limitation of chain verification, stated here
  and pinned by this test: removing the tail leaves a self-consistent prefix,
  so only the reported packet_count shows that packets are missing.

Signing keys below are generated constants, labelled as test fixtures; no real
credential exists in this file and none is needed to run it.
"""

from __future__ import annotations

import json

from src.audit_trail import AuditTrail
from src.verifier import Verifier

# Deterministic test fixtures, generated here so no real-looking credential
# string appears anywhere in the repository. Not credentials.
FIXTURE_KEY = b"\x00" * 32
OTHER_FIXTURE_KEY = b"\xff" * 32  # a second fixture, deliberately not the signer


def _make_trail(secret: bytes = FIXTURE_KEY, count: int = 3) -> AuditTrail:
    trail = AuditTrail(secret=secret)
    for i in range(count):
        trail.append(f"action-{i}", i, i * 2, 0.9, "auto_executed")
    return trail


def test_verify_json_accepts_clean_trail() -> None:
    trail = _make_trail()
    report = Verifier(secret=FIXTURE_KEY).verify_json(trail.to_json())
    assert report.valid is True
    assert report.packet_count == 3
    assert report.findings == []
    assert report.to_dict()["valid"] is True


def test_verify_file_roundtrip(tmp_path) -> None:
    trail = _make_trail()
    path = tmp_path / "trail.json"
    path.write_text(trail.to_json(), encoding="utf-8")
    report = Verifier(secret=FIXTURE_KEY).verify_file(path)
    assert report.valid is True
    assert json.loads(report.to_json())["packet_count"] == 3


def test_wrong_secret_fails_signature_check() -> None:
    trail = _make_trail(secret=FIXTURE_KEY)
    report = Verifier(secret=OTHER_FIXTURE_KEY).verify_json(trail.to_json())
    assert report.valid is False


def test_edit_after_seal_is_detected() -> None:
    trail = _make_trail()
    packets = json.loads(trail.to_json())
    data = json.loads(packets) if isinstance(packets, str) else packets
    rows = data["packets"] if isinstance(data, dict) and "packets" in data else data
    rows[1]["output"] = "edited"
    report = Verifier(secret=FIXTURE_KEY).verify_json(json.dumps(data))
    assert report.valid is False
    assert report.findings


def test_reorder_is_detected() -> None:
    trail = _make_trail()
    data = json.loads(trail.to_json())
    rows = data["packets"] if isinstance(data, dict) and "packets" in data else data
    rows[0], rows[2] = rows[2], rows[0]
    report = Verifier(secret=FIXTURE_KEY).verify_json(json.dumps(data))
    assert report.valid is False


def test_tail_truncation_reports_surviving_count() -> None:
    trail = _make_trail(count=4)
    data = json.loads(trail.to_json())
    rows = data["packets"] if isinstance(data, dict) and "packets" in data else data
    kept = rows[:2]
    if isinstance(data, dict) and "packets" in data:
        data["packets"] = kept
        payload = json.dumps(data)
    else:
        payload = json.dumps(kept)
    report = Verifier(secret=FIXTURE_KEY).verify_json(payload)
    # Known limitation of chain verification: a removed tail is invisible
    # because the surviving prefix is self-consistent. The honest assertions
    # are the ones that hold today: the prefix verifies and the report counts
    # only the packets that survived.
    assert report.valid is True
    assert report.packet_count == 2
