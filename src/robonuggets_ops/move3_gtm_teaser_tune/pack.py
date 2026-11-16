"""Move 3 deliverables (RoboNuggets 6-tool spec, ticket #4).

1. Pre-touch-1 working teaser generator, touch-1 link-free guard, and a
   5-touch spaced distinct-angle follow-up generator
   (src: classroom/agents-as-a-service/1-cold-outreach-that-works).
2. Live-discovery annual-bleed calculator
   (src: classroom/agents-as-a-service/2-discovery-that-sells).
3. Kickoff contract checker: line-1 integration model lock + explicit
   2-to-4-week hypercare dates (src: classroom/agents-as-a-service/2-the-integrate-phase).
4. 1-slide 5-field dollarized Tune report + 3 recurring retainer tiers
   (src: classroom/agents-as-a-service/3-the-tune-phase-results-reporting,
    src: classroom/agents-as-a-service/1-expanding-with-existing-clients).

Every outreach artifact is gated by evaluate_outreach_target (No Oracle +
Matt Colmia block + ATS-host carve-out) and is draft-only behind Gate-D.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from ..dnc_guard import evaluate_outreach_target

GATE_D = "draft_only: nothing sends without Mike's exact-text approval"
INTEGRATION_MODELS = ("DFY", "install_into_stack", "build_operate_transfer")
HYPERCARE_MIN_DAYS = 14  # 2 weeks
HYPERCARE_MAX_DAYS = 28  # 4 weeks
TOUCH_DAY_OFFSETS = (0, 3, 7, 12, 18)
TOUCH_ANGLES = ("finding", "question", "proof", "insight", "permission_close")
PURCHASE_METRICS = ("hours_returned", "leads_created", "output_shipped", "money_moved")
RETAINER_TIERS = ("monitoring_fixes", "monthly_tuning", "next_workflow_build")

_LINK_RE = re.compile(r"(https?://\S+|www\.\S+|\b\S+\.(?:com|net|org|io|co|ai|ly)\b)", re.IGNORECASE)
_MODEL_RE = re.compile(r"\b(DFY|install_into_stack|build_operate_transfer)\b")

_TOUCH_TEMPLATES = {
    "finding": "Touch 1: the audit of {company} turned up {finding} — want me to send the write-up?",
    "question": (
        "Touch 2: one question after the audit of {company} — "
        "is {finding} already on your team's radar?"
    ),
    "proof": (
        "Touch 3: a similar audit elsewhere turned {finding} into hours back per week — "
        "happy to show the before and after."
    ),
    "insight": (
        "Touch 4: the pattern behind {finding} usually hides in the handoffs — "
        "worth 15 minutes on where it sits at {company}?"
    ),
    "permission_close": (
        "Touch 5: closing the loop on {finding} — "
        "should I leave this with you, or is there a better person at {company}?"
    ),
}


def _nonneg_number(name: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return float(value)


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def touch1_link_free_guard(text: str) -> dict:
    """Touch 1 must carry no links, so the first message never looks like a blast."""
    links = _LINK_RE.findall(text or "")
    return {"link_free": not links, "links": links, "gate_d": GATE_D}


def generate_working_teaser(
    *,
    company: str,
    finding: str,
    evidence: str = "",
    contact_name: str = "",
    url: str = "",
    recipient_domain: str = "",
) -> dict:
    """Pre-touch-1 teaser: the audit finding drafted as a five-sentence permission ask."""
    verdict = evaluate_outreach_target(
        company=company, person_name=contact_name, url=url, recipient_domain=recipient_domain
    )
    if not verdict["allowed"]:
        return {"ok": False, "stage": "pre_touch_1", "blocked_by": verdict, "draft": None, "gate_d": GATE_D}
    finding = (finding or "").strip()
    if not finding:
        return {
            "ok": False,
            "stage": "pre_touch_1",
            "blocked_by": verdict,
            "draft": None,
            "reason": "missing_finding",
            "gate_d": GATE_D,
        }
    who = verdict["employer"] or company
    sentences = [f"I ran a quick audit of {who} and found {finding}"]
    if evidence.strip():
        sentences.append(f"The evidence: {evidence.strip()}")
    sentences.append("It looked worth a look, so I wrote it up as a short report")
    sentences.append("Mind if I send what I found over?")
    sentences.append("Happy to walk through it live instead if that is easier")
    sentences = sentences[:5]  # course rule: the first message fits a five-sentence cap
    body = ". ".join(sentences) + "."
    return {
        "ok": True,
        "stage": "pre_touch_1",
        "blocked_by": verdict,
        "draft": {"subject": f"one thing I found at {who}", "sentences": sentences, "body": body},
        "gate_d": GATE_D,
    }


def generate_followup_sequence(
    *,
    company: str,
    finding: str,
    contact_name: str = "",
    angles=TOUCH_ANGLES,
    day_offsets=TOUCH_DAY_OFFSETS,
    url: str = "",
    recipient_domain: str = "",
) -> dict:
    """Five touches, strictly spaced, each from its own distinct angle (touch 1 link-free)."""
    verdict = evaluate_outreach_target(
        company=company, person_name=contact_name, url=url, recipient_domain=recipient_domain
    )
    if not verdict["allowed"]:
        return {"ok": False, "blocked_by": verdict, "touches": [], "gate_d": GATE_D}
    finding = (finding or "").strip()
    if not finding:
        return {"ok": False, "blocked_by": verdict, "touches": [], "reason": "missing_finding", "gate_d": GATE_D}
    angles = tuple(angles)
    offsets = tuple(day_offsets)
    if len(angles) != 5 or len(set(angles)) != 5:
        return {
            "ok": False,
            "blocked_by": verdict,
            "touches": [],
            "reason": "angles_must_be_5_distinct",
            "gate_d": GATE_D,
        }
    unknown = [a for a in angles if a not in _TOUCH_TEMPLATES]
    if unknown:
        return {
            "ok": False,
            "blocked_by": verdict,
            "touches": [],
            "reason": f"unknown_angle:{unknown[0]}",
            "gate_d": GATE_D,
        }
    if len(offsets) != 5 or any(offsets[i] >= offsets[i + 1] for i in range(4)):
        return {
            "ok": False,
            "blocked_by": verdict,
            "touches": [],
            "reason": "day_offsets_must_be_5_strictly_increasing",
            "gate_d": GATE_D,
        }
    who = verdict["employer"] or company
    touches = []
    for i, (day, angle) in enumerate(zip(offsets, angles, strict=True), start=1):
        text = _TOUCH_TEMPLATES[angle].format(company=who, finding=finding)
        guard = touch1_link_free_guard(text)
        if i == 1 and not guard["link_free"]:
            return {
                "ok": False,
                "blocked_by": verdict,
                "touches": [],
                "reason": "touch_1_carries_a_link",
                "guard": guard,
                "gate_d": GATE_D,
            }
        touches.append(
            {
                "touch": i,
                "day_offset": day,
                "angle": angle,
                "text": text,
                "link_free": guard["link_free"],
                "gate_d": GATE_D,
            }
        )
    return {"ok": True, "blocked_by": verdict, "touches": touches, "gate_d": GATE_D}


def annual_bleed(
    *,
    hours_per_week,
    loaded_hourly_rate,
    errors_per_week=0.0,
    cost_per_error=0.0,
    lost_leads_per_week=0.0,
    value_per_lead=0.0,
) -> dict:
    """Live-discovery bleed: hours_per_week * loaded_hourly_rate * 52 + error/lead-loss bleed."""
    hours = _nonneg_number("hours_per_week", hours_per_week)
    rate = _nonneg_number("loaded_hourly_rate", loaded_hourly_rate)
    errors = _nonneg_number("errors_per_week", errors_per_week)
    per_error = _nonneg_number("cost_per_error", cost_per_error)
    leads = _nonneg_number("lost_leads_per_week", lost_leads_per_week)
    per_lead = _nonneg_number("value_per_lead", value_per_lead)
    time_bleed = hours * rate * 52
    error_bleed = errors * per_error * 52
    lead_bleed = leads * per_lead * 52
    return {
        "formula": "hours_per_week * loaded_hourly_rate * 52 + error/lead-loss bleed",
        "annual_time_bleed": round(time_bleed, 2),
        "annual_error_bleed": round(error_bleed, 2),
        "annual_lead_loss_bleed": round(lead_bleed, 2),
        "annual_total_bleed": round(time_bleed + error_bleed + lead_bleed, 2),
        "gate_d": GATE_D,
    }


def check_kickoff_contract(*, kickoff_text: str, hypercare_start, hypercare_end) -> dict:
    """Line 1 locks the integration model; hypercare window is explicit and 2-4 weeks."""
    errors = []
    lines = [line for line in (kickoff_text or "").splitlines() if line.strip()]
    first = lines[0] if lines else ""
    match = _MODEL_RE.search(first)
    model = match.group(1) if match else None
    if model is None:
        errors.append("integration_model_not_locked_on_line_1")
    start = _as_date(hypercare_start)
    end = _as_date(hypercare_end)
    if start is None:
        errors.append("hypercare_start_missing_or_unparseable")
    if end is None:
        errors.append("hypercare_end_missing_or_unparseable")
    days = None
    if start is not None and end is not None:
        days = (end - start).days
        if not (HYPERCARE_MIN_DAYS <= days <= HYPERCARE_MAX_DAYS):
            errors.append(f"hypercare_window_out_of_range:{days}d")
    return {
        "ok": not errors,
        "errors": errors,
        "integration_model": model,
        "hypercare_days": days,
        "gate_d": GATE_D,
    }


def build_tune_report(
    *,
    what_shipped: str,
    purchase_metric: str,
    metric_value,
    dollar_value,
    paid,
    received,
    expansion_suggestion: str,
) -> dict:
    """One slide, five fixed dollarized fields (metric must match what they bought)."""
    errors = []
    if not (what_shipped or "").strip():
        errors.append("what_shipped_required")
    if purchase_metric not in PURCHASE_METRICS:
        errors.append("purchase_metric_must_match_what_they_bought")
    metric_value = _nonneg_number("metric_value", metric_value)
    dollar_value = _nonneg_number("dollar_value", dollar_value)  # honest estimate beats a blank
    paid = _nonneg_number("paid", paid)
    received = _nonneg_number("received", received)
    if paid <= 0:
        errors.append("paid_must_be_positive")
    if not (expansion_suggestion or "").strip():
        errors.append("one_expansion_suggestion_required")
    fields = {
        "what_delivered": (what_shipped or "").strip(),
        "metric": {"type": purchase_metric, "value": metric_value},
        "dollar_value": dollar_value,
        "paid_versus_received": {
            "paid": paid,
            "received": received,
            "roi": round(received / paid, 2) if paid > 0 else None,
        },
        "expansion_suggestion": (expansion_suggestion or "").strip(),
    }
    return {
        "ok": not errors,
        "errors": errors,
        "slide": {"title": "Tune report — one slide", "fields": fields},
        "field_count": len(fields),
        "gate_d": GATE_D,
    }


def retainer_tiers(*, something_shipped: bool, observed_gap: str = "") -> dict:
    """Three recurring tiers, each tied to a gap observed in the build — never before shipping."""
    if not something_shipped:
        return {
            "ok": False,
            "reason": "never_pitch_tiers_before_something_shipped",
            "tiers": [],
            "gate_d": GATE_D,
        }
    gap = (observed_gap or "").strip()
    if not gap:
        return {
            "ok": False,
            "reason": "each_tier_must_tie_to_an_observed_gap",
            "tiers": [],
            "gate_d": GATE_D,
        }
    tiers = [
        {
            "id": "monitoring_fixes",
            "promise": "keeping it running: monitoring plus fixes",
            "cadence": "recurring",
            "tied_to_gap": gap,
        },
        {
            "id": "monthly_tuning",
            "promise": "producing more of the outcome: monthly tuning",
            "cadence": "recurring",
            "tied_to_gap": gap,
        },
        {
            "id": "next_workflow_build",
            "promise": "the next workflow to build, pitched from this slide",
            "cadence": "recurring",
            "tied_to_gap": gap,
        },
    ]
    return {"ok": True, "tiers": tiers, "gate_d": GATE_D}
