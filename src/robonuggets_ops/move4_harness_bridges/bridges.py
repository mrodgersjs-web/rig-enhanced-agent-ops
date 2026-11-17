"""Move 4 — 6-harness thin bridge generator + session-end edit-delta calibrator.

Ticket #6 deliverables:
1. Thin role-mapping bridge generator from the canonical ``~/.aside/u/0/doctrine/``
   rules for all six tools (aside, autark, nod, orca, omp, prime-agent), preserving
   No Oracle (with the ATS-host carve-out), Gate-D draft-only, and Jev-before-done,
   without duplicating bloated L1 prose (thin = pointers, not copies).
2. Session-end edit-delta calibrator: structured diffs between agent drafts and
   Mike's approved edits/rejections -> linted skill-rule patch proposals (never
   raw L1 appends) + outlier baseline multiplier (views / account_median_views)
   taste-cart updates.
3. CLI entrypoint (--json) + unittest suite + context.json passing verify_gates.py.
"""

from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import statistics
import sys
from typing import Any, Dict, List, Optional, Sequence

if __package__ in (None, ""):  # direct CLI run: `python3 .../bridges.py`
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from robonuggets_ops import dnc_guard

TOOLS: Sequence[str] = ("aside", "autark", "nod", "orca", "omp", "prime-agent")
DEFAULT_DOCTRINE_DIR = pathlib.Path.home() / ".aside" / "u" / "0" / "doctrine"

# Thin role mapping: one line per tool, duty keywords select the canonical rule files.
ROLE_MAP: Dict[str, Dict[str, Any]] = {
    "aside": {
        "role": "operator console and logged-in browser lane",
        "duty_keywords": ("linkedin", "attention", "identity", "safety"),
    },
    "autark": {
        "role": "autonomous desk worker (computer control lane)",
        "duty_keywords": ("gates", "effort", "attention"),
    },
    "nod": {
        "role": "automation pipeline lane (Nod/n8n workflows)",
        "duty_keywords": ("eight-types", "earned-leg", "gates"),
    },
    "orca": {
        "role": "terminal crew execution lanes",
        "duty_keywords": ("code-and-context", "harnesses-and-testing", "jev-and-verification"),
    },
    "omp": {
        "role": "coding agent CLI runtime",
        "duty_keywords": ("code-and-context", "harnesses-and-testing", "jev-and-verification", "build-vs-buy"),
    },
    "prime-agent": {
        "role": "fleet execution runtime for Jake",
        "duty_keywords": ("jake-identity", "jake-direction", "jev-and-verification", "earned-leg-gates"),
    },
}

# The three invariants every bridge must preserve, with their canonical rule ids.
INVARIANT_NO_ORACLE = "no_oracle"
INVARIANT_GATE_D = "gate_d_draft_only"
INVARIANT_JEV = "jev_before_done"

ALLOWED_PATCH_OPS = ("add_check", "tighten_rule", "remove_rule")


def bridge_invariants() -> Dict[str, Any]:
    """The invariant triplet every generated bridge carries (thin, not prose)."""
    return {
        INVARIANT_NO_ORACLE: {
            "rule": "no-oracle",
            "ats_host_carve_out": True,
            "ats_host_domains": list(dnc_guard.ATS_HOST_DOMAINS),
            "blocked_employers": list(dnc_guard.BLOCKED_EMPLOYERS),
        },
        INVARIANT_GATE_D: {
            "rule": "gate-d",
            "mode": "draft_only",
            "auto_send": False,
            "approval": "mike_exact_text",
        },
        INVARIANT_JEV: {
            "rule": "jev-before-done",
            "route_on_done": "JEV",
        },
    }


def _rule_refs(tool: str, doctrine_dir: pathlib.Path) -> List[Dict[str, str]]:
    """Canonical rule pointers for one tool: filenames matched by duty keywords."""
    keywords = ROLE_MAP[tool]["duty_keywords"]
    refs: List[Dict[str, str]] = []
    if not doctrine_dir.is_dir():
        return refs
    for path in sorted(doctrine_dir.glob("*.md")):
        if any(keyword in path.stem for keyword in keywords):
            refs.append({"ref": path.name, "path": str(path)})
    return refs


def generate_bridge(tool: str, doctrine_dir: Optional[pathlib.Path] = None) -> Dict[str, Any]:
    """One thin bridge: role + canonical rule pointers + invariants. No L1 prose."""
    if tool not in ROLE_MAP:
        raise ValueError(f"unknown tool: {tool!r}")
    doctrine = pathlib.Path(doctrine_dir) if doctrine_dir else DEFAULT_DOCTRINE_DIR
    return {
        "tool": tool,
        "role": ROLE_MAP[tool]["role"],
        "canonical_dir": str(doctrine),
        "rule_refs": _rule_refs(tool, doctrine),
        "invariants": bridge_invariants(),
    }


def generate_bridges(doctrine_dir: Optional[pathlib.Path] = None) -> Dict[str, Any]:
    """Thin bridges for all six tools, each linted against the anti-duplication rule."""
    doctrine = pathlib.Path(doctrine_dir) if doctrine_dir else DEFAULT_DOCTRINE_DIR
    bridges = [generate_bridge(tool, doctrine) for tool in TOOLS]
    lint = [lint_bridge(bridge, doctrine) for bridge in bridges]
    return {
        "ok": all(result["ok"] for result in lint),
        "doctrine_dir": str(doctrine),
        "bridges": bridges,
        "lint": lint,
    }


def lint_bridge(bridge: Dict[str, Any], doctrine_dir: Optional[pathlib.Path] = None) -> Dict[str, Any]:
    """Thin-bridge lint: refs resolve, invariants complete, no copied L1 prose."""
    violations: List[str] = []
    doctrine = pathlib.Path(doctrine_dir) if doctrine_dir else pathlib.Path(bridge.get("canonical_dir", DEFAULT_DOCTRINE_DIR))

    for ref in bridge.get("rule_refs", []):
        target = pathlib.Path(ref.get("path", "")) if ref.get("path") else doctrine / ref.get("ref", "")
        if not target.is_file():
            violations.append(f"unresolved_rule_ref:{ref.get('ref', '?')}")

    invariants = bridge.get("invariants", {})
    for name in (INVARIANT_NO_ORACLE, INVARIANT_GATE_D, INVARIANT_JEV):
        if name not in invariants:
            violations.append(f"missing_invariant:{name}")
    if INVARIANT_NO_ORACLE in invariants and not invariants[INVARIANT_NO_ORACLE].get("ats_host_carve_out"):
        violations.append("no_oracle_ats_carve_out_dropped")
    if INVARIANT_GATE_D in invariants and invariants[INVARIANT_GATE_D].get("mode") != "draft_only":
        violations.append("gate_d_draft_only_dropped")

    # Anti-duplication: a bridge may never carry verbatim long prose lines of the rules.
    if doctrine.is_dir():
        serialized = json.dumps(bridge, ensure_ascii=False)
        for path in doctrine.glob("*.md"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if len(line.strip()) > 100 and line.strip() in serialized:
                    violations.append("duplicated_l1_prose")
                    break
            if violations:
                break

    return {"ok": not violations, "tool": bridge.get("tool", "?"), "violations": violations}


def diff_draft_to_approved(draft_text: str, approved_text: str) -> Dict[str, Any]:
    """Structured word-level diff between an agent draft and Mike's approved edit."""
    draft_words = draft_text.split()
    approved_words = approved_text.split()
    matcher = difflib.SequenceMatcher(None, draft_words, approved_words)
    added: List[str] = []
    removed: List[str] = []
    edit_ops = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        edit_ops += 1
        if tag in ("replace", "delete"):
            removed.append(" ".join(draft_words[i1:i2]))
        if tag in ("replace", "insert"):
            added.append(" ".join(approved_words[j1:j2]))
    return {
        "similarity": round(matcher.ratio(), 4),
        "edit_ops": edit_ops,
        "added": added,
        "removed": removed,
        "changed": bool(edit_ops),
    }


def lint_patch_proposal(proposal: Dict[str, Any], *, max_detail_chars: int = 200) -> Dict[str, Any]:
    """Patch-proposal lint: structured ops only, evidenced, never a raw L1 append."""
    violations: List[str] = []
    op = proposal.get("op")
    if op not in ALLOWED_PATCH_OPS:
        violations.append(f"op_not_allowed:{op!r}")
    detail = str(proposal.get("detail", ""))
    if not detail.strip():
        violations.append("empty_detail")
    if len(detail) > max_detail_chars:
        violations.append("detail_too_long")
    if not proposal.get("evidence"):
        violations.append("missing_evidence")
    if not proposal.get("rule_id"):
        violations.append("missing_rule_id")
    return {"ok": not violations, "violations": violations}


def calibrate_edit_deltas(
    drafts: Sequence[Dict[str, Any]],
    decisions: Sequence[Dict[str, Any]],
    *,
    max_detail_chars: int = 200,
) -> Dict[str, Any]:
    """Session-end calibrator: diffs -> per-rule stats -> linted patch proposals.

    drafts:    [{"draft_id", "rule_id", "draft_text"}]
    decisions: [{"draft_id", "decision", "approved_text"?}]
               decision in {"approved", "approved_with_edits", "rejected"}
    """
    errors: List[str] = []
    by_id = {d.get("draft_id"): d for d in drafts}
    deltas: List[Dict[str, Any]] = []
    stats: Dict[str, Dict[str, Any]] = {}

    for decision in decisions:
        draft_id = decision.get("draft_id")
        draft = by_id.get(draft_id)
        if draft is None:
            errors.append(f"decision_without_draft:{draft_id}")
            continue
        verdict = decision.get("decision")
        if verdict not in ("approved", "approved_with_edits", "rejected"):
            errors.append(f"unknown_decision:{verdict!r}")
            continue
        rule_id = draft.get("rule_id", "")
        rule_stats = stats.setdefault(
            rule_id, {"drafts": 0, "approved": 0, "edited": 0, "rejected": 0, "removed_phrases": []}
        )
        rule_stats["drafts"] += 1
        delta: Dict[str, Any] = {"draft_id": draft_id, "rule_id": rule_id, "decision": verdict}
        if verdict == "approved":
            rule_stats["approved"] += 1
        elif verdict == "approved_with_edits":
            rule_stats["edited"] += 1
            diff = diff_draft_to_approved(str(draft.get("draft_text", "")), str(decision.get("approved_text", "")))
            delta["diff"] = diff
            rule_stats["removed_phrases"].extend(p for p in diff["removed"] if p.strip())
        else:  # rejected
            rule_stats["rejected"] += 1
        deltas.append(delta)

    proposals: List[Dict[str, Any]] = []
    proposal_lint: List[Dict[str, Any]] = []
    for rule_id, rule_stats in stats.items():
        total = rule_stats["drafts"]
        rule_stats["rejection_rate"] = round(rule_stats["rejected"] / total, 4) if total else 0.0
        evidence = [d["draft_id"] for d in deltas if d["rule_id"] == rule_id]
        if rule_stats["rejected"]:
            proposals.append(
                {
                    "op": "tighten_rule",
                    "rule_id": rule_id,
                    "detail": f"{rule_stats['rejected']}/{total} drafts rejected; tighten the rule's acceptance checks",
                    "evidence": evidence,
                }
            )
        removed = [p.strip() for p in rule_stats["removed_phrases"] if p.strip()]
        if removed:
            phrases = " | ".join(dict.fromkeys(removed))[:120]
            proposals.append(
                {
                    "op": "add_check",
                    "rule_id": rule_id,
                    "detail": f"drafts consistently deviate here, add a lint check rejecting: {phrases}",
                    "evidence": evidence,
                }
            )
        rule_stats.pop("removed_phrases")

    for proposal in proposals:
        result = lint_patch_proposal(proposal, max_detail_chars=max_detail_chars)
        proposal_lint.append({"rule_id": proposal["rule_id"], **result})

    return {
        "ok": not errors and all(r["ok"] for r in proposal_lint),
        "deltas": deltas,
        "rule_stats": stats,
        "patch_proposals": proposals,
        "proposal_lint": proposal_lint,
        "errors": errors,
    }


def taste_cart_update(
    content_records: Sequence[Dict[str, Any]], *, outlier_threshold: float = 2.0
) -> Dict[str, Any]:
    """Outlier baseline multiplier (views / account_median_views) taste-cart updates."""
    if not content_records:
        return {"ok": False, "reason": "no_content_records", "taste_cart_updates": []}
    views = [float(r.get("views", 0)) for r in content_records]
    median = statistics.median(views)
    if median <= 0:
        return {"ok": False, "reason": "non_positive_account_median", "taste_cart_updates": []}

    records: List[Dict[str, Any]] = []
    updates: List[Dict[str, Any]] = []
    for record in content_records:
        multiplier = round(float(record.get("views", 0)) / median, 4)
        is_outlier = multiplier >= outlier_threshold
        records.append(
            {
                "id": record.get("id"),
                "views": record.get("views"),
                "outlier_multiplier": multiplier,
                "tag": "outlier" if is_outlier else "baseline",
            }
        )
        if is_outlier:
            updates.append(
                {
                    "id": record.get("id"),
                    "update": "pin_to_taste_cart",
                    "outlier_multiplier": multiplier,
                }
            )
    return {
        "ok": True,
        "account_median_views": median,
        "outlier_threshold": outlier_threshold,
        "records": records,
        "taste_cart_updates": updates,
    }


def _load_json(path: str) -> Any:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Move 4 harness bridges + edit-delta calibrator")
    parser.add_argument("command", nargs="?", default="bridges", choices=("bridges", "calibrate", "taste", "all"))
    parser.add_argument("--tool", default="all", help="bridge target tool (default: all six)")
    parser.add_argument("--doctrine-dir", default=None, help="override canonical doctrine dir")
    parser.add_argument("--drafts", default=None, help="JSON file of agent drafts")
    parser.add_argument("--decisions", default=None, help="JSON file of Mike's decisions")
    parser.add_argument("--content", default=None, help="JSON file of content records (views)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    doctrine = pathlib.Path(args.doctrine_dir) if args.doctrine_dir else None
    report: Dict[str, Any] = {}

    if args.command in ("bridges", "all"):
        if args.tool != "all":
            bridge = generate_bridge(args.tool, doctrine)
            report["bridges"] = {"ok": lint_bridge(bridge, doctrine)["ok"], "bridges": [bridge], "lint": [lint_bridge(bridge, doctrine)]}
        else:
            report["bridges"] = generate_bridges(doctrine)
    if args.command in ("calibrate", "all") and args.drafts and args.decisions:
        report["calibration"] = calibrate_edit_deltas(_load_json(args.drafts), _load_json(args.decisions))
    if args.command in ("taste", "all") and args.content:
        report["taste_cart"] = taste_cart_update(_load_json(args.content))

    ok = all(section.get("ok", True) for section in report.values())
    report["ok"] = ok
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for name, section in report.items():
            print(f"{name}: ok={section.get('ok', True)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
