"""RIG-Enhanced Agent Ops — Independent Verifier.

``Verifier`` is deliberately decoupled from ``ActionGate`` and
``AuditTrail``: it only ever looks at an *exported* trail (a JSON string,
a file, or a list of packet dicts) and recomputes every hash — and every
signature, if given the key — from first principles. It never calls back
into the objects that produced the trail, so it cannot be fooled by a
compromised in-process ``AuditTrail`` that lies about its own state; it
only trusts what it can independently recompute from the raw content.

This mirrors how a real audit works: the auditor gets a copy of the
ledger, not a phone call from the ledger's owner assuring them it's fine.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Union

if TYPE_CHECKING:  # pragma: no cover
    from .audit_trail import AuditTrail

GENESIS_HASH = "0" * 64


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _packet_hash(packet: dict) -> str:
    """Recompute a packet's hash straight from its raw dict fields.

    Deliberately reimplemented here (rather than imported from
    ``audit_trail.ProofPacket.compute_hash``) so the verifier's notion of
    "what should this hash be" does not depend on the same code path that
    produced the trail in the first place.
    """
    payload = {
        "index": packet["index"],
        "action": packet["action"],
        "input": packet["input"],
        "output": packet["output"],
        "confidence": packet["confidence"],
        "status": packet["status"],
        "timestamp": packet["timestamp"],
        "prev_hash": packet["prev_hash"],
        "meta": packet.get("meta", {}),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _packet_signature(packet_hash: str, secret: bytes) -> str:
    return hmac.new(secret, packet_hash.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass
class Finding:
    """One integrity or authenticity problem discovered while verifying a trail."""

    index: int
    kind: str  # "index_mismatch" | "chain_break" | "hash_mismatch" | "signature_mismatch"
    message: str

    def to_dict(self) -> dict:
        return {"index": self.index, "kind": self.kind, "message": self.message}


@dataclass
class VerificationReport:
    """Result of running the verifier over a trail."""

    valid: bool
    packet_count: int
    checked_at: str
    findings: List[Finding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "packet_count": self.packet_count,
            "checked_at": self.checked_at,
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


class Verifier:
    """Recomputes an entire hash chain — and every signature, if given a
    key — from a raw exported trail. Never trusts a stored ``hash`` or
    ``signature`` field; every value is independently recomputed and
    compared."""

    def __init__(self, secret: Optional[Union[bytes, str]] = None) -> None:
        if isinstance(secret, str):
            secret = secret.encode("utf-8")
        self.secret: Optional[bytes] = secret

    def verify_packets(self, packets: List[dict]) -> VerificationReport:
        findings: List[Finding] = []
        expected_prev_hash = GENESIS_HASH

        for position, packet in enumerate(packets):
            index = packet.get("index", position)

            if index != position:
                findings.append(
                    Finding(
                        index=index,
                        kind="index_mismatch",
                        message=(
                            f"packet at position {position} claims index {index} "
                            f"— trail was reordered, packets were inserted, or "
                            f"packets were removed"
                        ),
                    )
                )

            if packet.get("prev_hash") != expected_prev_hash:
                findings.append(
                    Finding(
                        index=index,
                        kind="chain_break",
                        message=(
                            f"packet #{index} expected prev_hash "
                            f"{expected_prev_hash[:12]}\u2026, stored "
                            f"{str(packet.get('prev_hash'))[:12]}\u2026"
                        ),
                    )
                )

            recomputed_hash = _packet_hash(packet)
            stored_hash = packet.get("hash")
            if recomputed_hash != stored_hash:
                findings.append(
                    Finding(
                        index=index,
                        kind="hash_mismatch",
                        message=(
                            f"packet #{index} content hash does not match its "
                            f"stored hash — content was modified after sealing"
                        ),
                    )
                )

            if self.secret is not None:
                expected_sig = _packet_signature(stored_hash or "", self.secret)
                if packet.get("signature") != expected_sig:
                    findings.append(
                        Finding(
                            index=index,
                            kind="signature_mismatch",
                            message=(
                                f"packet #{index} signature does not verify "
                                f"against the supplied key — it was not sealed "
                                f"by the expected signer"
                            ),
                        )
                    )

            # Advance the expected chain using the packet's STORED hash, not
            # the recomputed one. This is what makes a single tampered
            # packet a single, precisely located finding instead of a
            # cascade of chain-break findings for every packet after it: a
            # sealed-then-tampered packet keeps the hash it was originally
            # sealed with, which is still exactly what the next packet's
            # prev_hash was written to expect.
            expected_prev_hash = stored_hash or recomputed_hash

        return VerificationReport(
            valid=len(findings) == 0,
            packet_count=len(packets),
            checked_at=datetime.now(timezone.utc).isoformat(),
            findings=findings,
        )

    def verify_json(self, data: str) -> VerificationReport:
        return self.verify_packets(json.loads(data))

    def verify_file(self, path: Union[str, Path]) -> VerificationReport:
        return self.verify_json(Path(path).read_text(encoding="utf-8"))

    def verify_trail(self, audit_trail: "AuditTrail") -> VerificationReport:
        """Convenience entry point for verifying a live ``AuditTrail`` in-process.

        Still only ever inspects exported plain dicts — the verifier never
        calls ``audit_trail.verify()`` or reaches into its private state.
        """
        return self.verify_packets([p.to_dict() for p in audit_trail.packets])
