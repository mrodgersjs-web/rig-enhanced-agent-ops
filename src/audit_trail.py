"""RIG-Enhanced Agent Ops — Audit Trail.

A tamper-evident, blockchain-style chain of ProofPackets. Each packet's
hash is computed over its own content *plus* the hash of the packet before
it, so any edit, deletion, reordering, or truncation anywhere in the chain
changes every downstream hash reference and is detectable by recomputing
hashes from the genesis block forward — the same construction that gives a
blockchain its tamper-evidence, applied to a single agent's action log.

Optionally HMAC-signed: if a secret key is supplied, each packet also
carries a signature that only a holder of the same key can produce or
verify. This separates two different guarantees:

  * integrity  — "has anything in this trail changed since it was sealed?"
                 answered by the hash chain alone, no secret required.
  * authenticity — "was this trail actually produced by us?"
                 answered by the HMAC signatures, which do require the key.

A trail can be exported to JSON (``to_json`` / ``from_json``) so it can be
shipped to an independent auditor (see ``verifier.py``) that never shares
process memory with the ``ActionGate`` that produced it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

GENESIS_HASH = "0" * 64
_ENV_SECRET_VAR = "RIG_PROOF_SECRET"


def _canonical_json(obj: Any) -> str:
    """Deterministic JSON encoding used for every hash/signature input.

    Sorted keys + fixed separators guarantee the same logical content
    always serializes to the same bytes, which is a precondition for
    hashes being comparable across processes and languages.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_secret(secret: bytes | str | None) -> bytes | None:
    if secret is None:
        return None
    if isinstance(secret, str):
        return secret.encode("utf-8")
    return secret


@dataclass
class ProofPacket:
    """One sealed, auditable record of a single gated agent action.

    ``hash`` and ``signature`` are populated by :meth:`seal` and are never
    set directly — they are always a deterministic function of the other
    fields, which is exactly what makes tampering detectable: change any
    other field without re-sealing and ``hash``/``signature`` stop matching
    their recomputed values.
    """

    index: int
    action: str
    input: Any
    output: Any
    confidence: float
    status: str
    timestamp: str
    prev_hash: str
    meta: dict = field(default_factory=dict)
    hash: str = ""
    signature: str | None = None

    def _payload(self) -> dict:
        """Everything that participates in the hash. Never includes
        ``hash``/``signature`` themselves — a hash cannot include itself."""
        return {
            "index": self.index,
            "action": self.action,
            "input": self.input,
            "output": self.output,
            "confidence": self.confidence,
            "status": self.status,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "meta": self.meta,
        }

    def compute_hash(self) -> str:
        return hashlib.sha256(_canonical_json(self._payload()).encode("utf-8")).hexdigest()

    def compute_signature(self, secret: bytes) -> str:
        """HMAC-SHA256 over the sealed hash — proves *who* sealed this packet."""
        return hmac.new(secret, self.hash.encode("utf-8"), hashlib.sha256).hexdigest()

    def seal(self, secret: bytes | None = None) -> ProofPacket:
        """Compute and store ``hash`` (and ``signature``, if a secret is given).

        Must be called exactly once, immediately after construction, before
        the packet is appended to a trail. ``AuditTrail.append`` does this
        for you — call it directly only when constructing packets outside
        an ``AuditTrail`` (e.g. in tests).
        """
        self.hash = self.compute_hash()
        if secret is not None:
            self.signature = self.compute_signature(secret)
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ProofPacket:
        return cls(**data)


class AuditTrail:
    """An append-only, hash-chained sequence of ProofPackets.

    Parameters
    ----------
    secret:
        Optional HMAC key (``bytes`` or ``str``) used to sign every packet
        as it is sealed. Falls back to the ``RIG_PROOF_SECRET`` environment
        variable, then to ``None`` (unsigned — integrity is still fully
        enforced by the hash chain, only authenticity is unavailable).
    """

    def __init__(self, secret: bytes | str | None = None) -> None:
        self._packets: list[ProofPacket] = []
        if secret is None:
            secret = os.environ.get(_ENV_SECRET_VAR)
        self._secret: bytes | None = _coerce_secret(secret)

    @property
    def packets(self) -> list[ProofPacket]:
        return list(self._packets)

    @property
    def is_signed(self) -> bool:
        return self._secret is not None

    def __len__(self) -> int:
        return len(self._packets)

    def __iter__(self):
        return iter(self._packets)

    def latest_hash(self) -> str:
        return self._packets[-1].hash if self._packets else GENESIS_HASH

    def append(
        self,
        action: str,
        input_: Any,
        output: Any,
        confidence: float,
        status: str,
        meta: dict | None = None,
    ) -> ProofPacket:
        """Seal a new ProofPacket referencing the current chain head and append it.

        This is the *only* way a packet should enter the trail — it is
        what guarantees ``prev_hash`` always points at the real previous
        packet's hash, which is the entire tamper-evidence property.
        """
        packet = ProofPacket(
            index=len(self._packets),
            action=action,
            input=input_,
            output=output,
            confidence=confidence,
            status=status,
            timestamp=_now(),
            prev_hash=self.latest_hash(),
            meta=meta or {},
        )
        packet.seal(self._secret)
        self._packets.append(packet)
        return packet

    def verify(
        self, secret: bytes | str | None = None
    ) -> tuple[bool, str | None]:
        """Recompute every hash (and signature, if a key is available) from genesis.

        Returns ``(True, None)`` if the trail is fully intact, or
        ``(False, reason)`` at the first point of failure. Reordering two
        otherwise-untouched packets breaks the ``prev_hash`` chain just as
        surely as editing a field does.
        """
        secret_bytes = _coerce_secret(secret) if secret is not None else self._secret

        prev_hash = GENESIS_HASH
        for i, packet in enumerate(self._packets):
            if packet.index != i:
                return False, f"index mismatch at position {i}: packet claims index {packet.index}"
            if packet.prev_hash != prev_hash:
                return False, (
                    f"chain break at packet #{packet.index}: expected prev_hash "
                    f"{prev_hash[:12]}\u2026, found {packet.prev_hash[:12]}\u2026"
                )
            recomputed = packet.compute_hash()
            if recomputed != packet.hash:
                return False, (
                    f"tamper detected at packet #{packet.index}: stored hash "
                    f"{packet.hash[:12]}\u2026 does not match recomputed "
                    f"{recomputed[:12]}\u2026 — content was modified after sealing"
                )
            if secret_bytes is not None:
                expected_sig = packet.compute_signature(secret_bytes)
                if packet.signature != expected_sig:
                    return False, (
                        f"signature invalid at packet #{packet.index}: packet "
                        f"was not sealed with the expected key"
                    )
            prev_hash = packet.hash
        return True, None

    def to_json(self) -> str:
        """Export the trail as plain JSON — the format an independent
        ``Verifier`` consumes. Never includes the signing secret."""
        return _canonical_json([p.to_dict() for p in self._packets])

    @classmethod
    def from_json(cls, data: str, secret: bytes | str | None = None) -> AuditTrail:
        trail = cls(secret=secret)
        for raw in json.loads(data):
            trail._packets.append(ProofPacket.from_dict(raw))
        return trail

    def tamper(self, index: int, **field_updates: Any) -> ProofPacket:
        """Test/demo helper: mutate a sealed packet WITHOUT resealing it.

        This intentionally produces an inconsistent trail. It exists so the
        L10 smoke harness and the test suite can prove ``verify()`` (and
        ``Verifier``) actually catch tampering instead of trusting the
        stored ``hash``/``signature`` fields blindly. Real agent code
        should never call this — the only legitimate way to add a packet
        is ``append``.
        """
        if not 0 <= index < len(self._packets):
            raise IndexError(f"packet index {index} out of range (0..{len(self._packets) - 1})")
        packet = self._packets[index]
        for key, value in field_updates.items():
            setattr(packet, key, value)
        return packet
