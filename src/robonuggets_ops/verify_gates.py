"""Executable QA gate command for AgentsRoom GTM and Product rooms."""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
OPS_ROOT = pathlib.Path(__file__).resolve().parent
REQUIRED_CONTEXT_KEYS = {"move", "status", "deliverables", "citations", "gates", "jev"}


def run_verification() -> int:
    errors: list[str] = []
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(REPO_ROOT / "test"), "-p", "test_*.py"]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if proc.returncode != 0:
        errors.append(f"unit_tests_failed: {proc.stdout} {proc.stderr}".strip())

    ctx_files = sorted(OPS_ROOT.glob("move*/context.json"))
    for ctx_path in ctx_files:
        try:
            payload = json.loads(ctx_path.read_text())
            missing = REQUIRED_CONTEXT_KEYS - set(payload.keys())
            if missing:
                errors.append(f"{ctx_path.name}: missing {sorted(missing)}")
            if not payload.get("citations"):
                errors.append(f"{ctx_path.name}: empty citations")
        except Exception as exc:
            errors.append(f"{ctx_path}: {exc}")

    report = {
        "ok": not errors,
        "contextArtifacts": [str(p.relative_to(REPO_ROOT)) for p in ctx_files],
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(run_verification())
