"""Command-line interface for rig-enhanced-agent-ops.

Commands:
    demo                       run the README example end to end and print output
                               (needs no credential: uses RIG_PROOF_SECRET when
                               set, otherwise an ephemeral per-run key)
    verify PATH [--json]       independently verify an exported trail file
    inspect PATH [--json]      summarize an exported trail (counts, statuses, validity)

Exit codes: 0 on success / valid trail, 1 on invalid trail or usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .action_gate import ActionGate, EscalationRequired
from .audit_trail import AuditTrail
from .verifier import Verifier


def _load_secret(env_var: str) -> bytes | None:
    value = os.environ.get(env_var)
    return value.encode("utf-8") if value else None


def cmd_demo(args: argparse.Namespace) -> int:
    """Run the end-to-end example and print what each step produced.

    Prints the four lines the README quotes. The demo needs no credential:
    it uses the operator's key from RIG_PROOF_SECRET when that variable is
    set, and otherwise generates an ephemeral key that dies with the process.
    """
    secret = os.environ.get("RIG_PROOF_SECRET") or os.urandom(32).hex()
    trail = AuditTrail(secret=secret)
    gate = ActionGate(audit_trail=trail)

    def deploy(release_id: str) -> dict:
        return {"deployed": release_id, "region": "us-east-1"}

    result = gate.execute("deploy_release", deploy, "release-42", confidence=0.96)
    print(f"auto action status: {result.status.value}")

    try:
        gate.execute("delete_production_database", deploy, "prod-db", confidence=0.40)
    except EscalationRequired as exc:
        print(f"escalated action: never ran, sealed as packet #{exc.packet.index}")

    report = Verifier(secret=secret).verify_json(trail.to_json())
    print(f"packets sealed: {report.packet_count}")
    print(f"trail valid: {report.valid}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 1
    verifier = Verifier(secret=_load_secret(args.secret_env))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not all(isinstance(row, dict) for row in raw):
            raise ValueError("expected a JSON list of packet objects")
        report = verifier.verify_json(json.dumps(raw))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"error: {path} is not an exported trail: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(report.to_json())
    else:
        state = "VALID" if report.valid else "INVALID"
        print(f"{state}: {report.packet_count} packets checked at {report.checked_at}")
        for finding in report.findings:
            print(f"  - {finding.kind}: {finding.message}")
    return 0 if report.valid else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 1
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not all(isinstance(row, dict) for row in raw):
            raise ValueError("expected a JSON list of packet objects")
        trail = AuditTrail.from_json(json.dumps(raw))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"error: {path} is not an exported trail: {exc}", file=sys.stderr)
        return 1
    by_status: dict = {}
    actions = []
    for packet in trail:
        by_status[packet.status] = by_status.get(packet.status, 0) + 1
        actions.append({"index": packet.index, "action": packet.action, "status": packet.status})
    summary = {
        "file": str(path),
        "packet_count": len(trail),
        "signed": trail.is_signed,
        "by_status": by_status,
        "actions": actions,
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"{path}: {summary['packet_count']} packets, signed={summary['signed']}")
        for status, count in sorted(by_status.items()):
            print(f"  {status}: {count}")
        for action in actions:
            print(f"  #{action['index']} {action['action']} [{action['status']}]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rig-agent-ops",
        description="Verify and inspect tamper-evident agent action trails.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="run the end-to-end example")
    p_demo.set_defaults(func=cmd_demo)

    p_verify = sub.add_parser("verify", help="verify an exported trail file")
    p_verify.add_argument("path", help="exported trail JSON file")
    p_verify.add_argument("--json", action="store_true", help="print the full report as JSON")
    p_verify.add_argument(
        "--secret-env",
        default="RIG_PROOF_SECRET",
        help="environment variable holding the HMAC key (default: RIG_PROOF_SECRET)",
    )
    p_verify.set_defaults(func=cmd_verify)

    p_inspect = sub.add_parser("inspect", help="summarize an exported trail file")
    p_inspect.add_argument("path", help="exported trail JSON file")
    p_inspect.add_argument("--json", action="store_true", help="print the summary as JSON")
    p_inspect.set_defaults(func=cmd_inspect)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
