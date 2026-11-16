"""Shared 1-dnc No-Oracle + Matt Colmia outreach filter with ATS-host carve-out."""
from __future__ import annotations
import re
import os
from typing import Any, Any, Dict

BLOCKED_EMPLOYERS = ("oracle", "oracle health", "cerner", "oracle cerner", "oracle corp", "oracle corporation", "oracle america")
BLOCKED_PEOPLE = ("matt colmia",)
ATS_HOST_DOMAINS = ("oraclecloud.com", "taleo.net")


def evaluate_outreach_target(company: str = "", person_name: str = "", url: str = "", recipient_domain: str = "") -> Dict[str, Any]:
    """Return gate verdict enforcing No-Oracle, Matt Colmia block, and ATS-host carve-out."""
    comp = re.sub(r"\s+", " ", (company or "").strip().lower())
    person = re.sub(r"\s+", " ", (person_name or "").strip().lower())
    dom = (recipient_domain or "").strip().lower().lstrip("@")
    link = (url or "").strip().lower()

    for blocked_person in BLOCKED_PEOPLE:
        if blocked_person in person or "colmia" in dom:
            return {"allowed": False, "gate": "1-dnc", "reason": f"blocked_person:{blocked_person}"}

    if any(comp == b or comp.startswith(b + " ") or comp.startswith(b + ",") or comp.startswith(b + " (") for b in BLOCKED_EMPLOYERS):
        return {"allowed": False, "gate": "1-dnc", "reason": f"blocked_employer:{comp}"}

    if dom in ("oracle.com", "cerner.com") or dom.endswith(".oracle.com") or dom.endswith(".cerner.com"):
        return {"allowed": False, "gate": "1-dnc", "reason": f"blocked_domain:{dom}"}

    ats_hosted = any(host in link for host in ATS_HOST_DOMAINS)
    if ats_hosted and not comp:
        return {"allowed": False, "gate": "1-dnc", "reason": "ats_host_missing_employer"}

    return {
        "allowed": True,
        "gate": "1-dnc",
        "atsHostCarveOut": ats_hosted,
        "employer": company or "",
    }


DEFAULT_SENDER_STOP_FILE = os.path.expanduser("~/rig-gtm-home/gmail-sender/STOP")


def check_sender_lane_ready(
    *,
    stop_file_path: str | None = None,
    template_sha12: str = "",
    approved_sha12: str = "",
) -> dict[str, Any]:
    """Enforce gmail-sender HOLD-PIN STOP brake and sha12 exact-text approval match.

    Rooms NEVER fire outward sends directly (`auto_send` is always False); even staging
    for the sender queue must report blocked if the sender STOP file exists or if
    `approved_sha12` does not match `template_sha12`.
    """
    resolved_stop = stop_file_path or os.environ.get("RIG_SENDER_STOP_FILE", DEFAULT_SENDER_STOP_FILE)
    if resolved_stop and os.path.exists(resolved_stop):
        return {
            "ready": False,
            "reason": f"blocked: sender STOP brake active at {resolved_stop} (requires Mike quote to lift)",
            "auto_send": False,
            "log_channel": "jake-owen",
        }
    t_sha = (template_sha12 or "").strip()
    a_sha = (approved_sha12 or "").strip()
    if not t_sha or not a_sha or t_sha != a_sha:
        return {
            "ready": False,
            "reason": "blocked: approved_sha12 must be non-empty and equal template_sha12",
            "auto_send": False,
            "log_channel": "jake-owen",
        }
    return {
        "ready": True,
        "reason": "eligible_for_sender_queue_only_never_room_autosend",
        "auto_send": False,
        "log_channel": "jake-owen",
    }
