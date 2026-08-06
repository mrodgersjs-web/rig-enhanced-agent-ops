"""RIG-Enhanced Agent Ops — Action Gate.

Every agent action is routed through the ``ActionGate`` before it is
allowed to touch the world. The gate makes exactly one decision per
action, driven by a single number: the agent's self-reported confidence
for that action.

    confidence >= AUTO_THRESHOLD (0.85)      -> AUTO_EXECUTE
    VALIDATE_THRESHOLD <= confidence < 0.85  -> VALIDATE (execute, then
                                                 optionally confirmed by an
                                                 independent validator)
    confidence <  VALIDATE_THRESHOLD (0.70)  -> ESCALATE (never executes —
                                                 a human or a stronger
                                                 process must decide)

Every decision — auto, validated, escalated, or rejected — is sealed into
a ``ProofPacket`` and appended to an ``AuditTrail``, so "why did the agent
do that" (or "why didn't it") always has an answer on disk.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from .audit_trail import AuditTrail, ProofPacket


class GateStatus(str, Enum):
    """Outcome of a single ActionGate decision."""

    AUTO_EXECUTED = "auto_executed"
    VALIDATED = "validated"
    ESCALATED = "escalated"
    REJECTED = "rejected"


class EscalationRequired(Exception):
    """Raised when an action's confidence is below the validate threshold.

    The action is NEVER executed in this case — ``fn`` is not called at
    all. The exception carries the sealed ``ProofPacket`` recording the
    escalation itself, so the refusal to act is just as auditable as an
    execution would have been.
    """

    def __init__(self, packet: ProofPacket, threshold: float):
        self.packet = packet
        self.threshold = threshold
        super().__init__(
            f"action '{packet.action}' escalated: confidence "
            f"{packet.confidence:.2f} is below the validate threshold "
            f"({threshold:.2f}) — packet #{packet.index} sealed, action was "
            f"never executed"
        )


class ValidationFailed(Exception):
    """Raised when a mid-confidence action's output fails independent validation.

    Unlike ``EscalationRequired``, ``fn`` DID run here — the action already
    happened. The sealed packet (status ``rejected``) is the permanent
    record that it happened and was subsequently judged invalid.
    """

    def __init__(self, packet: ProofPacket):
        self.packet = packet
        super().__init__(
            f"action '{packet.action}' executed at confidence "
            f"{packet.confidence:.2f} but failed independent validation — "
            f"packet #{packet.index} sealed with status 'rejected'"
        )


@dataclass
class GateResult:
    """What ``ActionGate.execute`` returns on success."""

    result: Any
    proof: ProofPacket
    status: GateStatus


class ActionGate:
    """Wraps every agent action with a confidence-gated proof seal.

    Parameters
    ----------
    audit_trail:
        The tamper-evident chain every decision is appended to. A fresh
        ``AuditTrail`` is created if none is supplied.
    validator:
        Optional ``callable(action, input, output) -> bool`` used to
        independently confirm mid-confidence (VALIDATE-band) actions
        before they are allowed to stand. If omitted, VALIDATE-band
        actions execute and are recorded as ``VALIDATED`` without a second
        opinion — callers that need a stronger guarantee should always
        supply one.
    auto_threshold / validate_threshold:
        Override the default 0.85 / 0.70 gate bands. Must satisfy
        ``0 <= validate_threshold <= auto_threshold <= 1``.
    """

    AUTO_THRESHOLD = 0.85
    VALIDATE_THRESHOLD = 0.70

    def __init__(
        self,
        audit_trail: Optional[AuditTrail] = None,
        validator: Optional[Callable[[str, Any, Any], bool]] = None,
        auto_threshold: float = AUTO_THRESHOLD,
        validate_threshold: float = VALIDATE_THRESHOLD,
    ) -> None:
        if not (0.0 <= validate_threshold <= auto_threshold <= 1.0):
            raise ValueError(
                "thresholds must satisfy 0 <= validate_threshold <= "
                "auto_threshold <= 1, got "
                f"validate_threshold={validate_threshold}, "
                f"auto_threshold={auto_threshold}"
            )
        self.audit_trail = audit_trail if audit_trail is not None else AuditTrail()
        self.validator = validator
        self.auto_threshold = auto_threshold
        self.validate_threshold = validate_threshold

    def execute(
        self,
        action: str,
        fn: Callable[..., Any],
        action_input: Any,
        confidence: float,
        *args: Any,
        **kwargs: Any,
    ) -> GateResult:
        """Run ``fn(action_input, *args, **kwargs)`` through the gate.

        Raises ``EscalationRequired`` without ever calling ``fn`` if
        confidence is below ``validate_threshold``. Raises
        ``ValidationFailed`` if ``fn`` runs but the attached validator
        rejects the output — the packet is still sealed and appended (as
        ``rejected``) so the failed attempt stays on the record.
        """
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {confidence}")

        if confidence < self.validate_threshold:
            packet = self.audit_trail.append(
                action=action,
                input_=action_input,
                output=None,
                confidence=confidence,
                status=GateStatus.ESCALATED.value,
                meta={"reason": "confidence below validate_threshold"},
            )
            raise EscalationRequired(packet, self.validate_threshold)

        started = time.monotonic()
        output = fn(action_input, *args, **kwargs)
        duration_ms = round((time.monotonic() - started) * 1000, 3)

        if confidence >= self.auto_threshold:
            status = GateStatus.AUTO_EXECUTED
        else:
            status = GateStatus.VALIDATED
            if self.validator is not None and not self.validator(action, action_input, output):
                packet = self.audit_trail.append(
                    action=action,
                    input_=action_input,
                    output=output,
                    confidence=confidence,
                    status=GateStatus.REJECTED.value,
                    meta={"duration_ms": duration_ms, "reason": "failed independent validation"},
                )
                raise ValidationFailed(packet)

        packet = self.audit_trail.append(
            action=action,
            input_=action_input,
            output=output,
            confidence=confidence,
            status=status.value,
            meta={"duration_ms": duration_ms},
        )
        return GateResult(result=output, proof=packet, status=status)
