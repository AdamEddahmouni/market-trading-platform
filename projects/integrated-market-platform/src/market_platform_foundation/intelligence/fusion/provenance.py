"""Explicit forecast provenance resolution for BUILD 14."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts import ContractKind, ForecastV1, HypothesisV1
from ..persistence.repository import IntelligenceRepository
from .errors import FusionDependenceError


@dataclass(frozen=True, slots=True)
class ForecastProvenanceResolver:
    repository: IntelligenceRepository

    def resolve_terminal_source_ids(self, forecast: ForecastV1) -> frozenset[str]:
        terminal_ids: set[str] = set()
        for ref in forecast.lineage_refs:
            if ref.kind == ContractKind.SIGNAL.value:
                terminal_ids.update(self._resolve_signal_terminal(ref.id))
            elif ref.kind == ContractKind.EVIDENCE.value:
                terminal_ids.update(self._resolve_evidence_terminal(ref.id))
            elif ref.kind == ContractKind.EVENT.value:
                terminal_ids.add(ref.id)
            else:
                terminal_ids.add(ref.id)

        for ref in forecast.source_evidence_refs:
            terminal_ids.update(self._resolve_evidence_terminal(ref.id))

        for ref in forecast.source_hypothesis_refs:
            terminal_ids.update(self._resolve_hypothesis_terminal(ref.id))

        return frozenset(terminal_ids)

    def _resolve_signal_terminal(self, signal_id: str) -> set[str]:
        signal = self.repository.get_signal(signal_id)
        if signal is None:
            return {signal_id}
        if signal.source_event_refs:
            return {event_ref.id for event_ref in signal.source_event_refs}
        return {signal.signal_id}

    def _resolve_evidence_terminal(self, evidence_id: str) -> set[str]:
        evidence = self.repository.get_evidence(evidence_id)
        if evidence is None:
            raise FusionDependenceError(f"MISSING_EVIDENCE:{evidence_id}")
        terminal_ids: set[str] = set()
        for ref in evidence.source_event_refs:
            terminal_ids.add(ref.id)
        for ref in evidence.source_signal_refs:
            terminal_ids.update(self._resolve_signal_terminal(ref.id))
        return terminal_ids

    def _resolve_hypothesis_terminal(self, hypothesis_id: str) -> set[str]:
        hypothesis = self.repository.get_hypothesis(hypothesis_id)
        if hypothesis is None:
            raise FusionDependenceError(f"MISSING_HYPOTHESIS:{hypothesis_id}")
        return self._resolve_hypothesis_record_terminal(hypothesis)

    def _resolve_hypothesis_record_terminal(self, hypothesis: HypothesisV1) -> set[str]:
        terminal_ids: set[str] = set()
        for evidence_id in hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids:
            terminal_ids.update(self._resolve_evidence_terminal(evidence_id))
        return terminal_ids


__all__ = ["ForecastProvenanceResolver"]
