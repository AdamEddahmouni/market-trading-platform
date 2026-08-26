"""Backend-independent intelligence repository contract (BUILD 04.5)."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from ..contracts.event import EventV1
from ..contracts.detection import DetectionV1
from ..contracts.evidence import EvidenceV1
from ..contracts.forecast import ForecastV1
from ..contracts.hypothesis import HypothesisV1
from ..contracts.opportunity import OpportunityV1
from ..contracts.outcome import OutcomeV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..contracts.run_manifest import RunManifestV1
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from ..contracts.routing_decision import RoutingDecisionV1
from ..contracts.inference_job import InferenceJobV1
from ..temporal.policy import TemporalIntegrityPolicy


class RepositoryPutResult(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


@runtime_checkable
class IntelligenceRepository(Protocol):
    """Typed persistence boundary for canonical intelligence records."""

    def put_event(self, event: EventV1) -> RepositoryPutResult: ...

    def get_event(self, event_id: str) -> EventV1 | None: ...

    def get_events(self, event_ids: tuple[str, ...] | list[str]) -> tuple[EventV1, ...]: ...

    def put_detection(self, detection: DetectionV1) -> RepositoryPutResult: ...

    def get_detection(self, detection_id: str) -> DetectionV1 | None: ...

    def get_detections_by_snapshot(self, snapshot_id: str) -> tuple[DetectionV1, ...]: ...

    def put_routing_decision(self, decision: RoutingDecisionV1) -> RepositoryPutResult: ...

    def get_routing_decision(self, routing_decision_id: str) -> RoutingDecisionV1 | None: ...

    def get_routes_by_detection(self, detection_id: str) -> tuple[RoutingDecisionV1, ...]: ...

    def put_inference_job(self, job: InferenceJobV1) -> RepositoryPutResult: ...

    def get_inference_job(self, job_id: str) -> InferenceJobV1 | None: ...

    def put_snapshot(self, snapshot: SnapshotV1) -> RepositoryPutResult: ...

    def get_snapshot(self, snapshot_id: str) -> SnapshotV1 | None: ...

    def put_signal(self, signal: SignalV1) -> RepositoryPutResult: ...

    def get_signal(self, signal_id: str) -> SignalV1 | None: ...

    def get_signals(self, signal_ids: tuple[str, ...] | list[str]) -> tuple[SignalV1, ...]: ...

    def put_evidence(self, evidence: EvidenceV1) -> RepositoryPutResult: ...

    def get_evidence(self, evidence_id: str) -> EvidenceV1 | None: ...

    def put_hypothesis(self, hypothesis: HypothesisV1) -> RepositoryPutResult: ...

    def get_hypothesis(self, hypothesis_id: str) -> HypothesisV1 | None: ...

    def put_forecast(self, forecast: ForecastV1) -> RepositoryPutResult: ...

    def get_forecast(self, forecast_id: str) -> ForecastV1 | None: ...

    def put_opportunity(self, opportunity: OpportunityV1) -> RepositoryPutResult: ...

    def get_opportunity(self, opportunity_id: str) -> OpportunityV1 | None: ...

    def put_outcome(self, outcome: OutcomeV1) -> RepositoryPutResult: ...

    def get_outcome(self, outcome_id: str) -> OutcomeV1 | None: ...

    def put_prediction_ledger_entry(self, entry: PredictionLedgerEntryV1) -> RepositoryPutResult: ...

    def get_prediction_ledger_entry(self, ledger_entry_id: str) -> PredictionLedgerEntryV1 | None: ...

    def get_prediction_ledger_entries_by_forecast(
        self, forecast_id: str
    ) -> tuple[PredictionLedgerEntryV1, ...]: ...

    def query_prediction_ledger_entries(
        self,
        *,
        decision_start_ns: int,
        decision_end_ns: int,
        mode: str | None = None,
        scenario_id: str | None = None,
        target_kind: str | None = None,
        horizon_ns: int | None = None,
        limit: int = 1000,
    ) -> tuple[PredictionLedgerEntryV1, ...]: ...

    def put_run_manifest(self, manifest: RunManifestV1) -> RepositoryPutResult: ...

    def get_run_manifest(self, run_id: str) -> RunManifestV1 | None: ...

    def query_events_as_of(
        self,
        decision_time_ns: int,
        *,
        instrument_id: str | None = None,
        event_type: str | None = None,
        limit: int = 1000,
        require_usable: bool = False,
        policy: TemporalIntegrityPolicy | None = None,
    ) -> tuple[EventV1, ...]: ...

    def iter_events_by_availability(
        self,
        *,
        start_time_ns: int,
        end_time_ns: int,
        instrument_id: str | None = None,
        event_type: str | None = None,
        provider_id: str | None = None,
        limit: int | None = None,
    ) -> tuple[EventV1, ...]: ...

    def query_signals_as_of(
        self,
        decision_time_ns: int,
        *,
        instrument_id: str | None = None,
        limit: int = 1000,
        policy: TemporalIntegrityPolicy | None = None,
    ) -> tuple[SignalV1, ...]: ...

    def get_evidence_by_snapshot(self, snapshot_id: str) -> tuple[EvidenceV1, ...]: ...

    def get_forecasts_by_instrument(
        self,
        instrument_id: str,
        *,
        decision_from_ns: int | None = None,
        decision_to_ns: int | None = None,
        limit: int = 1000,
    ) -> tuple[ForecastV1, ...]: ...

    def get_outcomes_by_forecast(self, forecast_id: str) -> tuple[OutcomeV1, ...]: ...

    def get_opportunities_by_instrument(
        self,
        instrument_id: str,
        *,
        valid_at_ns: int | None = None,
        limit: int = 1000,
    ) -> tuple[OpportunityV1, ...]: ...

    def put_research_finding(self, finding) -> RepositoryPutResult: ...

    def get_research_finding(self, finding_id: str): ...

    def put_research_hypothesis(self, hypothesis) -> RepositoryPutResult: ...

    def get_research_hypothesis(self, research_hypothesis_id: str): ...

    def query_experiment_manifests_by_hypothesis(
        self, research_hypothesis_id: str
    ) -> tuple: ...

    def put_experiment_manifest(self, manifest) -> RepositoryPutResult: ...

    def get_experiment_manifest(self, experiment_id: str): ...

    def put_research_lifecycle_event(self, event) -> RepositoryPutResult: ...

    def get_research_lifecycle_events(
        self, entity_id: str
    ) -> tuple: ...

    def check_health(self) -> dict[str, object]: ...


__all__ = ["IntelligenceRepository", "RepositoryPutResult"]
