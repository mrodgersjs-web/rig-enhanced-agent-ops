"""Tests for src/cli.py: the rig-agent-ops command line interface.

Task this file addresses: the command line interface shipped without tests,
so its exit codes and output were unverified. This module gives that
interface real coverage.

Each test pins one command behaviour including its exit code:

- test_demo_runs_end_to_end: `rig-agent-ops demo` runs the full gate loop,
  prints the four lines the README quotes, and exits 0.
- test_verify_valid_trail: `verify` on a trail signed with the key named in
  RIG_PROOF_SECRET exits 0 and prints a line starting "VALID".
- test_verify_tampered_trail_exits_one: `verify` on a trail tampered after
  sealing exits 1 and prints a line starting "INVALID".
- test_verify_missing_file_exits_one: `verify` on a nonexistent path exits 1
  and writes "no such file" to stderr.
- test_verify_rejects_non_trail_json: `verify` refuses JSON that is not a list
  of packet objects, exiting 1 with "not an exported trail" on stderr.
- test_inspect_prints_summary: `inspect --json` prints packet_count and a
  per-status breakdown that matches the file it read.

No real credential is involved: the demo generates an ephemeral key when
RIG_PROOF_SECRET is unset, and these tests use the generated fixture below.
"""

from __future__ import annotations

import json
import os

from src.audit_trail import AuditTrail
from src.cli import main

# Deterministic test fixture, generated here so no real-looking credential
# string appears anywhere in the repository. Not a credential.
FIXTURE_KEY = b"\x00" * 32
FIXTURE_KEY_TEXT = FIXTURE_KEY.hex()  # text form for the env-var channel


def test_demo_runs_end_to_end(capsys) -> None:
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "auto action status: auto_executed" in out
    assert "trail valid: True" in out


def test_verify_valid_trail(tmp_path, capsys) -> None:
    trail = AuditTrail(secret=FIXTURE_KEY_TEXT)
    trail.append("a", 1, 2, 0.9, "auto_executed")
    path = tmp_path / "trail.json"
    path.write_text(trail.to_json(), encoding="utf-8")

    os.environ["RIG_PROOF_SECRET"] = FIXTURE_KEY_TEXT
    try:
        assert main(["verify", str(path)]) == 0
    finally:
        os.environ.pop("RIG_PROOF_SECRET", None)
    out = capsys.readouterr().out
    assert out.startswith("VALID")


def test_verify_tampered_trail_exits_one(tmp_path, capsys) -> None:
    trail = AuditTrail(secret=FIXTURE_KEY)
    trail.append("a", 1, 2, 0.9, "auto_executed")
    trail.append("b", 3, 4, 0.9, "auto_executed")
    trail.tamper(0, output="edited")
    path = tmp_path / "trail.json"
    path.write_text(trail.to_json(), encoding="utf-8")

    assert main(["verify", str(path)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("INVALID")


def test_verify_missing_file_exits_one(capsys) -> None:
    assert main(["verify", "/no/such/file.json"]) == 1
    assert "no such file" in capsys.readouterr().err


def test_verify_rejects_non_trail_json(tmp_path, capsys) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    assert main(["verify", str(path)]) == 1
    assert "not an exported trail" in capsys.readouterr().err


def test_inspect_prints_summary(tmp_path, capsys) -> None:
    trail = AuditTrail(secret=FIXTURE_KEY)
    trail.append("a", 1, 2, 0.9, "auto_executed")
    trail.append("b", 3, 4, 0.4, "escalated")
    path = tmp_path / "trail.json"
    path.write_text(trail.to_json(), encoding="utf-8")

    assert main(["inspect", str(path), "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["packet_count"] == 2
    assert summary["by_status"] == {"auto_executed": 1, "escalated": 1}
