"""Explicit evidence provenance resolution for BUILD 12."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts import ContractKind, EvidenceV1
from ..persistence.repository import IntelligenceRepository
from .errors import ProvenanceResolutionError
from .identity import derive_source_signature_id
from .models import SourceIndependence, SourceOverlap, SourceSignature


@dataclass(frozen=True, slots=True)
class EvidenceProvenanceResolver:
    repository: IntelligenceRepository

    def resolve_terminal_sources(self, evidence: EvidenceV1) -> SourceSignature:
        terminal_ids: set[str] = set()

        if evidence.source_event_refs:
            for ref in evidence.source_event_refs:
                terminal_ids.add(ref.id)

        if evidence.source_signal_refs:
            signals = self.repository.get_signals(
                tuple(ref.id for ref in evidence.source_signal_refs)
            )
            signal_by_id = {signal.signal_id: signal for signal in signals}
            for ref in evidence.source_signal_refs:
                signal = signal_by_id.get(ref.id)
                if signal is None:
                    raise ProvenanceResolutionError(f"MISSING_SIGNAL:{ref.id}")
                if signal.source_event_refs:
                    for event_ref in signal.source_event_refs:
                        terminal_ids.add(event_ref.id)
                else:
                    terminal_ids.add(signal.signal_id)

        if not terminal_ids:
            return SourceSignature(
                signature_id=derive_source_signature_id(terminal_source_ids=()),
                terminal_source_ids=(),
            )

        signature_id = derive_source_signature_id(terminal_source_ids=tuple(terminal_ids))
        return SourceSignature(signature_id=signature_id, terminal_source_ids=tuple(terminal_ids))

    def classify_overlap(
        self,
        signature_a: SourceSignature,
        signature_b: SourceSignature,
    ) -> SourceOverlap:
        set_a = set(signature_a.terminal_source_ids)
        set_b = set(signature_b.terminal_source_ids)
        intersection = tuple(sorted(set_a & set_b))
        union = tuple(sorted(set_a | set_b))
        if not set_a or not set_b:
            independence = SourceIndependence.UNKNOWN
        elif set_a == set_b and set_a:
            independence = SourceIndependence.STRONGLY_CORRELATED
        elif intersection:
            independence = SourceIndependence.CORRELATED
        else:
            independence = SourceIndependence.SOURCE_INDEPENDENT
        jaccard = None
        if union:
            jaccard = len(intersection) / len(union)
        return SourceOverlap(
            evidence_a_id="",
            evidence_b_id="",
            intersection=intersection,
            union=union,
            independence=independence,
            overlap_count=len(intersection),
            jaccard=jaccard,
        )


def terminal_source_kind(source_id: str) -> str:
    if source_id.startswith("EVT-"):
        return ContractKind.EVENT.value
    if source_id.startswith("SIG-"):
        return ContractKind.SIGNAL.value
    return "unknown"


__all__ = ["EvidenceProvenanceResolver", "terminal_source_kind"]
