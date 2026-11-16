"""Move 1: ARMS + Gate-D 5-axis routine auditor, dry-run enforcer, 3-slot consolidator.

Scores a routine record (Aside routine or Autark bot) 0-2 on five axes —
Action, Recall, Model, Self-Improvement (ARMS) plus Gate-D/Jev compliance —
for a maximum total of 10. A loop with action == 0 is flagged chat-shaped:
it talks, it does not act.

Axis rubric (deterministic, evidence-based):
  0 = no evidence, 1 = evidence present, 2 = evidence strong (see _AXIS_EVIDENCE).

Schedule gate: cron/RRULE arming is blocked unless the schedule record proves
manual_dry_runs_passed >= 1, idempotent_writes == True, max_retries <= 3,
token_ceiling > 0, and a non-empty watched_failure_channel.

Slot consolidator: merges routine deliverables into one morning/midday/evening
inbox digest per slot and batches every pending Gate-D approval into one
yes-queue for Mike.

CLI: python3 auditor.py [--json] [routines.json]  (stdin when no file given)
Exit 1 when any cron/RRULE schedule fails the pre-arm checks, so it can gate CI.

Sources (cited in context.json):
  src: classroom/hermes-agent-os/m3-the-arms-framework-audit-any-ai-tool
  src: classroom/claude-code-mastery/4-scheduled-tasks
  src: classroom/hermes-agent-os/m5-your-morning-briefing-first-scheduled-task
"""
from __future__ import annotations

import argparse
import json
import sys

SLOTS = ("morning", "midday", "evening")
AXES = ("action", "recall", "model", "self_improvement", "gate_d_jev")
MAX_TOTAL = 10

# Pre-arm checks for cron/RRULE schedules: field -> (predicate, human rule text).
_ARM_RULES = {
    "manual_dry_runs_passed": (lambda v: isinstance(v, int) and v >= 1, "manual_dry_runs_passed >= 1"),
    "idempotent_writes": (lambda v: v is True, "idempotent_writes == True"),
    "max_retries": (lambda v: isinstance(v, int) and v <= 3, "max_retries <= 3"),
    "token_ceiling": (lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0, "token_ceiling > 0"),
    "watched_failure_channel": (lambda v: isinstance(v, str) and v.strip() != "", "watched_failure_channel non-empty"),
}

# (present evidence field, strong evidence field) per axis.
_AXIS_EVIDENCE = {
    "action": ("actions", "action_receipts"),
    "recall": ("recall_reads", "recall_writes"),
    "model": ("model", "model_fallback"),
    "self_improvement": ("feedback_log", "feedback_applied"),
    "gate_d_jev": ("gate_d", "jev"),
}


def _axis_score(routine: dict, present_field: str, strong_field: str) -> int:
    present = bool(routine.get(present_field))
    if not present:
        return 0
    return 2 if bool(routine.get(strong_field)) else 1


def score_arms(routine: dict) -> dict:
    """Score one routine 0-2 per axis; total 0-10; flag action == 0 as chat-shaped."""
    scores = {}
    for axis, (present_field, strong_field) in _AXIS_EVIDENCE.items():
        if axis == "gate_d_jev":
            # Gate-D/Jev is strong only when BOTH gates are wired.
            gate_d = bool(routine.get("gate_d"))
            jev = bool(routine.get("jev"))
            scores[axis] = 2 if (gate_d and jev) else (1 if (gate_d or jev) else 0)
        else:
            scores[axis] = _axis_score(routine, present_field, strong_field)
    scores["total"] = sum(scores[a] for a in AXES)
    scores["chat_shaped"] = scores["action"] == 0
    return scores


def validate_schedule(routine: dict) -> dict:
    """Return {'kind', 'allowed', 'violations'}; block cron/RRULE arming that fails any pre-arm rule."""
    schedule = routine.get("schedule") or {}
    kind = str(schedule.get("kind", "manual")).lower()
    violations = []
    if kind in ("cron", "rrule"):
        for field, (predicate, rule) in _ARM_RULES.items():
            if not predicate(schedule.get(field)):
                violations.append(f"{field}: requires {rule}")
    return {"kind": kind, "allowed": not violations, "violations": violations}


def consolidate_slots(routines: list) -> dict:
    """Merge deliverables into one inbox digest per Mike-time slot + one batched Gate-D yes-queue."""
    slots = {slot: {"routines": [], "inbox": []} for slot in SLOTS}
    gate_d_queue = []
    for routine in routines:
        slot = routine.get("slot")
        if slot not in slots:
            raise ValueError(f"unknown slot {slot!r} (expected one of {SLOTS})")
        slots[slot]["routines"].append(routine.get("id", "?"))
        slots[slot]["inbox"].extend(routine.get("deliverables") or [])
        gate_d_queue.extend(routine.get("gate_d_actions") or [])
    return {
        "slots": slots,
        "gate_d_yes_queue": gate_d_queue,
        "digest_count": sum(1 for s in slots.values() if s["inbox"]),
    }


def audit(routines: list) -> dict:
    """Full Move-1 audit: per-routine ARMS scores, schedule verdicts, slot digests."""
    scored = []
    blocked = []
    for routine in routines:
        schedule = validate_schedule(routine)
        scored.append({
            "id": routine.get("id", "?"),
            "name": routine.get("name", ""),
            "arms": score_arms(routine),
            "schedule": schedule,
        })
        if not schedule["allowed"]:
            blocked.append(routine.get("id", "?"))
    return {
        "routines": scored,
        "blocked_armings": blocked,
        "consolidation": consolidate_slots(routines),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Move 1: ARMS + Gate-D routine auditor")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a text summary")
    parser.add_argument("path", nargs="?", help="routines JSON file (default: stdin)")
    args = parser.parse_args(argv)
    with open(args.path) if args.path else sys.stdin as handle:
        routines = json.load(handle)
    report = audit(routines)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for entry in report["routines"]:
            arms = entry["arms"]
            flag = " CHAT-SHAPED" if arms["chat_shaped"] else ""
            verdict = "ok" if entry["schedule"]["allowed"] else "BLOCKED: " + "; ".join(entry["schedule"]["violations"])
            print(f"{entry['id']} {entry['name']} ARMS+gates={arms['total']}/{MAX_TOTAL}{flag} schedule={verdict}")
        cons = report["consolidation"]
        for slot, data in cons["slots"].items():
            print(f"{slot}: {len(data['inbox'])} deliverable(s) from {len(data['routines'])} routine(s)")
        print(f"gate_d_yes_queue: {len(cons['gate_d_yes_queue'])} approval(s)")
    return 1 if report["blocked_armings"] else 0


if __name__ == "__main__":
    sys.exit(main())
