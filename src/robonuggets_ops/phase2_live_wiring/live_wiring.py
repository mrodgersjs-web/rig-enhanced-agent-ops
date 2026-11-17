"""Phase 2 live wiring: read-only Autark ARMS sweep + 6-harness thin bridge bundle.

Deliverables (ticket #9, Phase 2):

1. ``scripts/run_live_product_phase2.py`` (thin CLI wrapper over this module)
   reads the live Autark ``workforce.db`` READ-ONLY, scores every active
   schedule through ``robonuggets_ops.move1_arms_audit``, and writes
   ``reports/live_arms_audit_<date>.json`` + ``reports/live_arms_summary.md``.
2. The thin bridge bundle ``dist/harness_bridges/<tool>.md`` for all six tools
   (aside, autark, nod, orca, omp, prime-agent), rendered from
   ``robonuggets_ops.move4_harness_bridges`` against the canonical
   ``~/.aside/u/0/doctrine/`` rules.

Hard bounds (invariants of this module):

- ``workforce.db`` is opened ``mode=ro`` with ``PRAGMA query_only=1`` and is
  never written: no schedule, cron or launchd entry is created, armed or
  mutated by this code;
- the sweep is a FINDINGS run: ``main`` exits 0 when the sweep completed.
  Blocked armings are findings (the work queue), never a failure of the sweep;
- bridges stay thin (role + rule pointers + the three invariants); no doctrine
  prose is copied into the bundle.

stdlib only — no HTTP client, no sockets, no subprocess.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

if __package__ in (None, ""):  # direct CLI run of this file
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from robonuggets_ops.move1_arms_audit import auditor
from robonuggets_ops.move4_harness_bridges import bridges

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

DEFAULT_DB = "/Users/rig128gb/Library/Application Support/Autark/workforce.db"
DEFAULT_DOCTRINE_DIR = bridges.DEFAULT_DOCTRINE_DIR
DEFAULT_OUT_DIR = "reports"
DEFAULT_BRIDGES_DIR = "dist/harness_bridges"
DEFAULT_DATE = "2026-11-16"
ARM_REPORT_TEMPLATE = "live_arms_audit_{date}.json"
SUMMARY_NAME = "live_arms_summary.md"

# One Autark schedules row -> one move1 routine. Column order of the sweep query.
_SCHEDULE_COLUMNS = ("id", "owner_id", "conversation_id", "task_id", "kind", "title", "spec", "payload")

# Text-scan rules for the routine evidence fields (counts over the payload text).
_ACTION_RE = re.compile(r"(?:Run:|Command:)\s*(.+)")
_READ_VERB_RE = re.compile(r"\b(?:read|cat|tail|load)\b", re.IGNORECASE)
_WRITE_VERB_RE = re.compile(r"\b(?:log|append|write|post)\b", re.IGNORECASE)
_GATE_D_RE = re.compile(r"gate[- ]?d|approval", re.IGNORECASE)
_JEV_RE = re.compile(r"\bjev\b", re.IGNORECASE)
_DELIVERABLE_RE = re.compile(r"[\w./-]+\.(?:md|json|jsonl)")

# Feedback rows count as "applied" under these statuses.
_APPLIED_FEEDBACK_STATUSES = ("applied", "done", "resolved", "fixed")

# Expected finding of the 2026-11-16 sweep: the fleet predates the pre-arm
# contract, so payload.scheduleEvidence is absent everywhere.
EXPECTED_FINDING = (
    "EXPECTED FINDING (not a regression): the active Autark schedules carry no "
    "pre-arm evidence fields (payload.scheduleEvidence: manual_dry_runs_passed, "
    "idempotent_writes, max_retries, token_ceiling, watched_failure_channel), so "
    "every cron/rrule schedule fails move1_arms_audit.validate_schedule and lands "
    "in blocked_armings. The sweep still completes with exit 0; the block list is "
    "the work queue for attaching pre-arm evidence before arming."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value: Any) -> Dict[str, Any]:
    """Best-effort dict from a JSON column (dict passthrough, string parse, else {})."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _text_corpus(payload: Dict[str, Any]) -> str:
    """Concatenate the human-written payload text fields (taskTemplate.notes, note, body)."""
    template = _as_dict(payload.get("taskTemplate"))
    parts = [template.get("notes"), payload.get("note"), payload.get("body")]
    return "\n".join(str(part) for part in parts if part)


def _slot_from_spec(spec: Dict[str, Any]) -> str:
    """slot = hour of spec.window.from: <12 morning, <18 midday, else evening; no window -> morning."""
    window = _as_dict(spec.get("window"))
    raw = window.get("from")
    try:
        hour = int(str(raw).split(":", 1)[0])
    except (TypeError, ValueError):
        return "morning"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "midday"
    return "evening"


def _schedule_block(spec: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """schedule block: derived kind + pre-arm evidence fields, in sync with auditor._ARM_RULES."""
    if spec.get("cron"):
        kind = "cron"
    elif spec.get("everyMs"):
        kind = "rrule"
    else:
        kind = "manual"
    block: Dict[str, Any] = {"kind": kind}
    evidence = _as_dict(payload.get("scheduleEvidence"))
    for field in auditor._ARM_RULES:
        if field in evidence:
            block[field] = evidence[field]
    return block


def schedule_row_to_routine(
    row: dict,
    receipts: list,
    model: Optional[str],
    model_fallback: Optional[str],
) -> dict:
    """Map one Autark ``schedules`` row to a ``move1_arms_audit`` routine dict. Pure.

    ``receipts`` are the newest run ids for the schedule (run receipts -> action_receipts).
    ``model`` is the pinned model from ``agents.model_policy`` and ``model_fallback``
    the model of the latest run — the caller resolves both from the database.
    ``row`` may carry pre-merged feedback counts as ``feedback_log`` /
    ``feedback_applied`` (see ``run_arms``); defaults 0.
    """
    spec = _as_dict(row.get("spec"))
    payload = _as_dict(row.get("payload"))
    template = _as_dict(payload.get("taskTemplate"))
    notes = str(template.get("notes") or "")
    corpus = _text_corpus(payload)
    return {
        "id": row.get("id") or "?",
        "name": str(row.get("title") or template.get("title") or ""),
        "slot": _slot_from_spec(spec),
        "actions": [match.strip() for match in _ACTION_RE.findall(notes)],
        "action_receipts": [str(receipt) for receipt in (receipts or [])],
        "recall_reads": len(_READ_VERB_RE.findall(corpus)),
        "recall_writes": len(_WRITE_VERB_RE.findall(corpus)),
        "model": model,
        "model_fallback": model_fallback,
        "feedback_log": int(row.get("feedback_log") or 0),
        "feedback_applied": int(row.get("feedback_applied") or 0),
        "gate_d": bool(_GATE_D_RE.search(corpus)),
        "jev": bool(_JEV_RE.search(corpus)),
        "deliverables": sorted(set(_DELIVERABLE_RE.findall(corpus))),
        "gate_d_actions": [],  # no approval records exist in workforce.db yet
        "schedule": _schedule_block(spec, payload),
    }


def _open_readonly(db_path: str) -> sqlite3.Connection:
    """Open the Autark database READ-ONLY. This is the only connection mode used."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=1")
    return con


def _model_pair(con: sqlite3.Connection, row: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """model = agents.model_policy pin; model_fallback = model of the latest run."""
    model: Optional[str] = None
    policy_row = con.execute("SELECT model_policy FROM agents WHERE id = ?", (row.get("owner_id"),)).fetchone()
    if policy_row and policy_row[0]:
        policy = _as_dict(policy_row[0])
        model = policy.get("pin") or policy.get("model") or policy.get("primary")
        if model is not None:
            model = str(model)
    fallback_row = con.execute(
        "SELECT model FROM runs WHERE agent_id = ? OR task_id = ? ORDER BY started_at DESC, id DESC LIMIT 1",
        (row.get("owner_id"), row.get("task_id")),
    ).fetchone()
    fallback = str(fallback_row[0]) if fallback_row and fallback_row[0] else None
    return model, fallback


def _action_receipts(con: sqlite3.Connection, row: Dict[str, Any]) -> List[str]:
    """Newest run ids for this schedule's agent/task — the routine's run receipts."""
    rows = con.execute(
        "SELECT id FROM runs WHERE agent_id = ? OR task_id = ? ORDER BY started_at DESC, id DESC LIMIT 5",
        (row.get("owner_id"), row.get("task_id")),
    ).fetchall()
    return [str(run_id) for (run_id,) in rows]


def _feedback_counts(con: sqlite3.Connection, row: Dict[str, Any]) -> Tuple[int, int]:
    """(feedback_log, feedback_applied) counts of feedback rows referencing this schedule.

    Counts only — feedback text is never copied into the reports.
    """
    needles = [str(row[key]) for key in ("id", "task_id", "conversation_id") if row.get(key)]
    logged = 0
    applied = 0
    for feedback_id, context, status in con.execute("SELECT id, context, status FROM feedback"):
        blob = f"{feedback_id} {context or ''}"
        if any(needle in blob for needle in needles):
            logged += 1
            if str(status or "").lower() in _APPLIED_FEEDBACK_STATUSES:
                applied += 1
    return logged, applied


def _active_rows(con: sqlite3.Connection):
    """Stream active schedules rows lazily (the live database is ~800 MB and grows)."""
    query = (
        "SELECT id, owner_id, conversation_id, task_id, kind, title, spec, payload "
        "FROM schedules WHERE active = 1 ORDER BY created_at, id"
    )
    for raw in con.execute(query):
        row = dict(zip(_SCHEDULE_COLUMNS, raw))
        spec = _as_dict(row.get("spec"))
        payload = _as_dict(row.get("payload"))
        row["spec"], row["payload"] = spec, payload
        yield row


def render_summary(report: Dict[str, Any]) -> str:
    """Human-readable sweep summary: expected finding, per-routine lines, digests."""
    metadata = report["metadata"]
    lines = [
        f"# Live ARMS sweep — {metadata['date']} (read-only)",
        "",
        f"- db: {metadata['db_path']} (mode={metadata['mode']}, zero schedule mutations)",
        f"- active schedules scored: {metadata['active_count']}",
        f"- generated: {metadata['generated_at']}",
        "",
        "## Expected finding",
        "",
        EXPECTED_FINDING,
        "",
        "## Routines (ARMS + Gate-D axes, /10)",
        "",
    ]
    for entry in report["routines"]:
        arms = entry["arms"]
        flag = " CHAT-SHAPED" if arms["chat_shaped"] else ""
        if entry["schedule"]["allowed"]:
            verdict = "allowed"
        else:
            verdict = "BLOCKED: " + "; ".join(entry["schedule"]["violations"])
        lines.append(
            f"- {entry['id']} {entry['name']} ARMS={arms['total']}/{auditor.MAX_TOTAL}{flag} "
            f"schedule={verdict}"
        )
    lines += ["", "## Blocked armings", ""]
    blocked = report["blocked_armings"]
    lines.append(f"{len(blocked)} blocked arming(s): " + (", ".join(blocked) if blocked else "none"))
    lines += ["", "## Slot digests (consolidation)", ""]
    for slot, data in report["consolidation"]["slots"].items():
        lines.append(f"- {slot}: {len(data['inbox'])} deliverable(s) from {len(data['routines'])} routine(s)")
    lines.append(f"- gate_d_yes_queue: {len(report['consolidation']['gate_d_yes_queue'])} approval(s)")
    lines += ["", "Exit semantics: 0 = sweep completed; blocked armings are findings, not errors.", ""]
    return "\n".join(lines)


def run_arms(db_path: str = DEFAULT_DB, out_dir: str = DEFAULT_OUT_DIR, date: str = DEFAULT_DATE) -> Dict[str, Any]:
    """Read-only sweep: score active schedules via move1_arms_audit, write both reports."""
    con = _open_readonly(db_path)
    try:
        routines = []
        for row in _active_rows(con):
            model, model_fallback = _model_pair(con, row)
            receipts = _action_receipts(con, row)
            row["feedback_log"], row["feedback_applied"] = _feedback_counts(con, row)
            routines.append(schedule_row_to_routine(row, receipts, model, model_fallback))
    finally:
        con.close()

    audit_report = auditor.audit(routines)
    report: Dict[str, Any] = {
        "metadata": {
            "db_path": str(db_path),
            "mode": "ro",
            "active_count": len(routines),
            "generated_at": _utc_now(),
            "date": str(date),
        },
        "routines": audit_report["routines"],
        "blocked_armings": audit_report["blocked_armings"],
        "consolidation": audit_report["consolidation"],
    }

    dest_dir = pathlib.Path(out_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    report_path = dest_dir / ARM_REPORT_TEMPLATE.format(date=date)
    summary_path = dest_dir / SUMMARY_NAME
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(render_summary(report), encoding="utf-8")
    return {"report": report, "written": [str(report_path), str(summary_path)]}


def run_bridges(doctrine_dir: str = DEFAULT_DOCTRINE_DIR, bridges_dir: str = DEFAULT_BRIDGES_DIR) -> Dict[str, Any]:
    """Materialize the thin bridge bundle: one .md per tool, lint verdict appended."""
    result = bridges.generate_bridges(pathlib.Path(doctrine_dir))
    dest_dir = pathlib.Path(bridges_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for bridge, lint in zip(result["bridges"], result["lint"]):
        body = bridges.render_bridge_md(bridge)
        body += "\n## lint_bridge verdict\n\n```json\n"
        body += json.dumps(lint, sort_keys=True, indent=2)
        body += "\n```\n"
        dest = dest_dir / f"{bridge['tool']}.md"
        dest.write_text(body, encoding="utf-8")
        written.append(str(dest))
    return {"ok": result["ok"], "lint": result["lint"], "written": written}


def _resolve(path_str: str) -> str:
    path = pathlib.Path(path_str)
    return str(path if path.is_absolute() else REPO_ROOT / path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Phase 2 sweep CLI. Exit 0 = sweep completed; blocked armings are findings."""
    parser = argparse.ArgumentParser(
        description="Phase 2 live wiring: read-only Autark ARMS sweep + 6-harness bridge bundle"
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="Autark workforce.db (opened READ-ONLY)")
    parser.add_argument("--doctrine-dir", default=str(DEFAULT_DOCTRINE_DIR), help="canonical doctrine dir")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="report output dir (relative to repo root)")
    parser.add_argument("--bridges-dir", default=DEFAULT_BRIDGES_DIR, help="bridge bundle dir")
    parser.add_argument("--date", default=DEFAULT_DATE, help="report date stamp")
    parser.add_argument("--only", choices=("arms", "bridges"), default=None, help="run just one deliverable")
    args = parser.parse_args(argv)

    written: List[str] = []
    if args.only != "bridges":
        written += run_arms(args.db, _resolve(args.out_dir), args.date)["written"]
    if args.only != "arms":
        written += run_bridges(args.doctrine_dir, _resolve(args.bridges_dir))["written"]
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
