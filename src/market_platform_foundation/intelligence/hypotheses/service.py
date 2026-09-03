"""Hypothesis evaluation service for BUILD 13."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..contracts import EvidenceV1, HypothesisV1
from ..council.blackboard import BlackboardSnapshot
from ..council.models import EvidenceRelationReport
from ..council.provenance import EvidenceProvenanceResolver
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from .registry import DEFAULT_HYPOTHESIS_ENGINE_REGISTRY, HypothesisEngineRegistry
from .types import HypothesisEvaluationContext, HypothesisEvaluationResult, HypothesisEvaluationStatus, HypothesisType


@dataclass
class HypothesisEvaluationService:
    repository: IntelligenceRepository
    engine_registry: HypothesisEngineRegistry = DEFAULT_HYPOTHESIS_ENGINE_REGISTRY
    provenance_resolver: EvidenceProvenanceResolver | None = None

    def __post_init__(self) -> None:
        if self.provenance_resolver is None:
            self.provenance_resolver = EvidenceProvenanceResolver(self.repository)

    def evaluate_short_squeeze(
        self,
        *,
        blackboard: BlackboardSnapshot,
        relation_report: EvidenceRelationReport,
        evidence_by_id: Mapping[str, EvidenceV1] | None = None,
        decision_time_ns: int | None = None,
        persist: bool = False,
    ) -> HypothesisEvaluationResult:
        resolved = dict(evidence_by_id or self._resolve_blackboard_evidence(blackboard))
        snapshot = self.repository.get_snapshot(blackboard.source_snapshot_id)
        engine = self.engine_registry.get(HypothesisType.SHORT_SQUEEZE_SETUP.value)
        context = HypothesisEvaluationContext(
            blackboard=blackboard,
            relation_report=relation_report,
            evidence_by_id=resolved,
            snapshot=snapshot,
            decision_time_ns=decision_time_ns,
        )
        result = engine.evaluate(context)
        if persist and result.hypothesis is not None:
            self.repository.put_hypothesis(result.hypothesis)
        return result

    def persist_result(self, result: HypothesisEvaluationResult) -> RepositoryPutResult | None:
        if result.hypothesis is None:
            return None
        return self.repository.put_hypothesis(result.hypothesis)

    def _resolve_blackboard_evidence(self, blackboard: BlackboardSnapshot) -> dict[str, EvidenceV1]:
        resolved: dict[str, EvidenceV1] = {}
        for evidence_id in blackboard.evidence_refs:
            evidence = self.repository.get_evidence(evidence_id)
            if evidence is None:
                raise ValueError(f"HYPOTHESIS_MISSING_EVIDENCE:{evidence_id}")
            resolved[evidence_id] = evidence
        return resolved


def emitted(result: HypothesisEvaluationResult) -> bool:
    return result.status in {
        HypothesisEvaluationStatus.EMITTED,
        HypothesisEvaluationStatus.EMITTED_CONTESTED,
    }


__all__ = ["HypothesisEvaluationService", "emitted"]
