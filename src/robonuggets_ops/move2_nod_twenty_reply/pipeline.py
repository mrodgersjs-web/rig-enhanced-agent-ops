"""Move 2 pipeline: Nod/n8n -> Jev -> Twenty CRM -> Aside Gate-D reply & triggers.

Deterministic, schema-locked builders for the reply and trigger lanes:

- ``classify_reply``   — schema-locked inbound reply classifier (typed state for Jev).
- ``build_contact_brief`` — Twenty CRM contact brief builder (staged write only).
- ``build_gate_d_card``   — Aside Gate-D staged approval card (draft-only; the
  card never sends: ``send_enabled=False`` and ``clients_ai_send=False``).
- ``score_trigger_event`` — fresh-domain trigger-event scorer
  (``src: classroom/community-vault/the-30k-ai-app-breakdown-2026-08-03``).
- ``load_blueprint`` / ``validate_blueprint`` — the deterministic Nod/n8n
  blueprint separating pagination/retries/sleeps from schema-locked AI nodes
  (``src: classroom/automation-blueprints/n0-how-to-set-up-ai-agents-in-n8n``,
  ``src: classroom/automation-blueprints/n1-building-reliable-rag-agents-in-n8n``,
  ``src: classroom/automation-blueprints/n10-automate-faceless-channels-full-setup-free-tools``).

Hard floor: every lead and reply path re-runs
``dnc_guard.evaluate_outreach_target`` before any record is produced. Blocked
targets (Oracle, Oracle Health, Cerner, Matt Colmia — even with a blank company)
get ``"blocked"`` records and no draft; UCSF / JPMorganChase / Coherent hosted
on ``*.oraclecloud.com`` pass under the ATS-host carve-out.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any
from urllib.parse import urlparse

from ..dnc_guard import check_sender_lane_ready, evaluate_outreach_target

SCHEMA_VERSION = "move2.nod-twenty-reply.v1"
BLUEPRINT_SCHEMA_VERSION = "move2.nod-blueprint.v1"
BLUEPRINT_FILENAME = "nod_workflow_blueprint.json"
CLIENTS_AI_ENDPOINT = "http://127.0.0.1:3211"
TWENTY_CRM_SYSTEM = "twenty"

# Schema-locked reply classification enum. Earlier entries win score ties.
REPLY_CLASSES = (
    "hostile",
    "unsubscribe",
    "bounce",
    "out_of_office",
    "objection",
    "not_now",
    "referral",
    "meeting_request",
    "interested",
    "blocked",
    "other",
)

# Keyword -> weight per class; deterministic bag-of-signals scoring.
REPLY_KEYWORDS: dict[str, tuple] = {
    "hostile": (
        ("never contact", 3),
        ("cease and desist", 3),
        ("report spam", 3),
        ("harassment", 3),
        ("do not contact", 3),
        ("lawsuit", 2),
        ("sue", 2),
    ),
    "unsubscribe": (
        ("unsubscribe", 3),
        ("remove me", 3),
        ("opt out", 3),
        ("stop emailing", 3),
        ("take me off", 2),
        ("remove my", 2),
    ),
    "bounce": (
        ("undeliverable", 3),
        ("delivery failed", 3),
        ("address not found", 3),
        ("does not exist", 2),
        ("mailbox full", 2),
        ("550 ", 2),
    ),
    "out_of_office": (
        ("out of the office", 3),
        ("out of office", 3),
        ("auto-reply", 2),
        ("on leave", 2),
        ("away until", 2),
        ("returning on", 2),
        ("vacation", 2),
        ("ooo", 2),
    ),
    "objection": (
        ("not interested", 3),
        ("too expensive", 3),
        ("no budget", 3),
        ("not a priority", 2),
        ("already have", 2),
        ("not relevant", 2),
        ("no thanks", 2),
    ),
    "not_now": (
        ("not right now", 3),
        ("circle back", 2),
        ("next quarter", 2),
        ("maybe later", 2),
        ("bad timing", 2),
        ("reach out in", 2),
    ),
    "referral": (
        ("wrong person", 3),
        ("not the right person", 3),
        ("my colleague", 2),
        ("talk to", 1),
        ("reach out to", 1),
        ("forward this", 1),
        ("better fit", 1),
    ),
    "meeting_request": (
        ("let's talk", 2),
        ("schedule", 2),
        ("book", 2),
        ("calendar", 2),
        ("call next", 2),
        ("meeting", 1),
        ("available", 1),
        ("zoom", 1),
    ),
    "interested": (
        ("interested", 2),
        ("sounds good", 2),
        ("tell me more", 2),
        ("pricing", 1),
        ("demo", 1),
        ("send over", 1),
        ("more information", 1),
    ),
    "other": (),
}

NEXT_ACTION_BY_CLASS = {
    "hostile": "suppress_and_escalate",
    "unsubscribe": "suppress_contact",
    "bounce": "verify_and_suppress",
    "out_of_office": "defer_followup",
    "objection": "stage_objection_response",
    "not_now": "stage_nurture_followup",
    "referral": "stage_referral_followup",
    "meeting_request": "stage_meeting_draft",
    "interested": "stage_reply_draft",
    "blocked": "drop_contact",
    "other": "manual_review",
}

TALKING_POINTS_BY_CLASS = {
    "hostile": ["Acknowledge and close the thread.", "Add to suppression before any further outreach."],
    "unsubscribe": ["Confirm removal.", "Add to suppression before any further outreach."],
    "bounce": ["Verify the address.", "Suppress the dead address before any resend."],
    "out_of_office": ["Note the return window.", "Schedule follow-up after the return date."],
    "objection": ["Acknowledge the objection.", "Offer one concrete proof point, no pressure."],
    "not_now": ["Respect the timing.", "Queue a nurture touch for the window they named."],
    "referral": ["Thank for the pointer.", "Ask permission to name them in the referral note."],
    "meeting_request": ["Offer two concrete slots.", "Include a one-line agenda."],
    "interested": ["Answer their question directly.", "Offer the smallest next step (short call)."],
    "blocked": ["No outreach — DNC gate."],
    "other": ["Route for human review before any reply."],
}

REPLY_RECORD_KEYS = frozenset({
    "schema_version", "reply_id", "thread_id", "reply_class", "confidence",
    "signals", "allowed", "dnc",
})

CONTACT_BRIEF_KEYS = frozenset({
    "schema_version", "brief_id", "contact", "intent", "summary",
    "talking_points", "next_action", "crm", "write_enabled", "dnc",
})

GATE_D_CARD_KEYS = frozenset({
    "schema_version", "card_id", "stage", "channel", "draft_only",
    "send_enabled", "clients_ai_send", "clients_ai_endpoint", "approval",
    "draft", "sender_lane", "provenance", "dnc",
})

TRIGGER_EVENT_TYPES = (
    "hiring", "funding", "product_launch", "tech_adoption",
    "leadership_change", "domain_registration", "expansion", "regulatory", "other",
)

TRIGGER_BASE_SCORES = {
    "hiring": 45,
    "funding": 55,
    "product_launch": 40,
    "tech_adoption": 50,
    "leadership_change": 30,
    "domain_registration": 60,
    "expansion": 40,
    "regulatory": 20,
    "other": 10,
}

TRIGGER_SCORE_KEYS = frozenset({
    "schema_version", "event_id", "domain", "company", "event_type",
    "score", "band", "freshness", "signals", "allowed", "dnc",
})

# Separation rule: schema-locked AI nodes never own control-flow concerns.
AI_NODE_FORBIDDEN_KEYS = ("pagination", "sleeps", "retry", "retry_policy", "loop")


def _sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _stable_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return _sha12(canonical)


def _domain_of(email: str) -> str:
    return email.split("@", 1)[1].lower() if "@" in (email or "") else ""


def _contact_gate(name: str, company: str, email: str, url: str) -> dict[str, Any]:
    """Run the DNC gate on one contact/lead — the only way records may exist."""
    return evaluate_outreach_target(
        company=company or "",
        person_name=name or "",
        url=url or "",
        recipient_domain=_domain_of(email),
    )


def validate_reply_record(record: dict[str, Any]) -> None:
    """Schema-lock check for the reply record; raises ValueError on drift."""
    if not isinstance(record, dict) or set(record) != set(REPLY_RECORD_KEYS):
        raise ValueError(f"reply record keys must be exactly {sorted(REPLY_RECORD_KEYS)}")
    if record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("reply record schema_version mismatch")
    if record["reply_class"] not in REPLY_CLASSES:
        raise ValueError(f"reply_class must be one of {REPLY_CLASSES}")
    if not isinstance(record["confidence"], float) or not 0.0 <= record["confidence"] <= 1.0:
        raise ValueError("confidence must be a float in [0, 1]")
    if not isinstance(record["signals"], list) or not all(isinstance(s, str) for s in record["signals"]):
        raise ValueError("signals must be a list of strings")
    if not isinstance(record["allowed"], bool):
        raise ValueError("allowed must be a bool")
    if not isinstance(record["dnc"], dict) or "allowed" not in record["dnc"]:
        raise ValueError("dnc must carry the evaluate_outreach_target verdict")


def classify_reply(
    reply_text: str,
    *,
    reply_id: str = "",
    thread_id: str = "",
    sender_name: str = "",
    sender_company: str = "",
    sender_email: str = "",
    url: str = "",
) -> dict[str, Any]:
    """Classify one inbound reply into a schema-locked record.

    Deterministic keyword scoring; Jev consumes the typed record downstream
    (fail closed: if the classifier is unreachable the reply is deferred, never
    guessed). DNC gate runs first and short-circuits to ``"blocked"``.
    """
    gate = _contact_gate(sender_name, sender_company, sender_email, url)
    if not gate.get("allowed"):
        record = {
            "schema_version": SCHEMA_VERSION,
            "reply_id": reply_id,
            "thread_id": thread_id,
            "reply_class": "blocked",
            "confidence": 1.0,
            "signals": [f"dnc_gate:{gate.get('reason', 'blocked')}"],
            "allowed": False,
            "dnc": gate,
        }
        validate_reply_record(record)
        return record

    text = (reply_text or "").lower()
    scores: dict[str, int] = {}
    matched: dict[str, list[str]] = {}
    for reply_class, keywords in REPLY_KEYWORDS.items():
        total = 0
        hits: list[str] = []
        for keyword, weight in keywords:
            if keyword in text:
                total += weight
                hits.append(keyword)
        if total:
            scores[reply_class] = total
            matched[reply_class] = hits

    # Iterate in priority order; strictly-greater replacement keeps ties on the
    # earlier class.
    best_class, best_score = "other", 0
    for reply_class in REPLY_CLASSES:
        if scores.get(reply_class, 0) > best_score:
            best_class, best_score = reply_class, scores[reply_class]

    if best_score:
        runner_up = max(
            (score for cls, score in scores.items() if cls != best_class),
            default=0,
        )
        confidence = round(best_score / (best_score + runner_up), 3)
        signals = [f"{best_class}:{kw}" for kw in matched[best_class]]
        signals.append(f"score:{best_score}")
    else:
        confidence = 0.0
        signals = ["no_keyword_signal"]

    record = {
        "schema_version": SCHEMA_VERSION,
        "reply_id": reply_id,
        "thread_id": thread_id,
        "reply_class": best_class,
        "confidence": confidence,
        "signals": signals,
        "allowed": True,
        "dnc": gate,
    }
    validate_reply_record(record)
    return record


def validate_contact_brief(brief: dict[str, Any]) -> None:
    """Schema-lock check for the Twenty CRM contact brief; raises on drift."""
    if not isinstance(brief, dict) or set(brief) != set(CONTACT_BRIEF_KEYS):
        raise ValueError(f"contact brief keys must be exactly {sorted(CONTACT_BRIEF_KEYS)}")
    if brief["schema_version"] != SCHEMA_VERSION:
        raise ValueError("contact brief schema_version mismatch")
    if brief["intent"] not in REPLY_CLASSES:
        raise ValueError(f"intent must be one of {REPLY_CLASSES}")
    if brief["next_action"] not in set(NEXT_ACTION_BY_CLASS.values()):
        raise ValueError("next_action outside the locked action set")
    if brief["write_enabled"] is not False:
        raise ValueError("write_enabled must stay False — Twenty writes are Gate-D gated")
    crm = brief["crm"]
    if not isinstance(crm, dict) or crm.get("system") != TWENTY_CRM_SYSTEM:
        raise ValueError("crm.system must be 'twenty'")
    if crm.get("operation") != "upsert_contact" or crm.get("staged") is not True:
        raise ValueError("crm operation must be a staged upsert_contact")


def build_contact_brief(
    reply_record: dict[str, Any],
    *,
    name: str = "",
    company: str = "",
    email: str = "",
    url: str = "",
) -> dict[str, Any]:
    """Build the Twenty CRM contact brief from a classified reply record.

    Re-runs the DNC gate on the contact fields (defense in depth — a tampered
    record cannot smuggle a blocked contact into CRM staging).
    """
    validate_reply_record(reply_record)
    gate = _contact_gate(name, company, email, url)
    allowed = bool(reply_record["allowed"] and gate.get("allowed"))
    intent = reply_record["reply_class"] if allowed else "blocked"
    domain = _domain_of(email)

    brief_id = _stable_id({
        "name": name, "company": company, "email": email,
        "intent": intent, "thread_id": reply_record["thread_id"],
    })
    brief = {
        "schema_version": SCHEMA_VERSION,
        "brief_id": brief_id,
        "contact": {"name": name, "company": company, "email": email, "domain": domain},
        "intent": intent,
        "summary": (
            f"{name or 'Unknown contact'} ({company or 'unknown company'}) "
            f"replied with intent '{intent}' on thread "
            f"{reply_record['thread_id'] or 'unthreaded'}."
        ),
        "talking_points": list(TALKING_POINTS_BY_CLASS[intent]),
        "next_action": NEXT_ACTION_BY_CLASS[intent],
        "crm": {
            "system": TWENTY_CRM_SYSTEM,
            "operation": "upsert_contact",
            "staged": True,
            "external_id": brief_id,
        },
        "write_enabled": False,
        "dnc": gate,
    }
    validate_contact_brief(brief)
    return brief


def validate_gate_d_card(card: dict[str, Any]) -> None:
    """Schema-lock check for the Aside Gate-D card; raises on drift."""
    if not isinstance(card, dict) or set(card) != set(GATE_D_CARD_KEYS):
        raise ValueError(f"gate-d card keys must be exactly {sorted(GATE_D_CARD_KEYS)}")
    if card["schema_version"] != SCHEMA_VERSION:
        raise ValueError("gate-d card schema_version mismatch")
    if card["draft_only"] is not True or card["send_enabled"] is not False:
        raise ValueError("gate-d card must stay draft-only (send_enabled=False)")
    if card["clients_ai_send"] is not False:
        raise ValueError("clients_ai_send must be False — clients.ai is a non-send surface")
    if card["channel"] != "aside-gate-d":
        raise ValueError("gate-d card channel must be 'aside-gate-d'")
    if card["stage"] not in ("staged", "blocked"):
        raise ValueError("gate-d card stage must be 'staged' or 'blocked'")
    if card["approval"].get("kind") != "exact-text" or card["approval"].get("approver") != "human":
        raise ValueError("approval must be human exact-text")
    if card["sender_lane"].get("auto_send") is not False:
        raise ValueError("rooms/senders never auto-send: sender_lane.auto_send must be False")


def build_gate_d_card(
    reply_record: dict[str, Any],
    brief: dict[str, Any],
    *,
    sender_stop_file: str | None = None,
) -> dict[str, Any]:
    """Stage an Aside Gate-D approval card from a classified reply + brief.

    Draft-only: the card never sends. ``send_enabled=False`` and
    ``clients_ai_send=False`` are construction invariants, and the sender lane
    reads the STOP brake + exact-text sha12 approval through
    ``dnc_guard.check_sender_lane_ready``.
    """
    validate_reply_record(reply_record)
    validate_contact_brief(brief)
    allowed = bool(reply_record["allowed"] and brief["dnc"].get("allowed"))
    contact = brief["contact"]
    thread_id = reply_record["thread_id"]

    subject = f"Re: {contact['name'] or contact['company'] or 'your note'}"
    if allowed:
        body = (
            f"Hi {contact['name'] or 'there'},\n\n"
            f"Thanks for your reply ({brief['intent']}). "
            f"{brief['talking_points'][0]}\n\n"
            "— sent only after your exact-text approval\n"
        )
    else:
        subject = ""
        body = ""

    template_sha12 = _sha12(body) if body else ""
    sender_lane = check_sender_lane_ready(
        template_sha12=template_sha12,
        approved_sha12="",
        stop_file_path=sender_stop_file,
    )
    if allowed:
        exact_text = f"APPROVE SEND {template_sha12}: {subject}"
    else:
        exact_text = "BLOCKED_BY_DNC: no approval possible"

    card = {
        "schema_version": SCHEMA_VERSION,
        "card_id": _stable_id({
            "reply_id": reply_record["reply_id"],
            "brief_id": brief["brief_id"],
            "thread_id": thread_id,
            "template_sha12": template_sha12,
        }),
        "stage": "staged" if allowed else "blocked",
        "channel": "aside-gate-d",
        "draft_only": True,
        "send_enabled": False,
        "clients_ai_send": False,
        "clients_ai_endpoint": CLIENTS_AI_ENDPOINT,
        "approval": {
            "required": True,
            "kind": "exact-text",
            "approver": "human",
            "exact_text": exact_text,
            "approved_sha12_required": True,
        },
        "draft": {
            "subject": subject,
            "body": body,
            "recipients": [contact["email"]] if contact["email"] else [],
            "template_sha12": template_sha12,
        },
        "sender_lane": sender_lane,
        "provenance": {
            "reply_id": reply_record["reply_id"],
            "brief_id": brief["brief_id"],
            "thread_id": thread_id,
        },
        "dnc": {
            "allowed": allowed,
            "record": reply_record["dnc"],
            "contact": brief["dnc"],
        },
    }
    validate_gate_d_card(card)
    return card


def validate_trigger_score(scored: dict[str, Any]) -> None:
    """Schema-lock check for a scored trigger event; raises on drift."""
    if not isinstance(scored, dict) or set(scored) != set(TRIGGER_SCORE_KEYS):
        raise ValueError(f"trigger score keys must be exactly {sorted(TRIGGER_SCORE_KEYS)}")
    if scored["schema_version"] != SCHEMA_VERSION:
        raise ValueError("trigger score schema_version mismatch")
    if scored["band"] not in ("hot", "warm", "cold", "blocked"):
        raise ValueError("band must be hot/warm/cold/blocked")
    if not isinstance(scored["score"], int) or not 0 <= scored["score"] <= 100:
        raise ValueError("score must be an int in [0, 100]")


def score_trigger_event(event: dict[str, Any]) -> dict[str, Any]:
    """Score one fresh-domain trigger event for lead qualification.

    Fresh-domain trigger-event scorer
    (``src: classroom/community-vault/the-30k-ai-app-breakdown-2026-08-03``):
    event-type base weight, freshness decay on ``age_days``, evidence and
    domain-match bonuses. DNC gate runs first — a blocked lead scores 0.
    """
    gate = evaluate_outreach_target(
        company=str(event.get("company", "")),
        person_name=str(event.get("person_name", "")),
        url=str(event.get("source_url", "") or event.get("url", "")),
        recipient_domain=str(event.get("domain", "")).lower(),
    )
    event_type = event.get("event_type", "")
    if event_type not in TRIGGER_EVENT_TYPES:
        raise ValueError(f"event_type must be one of {TRIGGER_EVENT_TYPES}")

    domain = str(event.get("domain", "")).lower()
    company = str(event.get("company", ""))
    event_id = _stable_id({
        "domain": domain, "company": company,
        "event_type": event_type, "age_days": event.get("age_days"),
    })

    if not gate.get("allowed"):
        scored = {
            "schema_version": SCHEMA_VERSION,
            "event_id": event_id,
            "domain": domain,
            "company": company,
            "event_type": event_type,
            "score": 0,
            "band": "blocked",
            "freshness": "unknown",
            "signals": [f"dnc_gate:{gate.get('reason', 'blocked')}"],
            "allowed": False,
            "dnc": gate,
        }
        validate_trigger_score(scored)
        return scored

    try:
        age_days = int(event.get("age_days", 10**6))
    except (TypeError, ValueError):
        age_days = 10**6
    if age_days <= 30:
        freshness_mult, freshness_label = 1.0, "fresh:30d"
    elif age_days <= 90:
        freshness_mult, freshness_label = 0.7, "fresh:90d"
    elif age_days <= 180:
        freshness_mult, freshness_label = 0.4, "fresh:180d"
    else:
        freshness_mult, freshness_label = 0.2, "stale"

    raw = TRIGGER_BASE_SCORES[event_type]
    signals = [f"event_type:{event_type}", freshness_label]

    has_evidence = bool(str(event.get("evidence", "")).strip())
    raw += 15 if has_evidence else 0
    signals.append("evidence:yes" if has_evidence else "evidence:no")

    source_url = str(event.get("source_url", "") or event.get("url", ""))
    host = urlparse(source_url).netloc.lower()
    domain_match = bool(domain) and host.endswith(domain)
    raw += 10 if domain_match else 0
    signals.append("domain_match:yes" if domain_match else "domain_match:no")

    score = min(100, round(raw * freshness_mult))
    band = "hot" if score >= 70 else "warm" if score >= 40 else "cold"

    scored = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "domain": domain,
        "company": company,
        "event_type": event_type,
        "score": score,
        "band": band,
        "freshness": freshness_label,
        "signals": signals,
        "allowed": True,
        "dnc": gate,
    }
    validate_trigger_score(scored)
    return scored


def load_blueprint() -> dict[str, Any]:
    """Load the deterministic Nod/n8n blueprint shipped beside this module."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), BLUEPRINT_FILENAME)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def validate_blueprint(blueprint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate the blueprint's separation and non-send invariants.

    Returns {"valid", "errors", "deterministic_nodes", "ai_schema_locked_nodes"}.
    Rules: draft-only send policy; deterministic control plane owns
    pagination/retries/sleeps (max_retries <= 3); every AI node is schema-locked
    (output_schema with required properties and additionalProperties=false) and
    carries no pagination/sleeps/retry keys; a deterministic DNC gate node calls
    ``dnc_guard.evaluate_outreach_target``; cited_sources use ``src: `` paths.
    """
    errors: list[str] = []
    bp = load_blueprint() if blueprint is None else blueprint

    if not isinstance(bp, dict):
        return {"valid": False, "errors": ["blueprint must be an object"],
                "deterministic_nodes": 0, "ai_schema_locked_nodes": 0}

    if bp.get("schema_version") != BLUEPRINT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {BLUEPRINT_SCHEMA_VERSION}")

    send_policy = bp.get("send_policy", {})
    if send_policy.get("draft_only") is not True:
        errors.append("send_policy.draft_only must be True")
    if send_policy.get("send_enabled") is not False:
        errors.append("send_policy.send_enabled must be False")
    if send_policy.get("clients_ai_send") is not False:
        errors.append("send_policy.clients_ai_send must be False")

    nodes = bp.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append("nodes must be a non-empty list")
        nodes = []

    node_ids = set()
    deterministic_count = 0
    ai_count = 0
    has_dnc_gate = False
    for index, node in enumerate(nodes):
        where = f"nodes[{index}]"
        if not isinstance(node, dict):
            errors.append(f"{where} must be an object")
            continue
        node_id = node.get("id")
        if not node_id:
            errors.append(f"{where} missing id")
        else:
            node_ids.add(node_id)
        kind = node.get("kind")
        if kind not in ("deterministic", "ai_schema_locked"):
            errors.append(f"{where} kind must be 'deterministic' or 'ai_schema_locked'")
            continue
        if kind == "deterministic":
            deterministic_count += 1
            calls = node.get("calls", [])
            if node.get("type") == "gate" and any(
                "dnc_guard.evaluate_outreach_target" in str(call) for call in calls
            ):
                has_dnc_gate = True
        else:
            ai_count += 1
            schema = node.get("output_schema")
            if not isinstance(schema, dict):
                errors.append(f"{where} ai_schema_locked node must carry output_schema")
            else:
                properties = schema.get("properties")
                required = schema.get("required")
                if not isinstance(properties, dict) or not properties:
                    errors.append(f"{where} output_schema.properties must be a non-empty object")
                if not isinstance(required, list) or not required:
                    errors.append(f"{where} output_schema.required must be a non-empty list")
                if schema.get("additionalProperties") is not False:
                    errors.append(f"{where} output_schema.additionalProperties must be false")
            for forbidden in AI_NODE_FORBIDDEN_KEYS:
                if forbidden in node:
                    errors.append(f"{where} ai_schema_locked node must not own '{forbidden}' (deterministic control plane does)")

    if nodes and not has_dnc_gate:
        errors.append("no deterministic gate node calls dnc_guard.evaluate_outreach_target")

    control = bp.get("deterministic_control_plane")
    if not isinstance(control, dict):
        errors.append("deterministic_control_plane must be an object")
    else:
        for key in ("pagination", "retries", "sleeps"):
            if key not in control:
                errors.append(f"deterministic_control_plane.{key} is required")
        retries = control.get("retries")
        if isinstance(retries, dict):
            max_retries = retries.get("max_retries")
            if not isinstance(max_retries, int) or isinstance(max_retries, bool) or not 0 <= max_retries <= 3:
                errors.append("deterministic_control_plane.retries.max_retries must be an int <= 3")
        elif "retries" in control:
            errors.append("deterministic_control_plane.retries must be an object")

    for edge_index, edge in enumerate(bp.get("edges", []) or []):
        if not isinstance(edge, dict) or edge.get("from") not in node_ids or edge.get("to") not in node_ids:
            errors.append(f"edges[{edge_index}] must reference existing node ids")

    cited = bp.get("cited_sources")
    if not isinstance(cited, list) or not cited:
        errors.append("cited_sources must be a non-empty list")
    else:
        for source in cited:
            if not isinstance(source, str) or not source.startswith("src: "):
                errors.append(f"cited_sources entry must start with 'src: ': {source!r}")

    return {
        "valid": not errors,
        "errors": errors,
        "deterministic_nodes": deterministic_count,
        "ai_schema_locked_nodes": ai_count,
    }
