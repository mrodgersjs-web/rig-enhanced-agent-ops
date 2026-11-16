"""Move 2: Nod/n8n -> Jev -> Twenty CRM -> Aside Gate-D reply & trigger pipeline.

Draft-only by construction: nothing in this package sends anything.
"""

from .pipeline import (
    BLUEPRINT_SCHEMA_VERSION,
    CLIENTS_AI_ENDPOINT,
    CONTACT_BRIEF_KEYS,
    GATE_D_CARD_KEYS,
    REPLY_CLASSES,
    REPLY_RECORD_KEYS,
    SCHEMA_VERSION,
    TRIGGER_EVENT_TYPES,
    TRIGGER_SCORE_KEYS,
    build_contact_brief,
    build_gate_d_card,
    classify_reply,
    load_blueprint,
    score_trigger_event,
    validate_blueprint,
    validate_contact_brief,
    validate_reply_record,
    validate_trigger_score,
)

__all__ = [
    "BLUEPRINT_SCHEMA_VERSION",
    "CLIENTS_AI_ENDPOINT",
    "CONTACT_BRIEF_KEYS",
    "GATE_D_CARD_KEYS",
    "REPLY_CLASSES",
    "REPLY_RECORD_KEYS",
    "SCHEMA_VERSION",
    "TRIGGER_EVENT_TYPES",
    "TRIGGER_SCORE_KEYS",
    "build_contact_brief",
    "build_gate_d_card",
    "classify_reply",
    "load_blueprint",
    "score_trigger_event",
    "validate_blueprint",
    "validate_contact_brief",
    "validate_reply_record",
    "validate_trigger_score",
]
