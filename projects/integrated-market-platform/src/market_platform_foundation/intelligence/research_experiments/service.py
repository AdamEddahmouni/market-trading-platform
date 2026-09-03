"""Research experiment orchestration service (BUILD 17)."""

from __future__ import annotations

from dataclasses import dataclass

from ..evaluation.types import EvaluationReportV1
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from .builders import build_research_hypothesis, design_experiment
from .findings import DEFAULT_FINDING_POLICY, extract_findings
from .identity import derive_lifecycle_event_id
from .types import (
    ResearchEntityKind,
    ResearchFindingV1,
    ResearchHypothesisV1,
    ExperimentManifestV1,
    ResearchLifecycleEventV1,
    ResearchLifecycleState,
)


@dataclass
class ResearchExperimentService:
    repository: IntelligenceRepository

    def register_finding(
        self,
        finding: ResearchFindingV1,
        *,
        recorded_at_ns: int,
        persist: bool = True,
    ) -> RepositoryPutResult | None:
        if persist:
            result = self.repository.put_research_finding(finding)
            self._record_lifecycle(
                entity_kind=ResearchEntityKind.RESEARCH_FINDING,
                entity_id=finding.finding_id,
                state=ResearchLifecycleState.REGISTERED,
                recorded_at_ns=recorded_at_ns,
            )
            return result
        return None

    def register_hypothesis(
        self,
        hypothesis: ResearchHypothesisV1,
        *,
        recorded_at_ns: int,
        persist: bool = True,
    ) -> RepositoryPutResult | None:
        for finding_id in hypothesis.source_finding_ids:
            if self.repository.get_research_finding(finding_id) is None:
                from .errors import ResearchExperimentError

                raise ResearchExperimentError(
                    "SOURCE_FINDING_NOT_FOUND",
                    details={"finding_id": finding_id},
                )
        if persist:
            result = self.repository.put_research_hypothesis(hypothesis)
            self._record_lifecycle(
                entity_kind=ResearchEntityKind.RESEARCH_HYPOTHESIS,
                entity_id=hypothesis.research_hypothesis_id,
                state=ResearchLifecycleState.REGISTERED,
                recorded_at_ns=recorded_at_ns,
            )
            return result
        return None

    def register_experiment(
        self,
        manifest: ExperimentManifestV1,
        *,
        recorded_at_ns: int,
        persist: bool = True,
    ) -> RepositoryPutResult | None:
        if self.repository.get_research_hypothesis(manifest.research_hypothesis_id) is None:
            from .errors import ResearchExperimentError

            raise ResearchExperimentError(
                "HYPOTHESIS_NOT_FOUND",
                details={"research_hypothesis_id": manifest.research_hypothesis_id},
            )
        if persist:
            result = self.repository.put_experiment_manifest(manifest)
            self._record_lifecycle(
                entity_kind=ResearchEntityKind.EXPERIMENT_MANIFEST,
                entity_id=manifest.experiment_id,
                state=ResearchLifecycleState.REGISTERED,
                recorded_at_ns=recorded_at_ns,
            )
            self._record_lifecycle(
                entity_kind=ResearchEntityKind.RESEARCH_HYPOTHESIS,
                entity_id=manifest.research_hypothesis_id,
                state=ResearchLifecycleState.EXPERIMENT_DESIGNED,
                recorded_at_ns=recorded_at_ns,
            )
            return result
        return None

    def extract_and_register_findings(
        self,
        report: EvaluationReportV1,
        *,
        mode: str,
        scenario_id: str | None = None,
        recorded_at_ns: int,
        persist: bool = True,
    ) -> tuple[ResearchFindingV1, ...]:
        findings = extract_findings(report, mode=mode, scenario_id=scenario_id)
        if persist:
            for finding in findings:
                self.register_finding(finding, recorded_at_ns=recorded_at_ns, persist=True)
        return findings

    def _record_lifecycle(
        self,
        *,
        entity_kind: ResearchEntityKind,
        entity_id: str,
        state: ResearchLifecycleState,
        recorded_at_ns: int,
    ) -> None:
        event_id = derive_lifecycle_event_id(
            entity_kind=entity_kind.value,
            entity_id=entity_id,
            lifecycle_state=state.value,
            recorded_at_ns=recorded_at_ns,
        )
        event = ResearchLifecycleEventV1(
            event_id=event_id,
            schema_version="1",
            entity_kind=entity_kind,
            entity_id=entity_id,
            lifecycle_state=state,
            recorded_at_ns=recorded_at_ns,
        )
        self.repository.put_research_lifecycle_event(event)


__all__ = ["ResearchExperimentService"]
