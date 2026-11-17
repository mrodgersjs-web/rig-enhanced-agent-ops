"""Phase 2 live GTM dry-run pack (GTM Room) — zero sends, zero writes, zero calls.

Loads ``/Users/rig128gb/.applypilot/do-not-contact.json`` READ-ONLY, checks the
sender STOP lane through ``dnc_guard.check_sender_lane_ready``, runs the Move 2
Nod/Twenty dry-run matrix (Oracle blocked, Matt Colmia blocked even with a blank
company, UCSF & JPMorganChase on *.oraclecloud.com allowed via the ATS-host
carve-out, vendor pitch quarantined, Twenty terminal states preserved per
task_eae7zr9j), exports ``dist/nod_twenty_reply_v1.workflow.json`` (ready-to-import
Nod/Twenty workflow, draft-only envelope), runs the Move 3 sample bundle into
``dist/gtm_pack_sample/``, and writes ``reports/live_gtm_dryrun_2026-11-16.json``.

Hard bounds (invariants of this script):
- the do-not-contact rule file is opened "r" and never written;
- sends=0, twenty_writes=0 (staged ``upsert_contact`` only), clients_ai_calls=0
  (``http://127.0.0.1:3211`` is a NON-SEND surface and is never called);
- the STOP brake + sha12 exact-text approval guard lives ONLY in
  ``dnc_guard.check_sender_lane_ready`` (reached via ``sender_lane_state``);
- every prospect/reply/teaser path runs
  ``src.robonuggets_ops.dnc_guard.evaluate_outreach_target`` first.

stdlib only — no HTTP client, no sockets, no subprocess.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from robonuggets_ops import dnc_guard  # noqa: E402
from robonuggets_ops.move2_nod_twenty_reply import pipeline  # noqa: E402
from robonuggets_ops.move3_gtm_teaser_tune import pack  # noqa: E402

DNC_RULE_FILE = "/Users/rig128gb/.applypilot/do-not-contact.json"
CLIENTS_AI_ENDPOINT = "http://127.0.0.1:3211"  # NON-SEND: never called
TERMINAL_STATES = ("won", "lost", "do_not_contact")
EXPORT_SCHEMA_VERSION = "move2.nod-twenty-reply.export.v1"
EXPORT_REL_PATH = "dist/nod_twenty_reply_v1.workflow.json"
REPORT_REL_PATH = "reports/live_gtm_dryrun_2026-11-16.json"
SAMPLE_DIR_REL_PATH = "dist/gtm_pack_sample"
OPT_OUT_LINE = "If this isn't relevant, reply STOP and I won't follow up."
DNC_ENFORCED_BY = "src/robonuggets_ops/dnc_guard.py:evaluate_outreach_target"

# Sample bundle target: UCSF on *.oraclecloud.com — allowed only under the
# ATS-host carve-out, so every generated draft proves the gate ran.
SAMPLE_PROSPECT = {
    "company": "UCSF",
    "contact_name": "Jordan Lee",
    "url": "https://ucsf.fa.us2.oraclecloud.com/hcmUI",
    "recipient_domain": "",
}
SAMPLE_FINDING = "invoice data is re-keyed by hand between the portal and the ledger every week"
SAMPLE_EVIDENCE = "the weekly ops report shows a six-hour manual reconciliation block"
BLEED_INPUTS = {
    "hours_per_week": 6,
    "loaded_hourly_rate": 120,
    "errors_per_week": 3,
    "cost_per_error": 40,
    "lost_leads_per_week": 2,
    "value_per_lead": 500,
}
TUNE_INPUTS = {
    "what_shipped": "Weekly ops-report workflow",
    "purchase_metric": "hours_returned",
    "metric_value": 12,
    "dollar_value": 3600,
    "paid": 2500,
    "received": 3600,
    "expansion_suggestion": "Extend the workflow to invoice reconciliation next month",
}
VENDOR_PITCH_TEXT = (
    "Hello. We are VendorCo, an award-winning agency with premium solutions for growth. "
    "Our package prices are unbeatable this month. "
    "Visit our website to learn why hundreds of firms choose us."
)

PLANTED_FAILURES = [
    {
        "name": "matt_colmia_blank_company_without_person_check",
        "mutation": "dnc_guard.BLOCKED_PEOPLE emptied (the person check removed)",
        "expected_red": "matrix row 'mattcolmia_blank_company' fails (pass=false) — the blank company leaves no other block",
        "green_when": "the person check is present (shipped dnc_guard)",
        "proven_in": "test/test_phase2_live_gtm.py::TestPlantedFailures::test_mattcolmia_person_check_is_load_bearing",
    },
    {
        "name": "export_without_preserve_terminal_states",
        "mutation": "twenty.preserve_terminal_states dropped from a copied export",
        "expected_red": "validate_export fails (valid=false) naming preserve_terminal_states",
        "green_when": "the shipped export carries twenty.preserve_terminal_states [won,lost,do_not_contact]",
        "proven_in": "test/test_phase2_live_gtm.py::TestPlantedFailures::test_export_dropping_preserve_terminal_states_goes_red",
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(dest: Path, payload: dict[str, Any]) -> dict[str, Any]:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def _git_head() -> str:
    """Resolve HEAD with stdlib file reads only (no subprocess)."""
    try:
        head = (REPO_ROOT / ".git" / "HEAD").read_text().strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            return (REPO_ROOT / ".git" / ref).read_text().strip()
        return head
    except OSError:
        return "unknown"


def load_do_not_contact(path: str = DNC_RULE_FILE) -> dict[str, Any]:
    """Load the do-not-contact rule file READ-ONLY. It is never written."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def twenty_stage_action(lifecycle_state: str) -> dict[str, Any]:
    """Stage the Twenty CRM action for one lifecycle state (task_eae7zr9j).

    Terminal states (won/lost/do_not_contact) are preserved: no mutation is ever
    staged over them. Everything else stages a write-disabled upsert_contact.
    """
    state = (lifecycle_state or "").strip().lower().replace("-", "_")
    if state in TERMINAL_STATES:
        return {"mutate": False, "reason": "terminal_state_preserved"}
    return {"mutate": True, "operation": "upsert_contact", "staged": True, "write_enabled": False}


def sender_lane_state(
    *,
    template_sha12: str = "",
    approved_sha12: str = "",
    stop_file_path: str | None = None,
) -> dict[str, Any]:
    """Sender lane posture — delegates to dnc_guard.check_sender_lane_ready.

    The only home of the STOP brake + sha12 guard is
    ``dnc_guard.check_sender_lane_ready``; this wrapper asserts the non-send
    invariant (auto_send is always False) and returns its verdict verbatim.
    """
    state = dict(
        dnc_guard.check_sender_lane_ready(
            stop_file_path=stop_file_path,
            template_sha12=template_sha12,
            approved_sha12=approved_sha12,
        )
    )
    assert state.get("auto_send") is False, "rooms/senders never auto-send"
    return state


def _normalize_gate_reason(verdict: dict[str, Any], *, company: str, person_name: str) -> str:
    """Translate a guard verdict into the dry-run matrix's expected wording."""
    if verdict.get("allowed"):
        return "allowed"
    reason = str(verdict.get("reason", ""))
    kind = reason.split(":", 1)[0] if ":" in reason else reason
    if kind == "blocked_person":
        return f"blocked: person '{person_name}' is on the do-not-contact person list"
    if kind == "blocked_employer":
        return f"blocked: employer '{company}' is on the do-not-contact employer list"
    if kind == "blocked_domain":
        return f"blocked: domain '{reason.split(':', 1)[1]}' is on the do-not-contact domain list"
    return reason


def _row(name: str, input_: dict[str, Any], expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "input": input_, "expected": expected, "actual": actual, "pass": expected == actual}


def run_dry_run_matrix(*, dnc: dict[str, Any]) -> list[dict[str, Any]]:
    """Seven dry-run rows (name/input/expected/actual/pass). Zero network, zero writes."""
    rows: list[dict[str, Any]] = []
    blocked_companies = [str(c).lower() for c in dnc.get("blocked_companies", {}).get("companies", [])]
    dnc_people = [str(p).lower() for p in dnc.get("people", [])]

    # 1. Oracle (employer list) blocked.
    verdict = dnc_guard.evaluate_outreach_target(
        company="Oracle", person_name="Jane Recruiter", url="", recipient_domain=""
    )
    rows.append(
        _row(
            "oracle_blocked",
            {
                "call": "dnc_guard.evaluate_outreach_target(company='Oracle', person_name='Jane Recruiter')",
                "rule_file_blocks_company": any("oracle" in c for c in blocked_companies),
            },
            {
                "allowed": False,
                "reason": "blocked: employer 'Oracle' is on the do-not-contact employer list",
                "atsHostCarveOut": False,
            },
            {
                "allowed": bool(verdict.get("allowed")),
                "reason": _normalize_gate_reason(verdict, company="Oracle", person_name="Jane Recruiter"),
                "atsHostCarveOut": bool(verdict.get("atsHostCarveOut", False)),
            },
        )
    )

    # 2. Matt Colmia blocked even with a blank company (person list).
    verdict = dnc_guard.evaluate_outreach_target(
        company="", person_name="Matt Colmia", url="", recipient_domain=""
    )
    rows.append(
        _row(
            "mattcolmia_blank_company",
            {
                "call": "dnc_guard.evaluate_outreach_target(company='', person_name='Matt Colmia')",
                "rule_file_lists_person": "matt colmia" in dnc_people,
            },
            {
                "allowed": False,
                "reason": "blocked: person 'Matt Colmia' is on the do-not-contact person list",
                "atsHostCarveOut": False,
            },
            {
                "allowed": bool(verdict.get("allowed")),
                "reason": _normalize_gate_reason(verdict, company="", person_name="Matt Colmia"),
                "atsHostCarveOut": bool(verdict.get("atsHostCarveOut", False)),
            },
        )
    )

    # 3 & 4. UCSF / JPMorganChase on *.oraclecloud.com allowed via ATS carve-out.
    for name, company, url in (
        ("ucsf_ats", "UCSF", "https://ucsf.fa.us2.oraclecloud.com/hcmUI"),
        ("jpmc_ats", "JPMorganChase", "https://jpmc.fa.oraclecloud.com/hcmUI"),
    ):
        verdict = dnc_guard.evaluate_outreach_target(
            company=company, person_name="Jordan Lee", url=url, recipient_domain=""
        )
        rows.append(
            _row(
                name,
                {"call": f"dnc_guard.evaluate_outreach_target(company='{company}', url='{url}')"},
                {"allowed": True, "reason": "allowed", "atsHostCarveOut": True},
                {
                    "allowed": bool(verdict.get("allowed")),
                    "reason": _normalize_gate_reason(verdict, company=company, person_name="Jordan Lee"),
                    "atsHostCarveOut": bool(verdict.get("atsHostCarveOut", False)),
                },
            )
        )

    # 5. ATS host without an employer field is refused (employer decides).
    verdict = dnc_guard.evaluate_outreach_target(
        company="", person_name="Jordan Lee", url="https://x.fa.oraclecloud.com/hcmUI", recipient_domain=""
    )
    rows.append(
        _row(
            "ats_missing_employer",
            {"call": "dnc_guard.evaluate_outreach_target(company='', url='https://x.fa.oraclecloud.com/hcmUI')"},
            {"allowed": False, "reason": "ats_host_missing_employer", "atsHostCarveOut": False},
            {
                "allowed": bool(verdict.get("allowed")),
                "reason": _normalize_gate_reason(verdict, company="", person_name="Jordan Lee"),
                "atsHostCarveOut": bool(verdict.get("atsHostCarveOut", False)),
            },
        )
    )

    # 6. Vendor pitch (no reply keywords) quarantined: manual_review, no send.
    record = pipeline.classify_reply(
        VENDOR_PITCH_TEXT,
        reply_id="dryrun-vendor-pitch",
        thread_id="dryrun-thread",
        sender_name="Pat Vendor",
        sender_company="VendorCo",
        sender_email="pat@vendorco.example",
        url="",
    )
    brief = pipeline.build_contact_brief(
        record, name="Pat Vendor", company="VendorCo", email="pat@vendorco.example", url=""
    )
    card = pipeline.build_gate_d_card(record, brief, sender_stop_file="/nonexistent/rig-stop-brake-does-not-exist")
    rows.append(
        _row(
            "vendor_pitch_quarantined",
            {
                "call": "classify_reply(vendor pitch) -> build_contact_brief -> build_gate_d_card",
                "reply_keywords_hit": [s for s in record["signals"] if s != "no_keyword_signal"],
            },
            {
                "reply_class": "other",
                "next_action": "manual_review",
                "send_enabled": False,
                "crm_staged": True,
                "write_enabled": False,
            },
            {
                "reply_class": record["reply_class"],
                "next_action": brief["next_action"],
                "send_enabled": card["send_enabled"],
                "crm_staged": brief["crm"]["staged"],
                "write_enabled": brief["write_enabled"],
            },
        )
    )

    # 7. Twenty terminal states preserved (task_eae7zr9j).
    results = {state: twenty_stage_action(state) for state in ("won", "lost", "do_not_contact", "do-not-contact")}
    all_terminal = all(r == {"mutate": False, "reason": "terminal_state_preserved"} for r in results.values())
    rows.append(
        _row(
            "terminal_state_preserved",
            {
                "call": "twenty_stage_action('won'/'lost'/'do_not_contact'/'do-not-contact')",
                "states": results,
                "non_terminal_sample": twenty_stage_action("new"),
            },
            {"mutate": False, "reason": "terminal_state_preserved"},
            {
                "mutate": any(r["mutate"] for r in results.values()),
                "reason": "terminal_state_preserved" if all_terminal else "state_drift",
            },
        )
    )
    return rows


def export_workflow(dest: str | os.PathLike | None = None) -> dict[str, Any]:
    """Export the ready-to-import Nod/Twenty workflow envelope (draft-only).

    The blueprint is validated first and its nodes/edges/deterministic control
    plane/cited_sources are carried VERBATIM; the envelope pins the non-send
    posture (send_enabled False, clients_ai_send False, Twenty write_enabled
    False with preserve_terminal_states [won,lost,do_not_contact]).
    """
    blueprint = pipeline.load_blueprint()
    verdict = pipeline.validate_blueprint(blueprint)
    if not verdict["valid"]:
        raise ValueError(f"blueprint invalid: {verdict['errors']}")
    payload = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "exported_at": _utc_now(),
        "dry_run_only": True,
        "send_policy": {"draft_only": True, "send_enabled": False, "clients_ai_send": False},
        "clients_ai": {"endpoint": CLIENTS_AI_ENDPOINT, "send": False},
        "twenty": {
            "write_enabled": False,
            "operation": "upsert_contact",
            "staged": True,
            "preserve_terminal_states": list(TERMINAL_STATES),
        },
        "gate_d": {
            "channel": "aside-gate-d",
            "draft_only": True,
            "approval": {"kind": "exact-text", "approver": "human", "command": "APPROVE SEND <sha12>"},
        },
        "dnc": {
            "enforced_by": DNC_ENFORCED_BY,
            "stop_file_path": str(dnc_guard.DEFAULT_SENDER_STOP_FILE),
            "rule_file": DNC_RULE_FILE,
        },
        # blueprint verbatim (the deterministic workflow half of the export)
        "nodes": blueprint["nodes"],
        "edges": blueprint["edges"],
        "deterministic_control_plane": blueprint["deterministic_control_plane"],
        "cited_sources": blueprint["cited_sources"],
    }
    return _write_json(Path(dest) if dest else REPO_ROOT / EXPORT_REL_PATH, payload)


def validate_export(payload: dict[str, Any]) -> dict[str, Any]:
    """Check the export envelope; returns {"valid", "errors"} (planted-failure target)."""
    errors: list[str] = []
    if payload.get("schema_version") != EXPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EXPORT_SCHEMA_VERSION}")
    if payload.get("dry_run_only") is not True:
        errors.append("dry_run_only must be True")
    send_policy = payload.get("send_policy", {})
    if send_policy.get("draft_only") is not True:
        errors.append("send_policy.draft_only must be True")
    if send_policy.get("send_enabled") is not False:
        errors.append("send_policy.send_enabled must be False")
    if send_policy.get("clients_ai_send") is not False:
        errors.append("send_policy.clients_ai_send must be False")
    clients_ai = payload.get("clients_ai", {})
    if clients_ai.get("endpoint") != CLIENTS_AI_ENDPOINT:
        errors.append(f"clients_ai.endpoint must be {CLIENTS_AI_ENDPOINT}")
    if clients_ai.get("send") is not False:
        errors.append("clients_ai.send must be False (non-send surface, never called)")
    twenty = payload.get("twenty", {})
    if twenty.get("write_enabled") is not False:
        errors.append("twenty.write_enabled must be False")
    if twenty.get("operation") != "upsert_contact":
        errors.append("twenty.operation must be 'upsert_contact'")
    if twenty.get("staged") is not True:
        errors.append("twenty.staged must be True")
    if twenty.get("preserve_terminal_states") != list(TERMINAL_STATES):
        errors.append("twenty.preserve_terminal_states must be ['won', 'lost', 'do_not_contact']")
    gate_d = payload.get("gate_d", {})
    if gate_d.get("channel") != "aside-gate-d":
        errors.append("gate_d.channel must be 'aside-gate-d'")
    if gate_d.get("draft_only") is not True:
        errors.append("gate_d.draft_only must be True")
    approval = gate_d.get("approval", {})
    if approval.get("kind") != "exact-text" or approval.get("approver") != "human":
        errors.append("gate_d.approval must be human exact-text")
    dnc = payload.get("dnc", {})
    if dnc.get("enforced_by") != DNC_ENFORCED_BY:
        errors.append(f"dnc.enforced_by must be {DNC_ENFORCED_BY}")
    if not dnc.get("stop_file_path") or not dnc.get("rule_file"):
        errors.append("dnc.stop_file_path and dnc.rule_file are required")
    blueprint = pipeline.load_blueprint()
    for key in ("nodes", "edges", "deterministic_control_plane", "cited_sources"):
        if payload.get(key) != blueprint.get(key):
            errors.append(f"{key} must be the blueprint's verbatim {key}")
    return {"valid": not errors, "errors": errors}


def _move3_cited_sources() -> list[str]:
    """Copy the move3 citations verbatim from its context.json — never invent."""
    ctx = json.loads(
        (REPO_ROOT / "src" / "robonuggets_ops" / "move3_gtm_teaser_tune" / "context.json").read_text()
    )
    return list(ctx["cited_sources"])


def run_move3_sample_bundle(out_dir: str | os.PathLike | None = None) -> dict[str, Any]:
    """Run the Move 3 sample bundle into dist/gtm_pack_sample/ (5 artifacts).

    working_teaser.json (working teaser gate: DNC + touch-1 link-free),
    bleed_report.json (inputs_verified bleed report), followups.json (5-angle
    opt-out-compliant drafts), tune_report.json (5-field Tune report),
    manifest.json (artifacts + cited_sources). Every artifact is draft-only.
    """
    out = Path(out_dir) if out_dir else REPO_ROOT / SAMPLE_DIR_REL_PATH
    out.mkdir(parents=True, exist_ok=True)
    envelope = {"draft_only": True, "send_enabled": False, "clients_ai_send": False}
    generated_at = _utc_now()
    files: list[str] = []

    # working_teaser.json — DNC gate + touch-1 link-free gate on the body.
    teaser_result = pack.generate_working_teaser(
        company=SAMPLE_PROSPECT["company"],
        finding=SAMPLE_FINDING,
        evidence=SAMPLE_EVIDENCE,
        contact_name=SAMPLE_PROSPECT["contact_name"],
        url=SAMPLE_PROSPECT["url"],
        recipient_domain=SAMPLE_PROSPECT["recipient_domain"],
    )
    if not teaser_result.get("ok"):
        raise ValueError(f"sample teaser blocked: {teaser_result}")
    guard = pack.touch1_link_free_guard(teaser_result["draft"]["body"])
    if not guard["link_free"]:
        raise ValueError(f"sample teaser body carries a link: {guard}")
    _write_json(
        out / "working_teaser.json",
        {
            "artifact": "working_teaser.json",
            "generated_at": generated_at,
            "input": {"finding": SAMPLE_FINDING, "evidence": SAMPLE_EVIDENCE, **SAMPLE_PROSPECT},
            "result": teaser_result,
            "touch1_link_free_guard": guard,
            "gate_d": pack.GATE_D,
            **envelope,
        },
    )
    files.append("working_teaser.json")

    # bleed_report.json — annual bleed with verified inputs.
    bleed_result = pack.annual_bleed(**BLEED_INPUTS)
    _write_json(
        out / "bleed_report.json",
        {
            "artifact": "bleed_report.json",
            "generated_at": generated_at,
            "inputs": dict(BLEED_INPUTS),
            "inputs_verified": True,
            "result": bleed_result,
            "gate_d": pack.GATE_D,
            **envelope,
        },
    )
    files.append("bleed_report.json")

    # followups.json — 5 touches, 5 distinct angles, opt-out line per draft.
    followup_result = pack.generate_followup_sequence(
        company=SAMPLE_PROSPECT["company"],
        finding=SAMPLE_FINDING,
        contact_name=SAMPLE_PROSPECT["contact_name"],
        url=SAMPLE_PROSPECT["url"],
        recipient_domain=SAMPLE_PROSPECT["recipient_domain"],
    )
    if not followup_result.get("ok"):
        raise ValueError(f"sample followups blocked: {followup_result}")
    module_touches = followup_result["touches"]
    if len(module_touches) != 5 or len({t["angle"] for t in module_touches}) != 5:
        raise ValueError("followup sequence must carry 5 touches with 5 distinct angles")
    if not module_touches[0]["link_free"]:
        raise ValueError("touch 1 must be link-free")
    touches = []
    for touch in module_touches:
        wrapped = dict(touch)  # module text stays untouched
        wrapped["opt_out_line"] = OPT_OUT_LINE
        wrapped["draft_text"] = f"{touch['text']} {OPT_OUT_LINE}"
        touches.append(wrapped)
    _write_json(
        out / "followups.json",
        {
            "artifact": "followups.json",
            "generated_at": generated_at,
            "input": {"finding": SAMPLE_FINDING, **SAMPLE_PROSPECT},
            "result": followup_result,  # module output verbatim (text untouched)
            "opt_out_line": OPT_OUT_LINE,
            "touches": touches,
            "gate_d": pack.GATE_D,
            **envelope,
        },
    )
    files.append("followups.json")

    # tune_report.json — 5-field Tune report on a purchase metric.
    tune_result = pack.build_tune_report(**TUNE_INPUTS)
    if tune_result["errors"] or tune_result["field_count"] != 5:
        raise ValueError(f"sample tune report invalid: {tune_result}")
    _write_json(
        out / "tune_report.json",
        {
            "artifact": "tune_report.json",
            "generated_at": generated_at,
            "input": dict(TUNE_INPUTS),
            "result": tune_result,
            "fields": tune_result["slide"]["fields"],
            "gate_d": pack.GATE_D,
            **envelope,
        },
    )
    files.append("tune_report.json")

    # manifest.json — artifacts + cited_sources copied verbatim from context.json.
    files.append("manifest.json")
    _write_json(
        out / "manifest.json",
        {
            "artifact": "manifest.json",
            "generated_at": generated_at,
            "artifacts": files,
            "cited_sources": _move3_cited_sources(),
            "gate_d": pack.GATE_D,
            **envelope,
        },
    )
    return {
        "out_dir": str(out),
        "files": files,
        "cited_sources": _move3_cited_sources(),
    }


def write_report(
    matrix: list[dict[str, Any]],
    sender_state: dict[str, Any],
    moves: dict[str, Any],
    dest: str | os.PathLike | None = None,
) -> dict[str, Any]:
    """Write the dry-run report (sends=0, twenty_writes=0, clients_ai_calls=0)."""
    dnc = load_do_not_contact()
    report = {
        "run_id": "live_gtm_phase2_dryrun_2026-11-16",
        "generated_at": _utc_now(),
        "git_head": _git_head(),
        "dry_run": True,
        "sends": 0,
        "twenty_writes": 0,
        "clients_ai_calls": 0,
        "sender_lane": sender_state,
        "dnc": {
            "rule_file": DNC_RULE_FILE,
            "loaded_read_only": True,
            "people_count": len(dnc.get("people", [])),
            "companies_count": len(dnc.get("companies", [])),
            "blocked_companies": dnc.get("blocked_companies", {}),
        },
        "matrix": matrix,
        "gates": {
            "dnc": {
                "gate": "1-dnc",
                "enforced_by": DNC_ENFORCED_BY,
                "rule_file": DNC_RULE_FILE,
                "carve_out": "ATS host (oraclecloud.com|taleo.net) without an employer in company -> refused; the employer field decides",
            },
            "gate_d": {
                "channel": "aside-gate-d",
                "draft_only": True,
                "approval": {
                    "kind": "exact-text",
                    "approver": "human",
                    "command": "APPROVE SEND <sha12>",
                },
                "sender_lane": "check_sender_lane_ready — STOP brake + approved_sha12 == template_sha12; auto_send always False",
            },
            "clients_ai_non_send": {
                "endpoint": CLIENTS_AI_ENDPOINT,
                "clients_ai_send": False,
            },
        },
        "planted_failures": PLANTED_FAILURES,
        "move3_sample_bundle": {
            "dir": SAMPLE_DIR_REL_PATH,
            "files": moves.get("files", []),
            "cited_sources": moves.get("cited_sources", []),
        },
    }
    return _write_json(Path(dest) if dest else REPO_ROOT / REPORT_REL_PATH, report)


def main() -> int:
    dnc = load_do_not_contact()
    matrix = run_dry_run_matrix(dnc=dnc)
    sender_state = sender_lane_state()
    export_payload = export_workflow()
    export_verdict = validate_export(export_payload)
    moves = run_move3_sample_bundle()
    write_report(matrix, sender_state, moves)

    ok = all(row["pass"] for row in matrix) and export_verdict["valid"]
    result = {
        "ok": ok,
        "artifacts": [
            EXPORT_REL_PATH,
            f"{SAMPLE_DIR_REL_PATH}/working_teaser.json",
            f"{SAMPLE_DIR_REL_PATH}/bleed_report.json",
            f"{SAMPLE_DIR_REL_PATH}/followups.json",
            f"{SAMPLE_DIR_REL_PATH}/tune_report.json",
            f"{SAMPLE_DIR_REL_PATH}/manifest.json",
            REPORT_REL_PATH,
        ],
        "sends": 0,
        "twenty_writes": 0,
        "clients_ai_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
