"""Shared 1-dnc No-Oracle + Matt Colmia outreach filter with ATS-host carve-out."""
from __future__ import annotations
import re
from typing import Any, Dict

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
