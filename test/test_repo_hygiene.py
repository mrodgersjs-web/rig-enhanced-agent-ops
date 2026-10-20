"""Repo hygiene checks: the files a production repo must have, checked on disk.

These assert the polish-wave rules directly from the tracked files, so a future
edit that drops a badge, a timeout, or the code owner fails the test suite.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_NAME = "rig-enhanced-agent-ops"


def _workflow_files() -> list[Path]:
    return sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))


def _job_blocks(text: str) -> dict[str, str]:
    """Split a workflow file into job-name -> job-body, by 2-space indent under jobs:."""
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.rstrip() == "jobs:") + 1
    except StopIteration:
        return {}
    jobs: dict[str, str] = {}
    name = None
    body: list[str] = []
    for ln in lines[start:]:
        if ln.startswith("  ") and ln.rstrip().endswith(":") and not ln.startswith("    "):
            if name is not None:
                jobs[name] = "\n".join(body)
            name = ln.strip().rstrip(":")
            body = []
        elif name is not None:
            body.append(ln)
    if name is not None:
        jobs[name] = "\n".join(body)
    return jobs


def test_codeowners_assigns_repo_owner_everywhere() -> None:
    text = (REPO_ROOT / ".github" / "CODEOWNERS").read_text()
    rules = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    assert rules, "CODEOWNERS must have at least one rule"
    assert rules[0].split() == ["*", "@mrodgersjs-web"]


def test_copilot_instructions_size_and_commands() -> None:
    text = (REPO_ROOT / ".github" / "copilot-instructions.md").read_text()
    assert 500 <= len(text.encode()) <= 8000
    assert "pytest" in text
    assert "ruff check" in text
    assert "conventional" in text.lower()
    assert "truth rule" in text.lower()


def test_readme_badges_footer_and_clone_target() -> None:
    text = (REPO_ROOT / "README.md").read_text()
    assert "github/actions/workflow/status" in text
    assert "rodgersintelligence.com" in text
    assert any(word in text for word in ("pytest", "smoke", "npm test", "node --test"))
    clones = re.findall(r"git clone\s+(\S+)", text)
    assert clones, "README must show a clone command"
    for target in clones:
        assert f"mrodgersjs-web/{REPO_NAME}" in target


def test_workflows_have_timeouts_and_no_continue_on_error() -> None:
    files = _workflow_files()
    assert files, "at least one workflow must exist"
    for path in files:
        text = path.read_text()
        assert "continue-on-error" not in text, f"{path.name} sets continue-on-error"
        jobs = _job_blocks(text)
        assert jobs, f"{path.name} has no jobs"
        for job_name, body in jobs.items():
            assert "timeout-minutes:" in body, f"{path.name}:{job_name} has no timeout-minutes"


def test_test_job_runs_on_push() -> None:
    text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    on_block = text.split("jobs:", 1)[0]
    assert "push:" in on_block and "pull_request:" in on_block
    jobs = _job_blocks(text)
    assert "pytest" in jobs["test"]
