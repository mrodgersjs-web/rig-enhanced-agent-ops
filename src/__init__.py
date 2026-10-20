"""RIG-Enhanced Agent Ops — proof-gated agent operations with a tamper-evident,
HMAC-signed audit trail.

    from src.action_gate import ActionGate, GateStatus, EscalationRequired
    from src.audit_trail import AuditTrail, ProofPacket
    from src.verifier import Verifier, VerificationReport

See README.md for the end-to-end example.
"""
from .action_gate import (
    ActionGate,
    EscalationRequired,
    GateResult,
    GateStatus,
    ValidationFailed,
)
from .audit_trail import GENESIS_HASH, AuditTrail, ProofPacket
from .verifier import Finding, VerificationReport, Verifier

__version__ = "0.1.0"

__all__ = [
    "ActionGate",
    "GateResult",
    "GateStatus",
    "EscalationRequired",
    "ValidationFailed",
    "AuditTrail",
    "ProofPacket",
    "GENESIS_HASH",
    "Verifier",
    "VerificationReport",
    "Finding",
    "__version__",
]
