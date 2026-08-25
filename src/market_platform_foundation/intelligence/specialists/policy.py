"""Immutable specialist policies for BUILD 11."""

from __future__ import annotations

from dataclasses import dataclass

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts import SemanticEventType


@dataclass(frozen=True, slots=True)
class MicrostructureSpecialistPolicyV1:
    """Deterministic microstructure specialist policy."""

    allow_degraded_inputs: bool = True
    max_evidence_records: int = 1
    supported_semantic_event_types: tuple[SemanticEventType, ...] = (
        SemanticEventType.ORDER_FLOW_REVERSAL,
        SemanticEventType.LIQUIDITY_EVENT,
    )
    evidence_identity_version: str = "microstructure-evidence-sha256-v1"
    version: str = "1"

    def __post_init__(self) -> None:
        if self.max_evidence_records < 1:
            raise ValueError("MICROSTRUCTURE_MAX_EVIDENCE_INVALID")
        normalized = tuple(
            sorted({SemanticEventType(str(item)) for item in self.supported_semantic_event_types}, key=lambda row: row.value)
        )
        object.__setattr__(self, "supported_semantic_event_types", normalized)

    @property
    def identity(self) -> str:
        payload = {
            "policy_version": self.version,
            "allow_degraded_inputs": self.allow_degraded_inputs,
            "max_evidence_records": self.max_evidence_records,
            "supported_semantic_event_types": [item.value for item in self.supported_semantic_event_types],
            "evidence_identity_version": self.evidence_identity_version,
        }
        return f"MSPOL-{sha256_bytes(canonical_bytes(payload))}"


DEFAULT_MICROSTRUCTURE_SPECIALIST_POLICY = MicrostructureSpecialistPolicyV1()


__all__ = [
    "DEFAULT_MICROSTRUCTURE_SPECIALIST_POLICY",
    "MicrostructureSpecialistPolicyV1",
]
