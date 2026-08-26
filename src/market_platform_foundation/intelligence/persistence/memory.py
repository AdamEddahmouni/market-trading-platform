"""In-memory intelligence repository (BUILD 04.5)."""

from __future__ import annotations

import copy
import threading
from typing import Any

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
from .codec import CODEC_BY_TYPE, RECORD_CODECS, RecordT, canonical_semantic_equal, codec_for_record, encode_document
from .errors import RepositoryConflictError
from .queries import (
    filter_evidence_by_snapshot,
    filter_events_by_availability,
    filter_forecasts_by_instrument,
    filter_opportunities_by_instrument,
    filter_outcomes_by_forecast,
    filter_prediction_ledger_entries,
    filter_prediction_ledger_entries_by_forecast,
    query_events_as_of,
    query_signals_as_of,
)
from .repository import RepositoryPutResult

_CODEC_BY_TYPE = CODEC_BY_TYPE


class InMemoryIntelligenceRepository:
    """Thread-safe reference backend with Mongo-equivalent semantics."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stores: dict[str, dict[str, dict[str, Any]]] = {
            codec.collection_name: {} for codec in RECORD_CODECS
        }
        self._stores["evaluation_reports"] = {}
        self._stores["research_findings"] = {}
        self._stores["research_hypotheses"] = {}
        self._stores["experiment_manifests"] = {}
        self._stores["research_lifecycle_events"] = {}
        self._stores["training_dataset_manifests"] = {}
        self._stores["training_run_manifests"] = {}
        self._stores["candidate_artifacts"] = {}
        self._stores["distillation_dataset_manifests"] = {}

    def put_event(self, event: EventV1) -> RepositoryPutResult:
        return self._put(event)

    def get_event(self, event_id: str) -> EventV1 | None:
        return self._get(EventV1, "events", event_id)

    def get_events(self, event_ids: tuple[str, ...] | list[str]) -> tuple[EventV1, ...]:
        rows: list[EventV1] = []
        for event_id in sorted({str(value) for value in event_ids}):
            event = self.get_event(event_id)
            if event is not None:
                rows.append(event)
        return tuple(rows)

    def put_detection(self, detection: DetectionV1) -> RepositoryPutResult:
        return self._put(detection)

    def get_detection(self, detection_id: str) -> DetectionV1 | None:
        return self._get(DetectionV1, "detections", detection_id)

    def get_detections_by_snapshot(self, snapshot_id: str) -> tuple[DetectionV1, ...]:
        with self._lock:
            rows = [self._decode(DetectionV1, body) for body in self._stores["detections"].values()]
        return tuple(sorted((row for row in rows if row.source_snapshot_ref.id == snapshot_id), key=lambda row: row.detection_id))

    def put_routing_decision(self, decision: RoutingDecisionV1) -> RepositoryPutResult:
        return self._put(decision)

    def get_routing_decision(self, routing_decision_id: str) -> RoutingDecisionV1 | None:
        return self._get(RoutingDecisionV1, "routing_decisions", routing_decision_id)

    def get_routes_by_detection(self, detection_id: str) -> tuple[RoutingDecisionV1, ...]:
        with self._lock:
            rows = [self._decode(RoutingDecisionV1, body) for body in self._stores["routing_decisions"].values()]
        return tuple(sorted((row for row in rows if row.detection_ref.id == detection_id), key=lambda row: row.routing_decision_id))

    def put_inference_job(self, job: InferenceJobV1) -> RepositoryPutResult:
        return self._put(job)

    def get_inference_job(self, job_id: str) -> InferenceJobV1 | None:
        return self._get(InferenceJobV1, "inference_jobs", job_id)

    def put_snapshot(self, snapshot: SnapshotV1) -> RepositoryPutResult:
        return self._put(snapshot)

    def get_snapshot(self, snapshot_id: str) -> SnapshotV1 | None:
        return self._get(SnapshotV1, "snapshots", snapshot_id)

    def put_signal(self, signal: SignalV1) -> RepositoryPutResult:
        return self._put(signal)

    def get_signal(self, signal_id: str) -> SignalV1 | None:
        return self._get(SignalV1, "signals", signal_id)

    def get_signals(self, signal_ids: tuple[str, ...] | list[str]) -> tuple[SignalV1, ...]:
        rows: list[SignalV1] = []
        for signal_id in sorted({str(value) for value in signal_ids}):
            signal = self.get_signal(signal_id)
            if signal is not None:
                rows.append(signal)
        return tuple(rows)

    def put_evidence(self, evidence: EvidenceV1) -> RepositoryPutResult:
        return self._put(evidence)

    def get_evidence(self, evidence_id: str) -> EvidenceV1 | None:
        return self._get(EvidenceV1, "evidence", evidence_id)

    def put_hypothesis(self, hypothesis: HypothesisV1) -> RepositoryPutResult:
        return self._put(hypothesis)

    def get_hypothesis(self, hypothesis_id: str) -> HypothesisV1 | None:
        return self._get(HypothesisV1, "hypotheses", hypothesis_id)

    def put_forecast(self, forecast: ForecastV1) -> RepositoryPutResult:
        return self._put(forecast)

    def get_forecast(self, forecast_id: str) -> ForecastV1 | None:
        return self._get(ForecastV1, "forecasts", forecast_id)

    def put_opportunity(self, opportunity: OpportunityV1) -> RepositoryPutResult:
        return self._put(opportunity)

    def get_opportunity(self, opportunity_id: str) -> OpportunityV1 | None:
        return self._get(OpportunityV1, "opportunities", opportunity_id)

    def put_outcome(self, outcome: OutcomeV1) -> RepositoryPutResult:
        return self._put(outcome)

    def get_outcome(self, outcome_id: str) -> OutcomeV1 | None:
        return self._get(OutcomeV1, "outcomes", outcome_id)

    def put_prediction_ledger_entry(self, entry: PredictionLedgerEntryV1) -> RepositoryPutResult:
        return self._put(entry)

    def get_prediction_ledger_entry(self, ledger_entry_id: str) -> PredictionLedgerEntryV1 | None:
        return self._get(PredictionLedgerEntryV1, "prediction_ledger", ledger_entry_id)

    def get_prediction_ledger_entries_by_forecast(
        self, forecast_id: str
    ) -> tuple[PredictionLedgerEntryV1, ...]:
        with self._lock:
            rows = [
                self._decode(PredictionLedgerEntryV1, body)
                for body in self._stores["prediction_ledger"].values()
            ]
        return filter_prediction_ledger_entries_by_forecast(rows, forecast_id)

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
    ) -> tuple[PredictionLedgerEntryV1, ...]:
        with self._lock:
            rows = [
                self._decode(PredictionLedgerEntryV1, body)
                for body in self._stores["prediction_ledger"].values()
            ]
        return filter_prediction_ledger_entries(
            rows,
            decision_start_ns=decision_start_ns,
            decision_end_ns=decision_end_ns,
            mode=mode,
            scenario_id=scenario_id,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            limit=limit,
        )

    def put_evaluation_report(self, report) -> RepositoryPutResult:
        from ..evaluation.report import evaluation_report_v1_to_dict

        document = evaluation_report_v1_to_dict(report)
        document["_id"] = report.report_id
        with self._lock:
            store = self._stores["evaluation_reports"]
            existing = store.get(report.report_id)
            if existing is None:
                store[report.report_id] = copy.deepcopy(document)
                return RepositoryPutResult.INSERTED
            if canonical_semantic_equal(existing, document):
                return RepositoryPutResult.ALREADY_PRESENT
            raise RepositoryConflictError(
                f"IMMUTABLE_CONFLICT:evaluation_report:{report.report_id}",
                details={"kind": "evaluation_report", "id": report.report_id},
            )

    def get_evaluation_report(self, report_id: str):
        from ..evaluation.report import evaluation_report_v1_from_dict

        with self._lock:
            body = self._stores["evaluation_reports"].get(report_id)
        if body is None:
            return None
        payload = {k: v for k, v in body.items() if k != "_id"}
        return evaluation_report_v1_from_dict(payload)

    def put_research_finding(self, finding) -> RepositoryPutResult:
        from ..research_experiments.serialization import research_finding_v1_to_dict

        return self._put_sidecar(
            collection="research_findings",
            record_id=finding.finding_id,
            document=research_finding_v1_to_dict(finding),
            kind="research_finding",
        )

    def get_research_finding(self, finding_id: str):
        from ..research_experiments.serialization import research_finding_v1_from_dict

        return self._get_sidecar("research_findings", finding_id, research_finding_v1_from_dict)

    def put_research_hypothesis(self, hypothesis) -> RepositoryPutResult:
        from ..research_experiments.serialization import research_hypothesis_v1_to_dict

        return self._put_sidecar(
            collection="research_hypotheses",
            record_id=hypothesis.research_hypothesis_id,
            document=research_hypothesis_v1_to_dict(hypothesis),
            kind="research_hypothesis",
        )

    def get_research_hypothesis(self, research_hypothesis_id: str):
        from ..research_experiments.serialization import research_hypothesis_v1_from_dict

        return self._get_sidecar(
            "research_hypotheses", research_hypothesis_id, research_hypothesis_v1_from_dict
        )

    def put_experiment_manifest(self, manifest) -> RepositoryPutResult:
        from ..research_experiments.serialization import experiment_manifest_v1_to_dict

        return self._put_sidecar(
            collection="experiment_manifests",
            record_id=manifest.experiment_id,
            document=experiment_manifest_v1_to_dict(manifest),
            kind="experiment_manifest",
        )

    def get_experiment_manifest(self, experiment_id: str):
        from ..research_experiments.serialization import experiment_manifest_v1_from_dict

        return self._get_sidecar(
            "experiment_manifests", experiment_id, experiment_manifest_v1_from_dict
        )

    def query_experiment_manifests_by_hypothesis(
        self, research_hypothesis_id: str
    ) -> tuple:
        from ..research_experiments.serialization import experiment_manifest_v1_from_dict

        with self._lock:
            bodies = list(self._stores["experiment_manifests"].values())
        rows = []
        for body in bodies:
            manifest = experiment_manifest_v1_from_dict(
                {k: v for k, v in body.items() if k != "_id"}
            )
            if manifest.research_hypothesis_id == research_hypothesis_id:
                rows.append(manifest)
        return tuple(sorted(rows, key=lambda row: row.experiment_id))

    def put_research_lifecycle_event(self, event) -> RepositoryPutResult:
        from ..research_experiments.serialization import research_lifecycle_event_v1_to_dict

        return self._put_sidecar(
            collection="research_lifecycle_events",
            record_id=event.event_id,
            document=research_lifecycle_event_v1_to_dict(event),
            kind="research_lifecycle_event",
        )

    def get_research_lifecycle_events(self, entity_id: str) -> tuple:
        from ..research_experiments.serialization import research_lifecycle_event_v1_from_dict

        with self._lock:
            bodies = list(self._stores["research_lifecycle_events"].values())
        rows = []
        for body in bodies:
            event = research_lifecycle_event_v1_from_dict(
                {k: v for k, v in body.items() if k != "_id"}
            )
            if event.entity_id == entity_id:
                rows.append(event)
        return tuple(sorted(rows, key=lambda row: (row.recorded_at_ns, row.event_id)))

    def put_training_dataset_manifest(self, manifest) -> RepositoryPutResult:
        from ..training.serialization import training_dataset_manifest_v1_to_dict

        return self._put_sidecar(
            collection="training_dataset_manifests",
            record_id=manifest.training_dataset_id,
            document=training_dataset_manifest_v1_to_dict(manifest),
            kind="training_dataset_manifest",
        )

    def get_training_dataset_manifest(self, training_dataset_id: str):
        from ..training.serialization import training_dataset_manifest_v1_from_dict

        return self._get_sidecar(
            "training_dataset_manifests", training_dataset_id, training_dataset_manifest_v1_from_dict
        )

    def put_training_run_manifest(self, run) -> RepositoryPutResult:
        from ..training.serialization import training_run_manifest_v1_to_dict

        return self._put_sidecar(
            collection="training_run_manifests",
            record_id=run.training_run_id,
            document=training_run_manifest_v1_to_dict(run),
            kind="training_run_manifest",
        )

    def get_training_run_manifest(self, training_run_id: str):
        from ..training.serialization import training_run_manifest_v1_from_dict

        return self._get_sidecar(
            "training_run_manifests", training_run_id, training_run_manifest_v1_from_dict
        )

    def put_candidate_artifact(self, candidate) -> RepositoryPutResult:
        from ..training.serialization import candidate_artifact_v1_to_dict

        return self._put_sidecar(
            collection="candidate_artifacts",
            record_id=candidate.candidate_id,
            document=candidate_artifact_v1_to_dict(candidate),
            kind="candidate_artifact",
        )

    def get_candidate_artifact(self, candidate_id: str):
        from ..training.serialization import candidate_artifact_v1_from_dict

        return self._get_sidecar("candidate_artifacts", candidate_id, candidate_artifact_v1_from_dict)

    def put_distillation_dataset_manifest(self, manifest) -> RepositoryPutResult:
        from ..training.serialization import distillation_dataset_manifest_v1_to_dict

        return self._put_sidecar(
            collection="distillation_dataset_manifests",
            record_id=manifest.distillation_dataset_id,
            document=distillation_dataset_manifest_v1_to_dict(manifest),
            kind="distillation_dataset_manifest",
        )

    def get_distillation_dataset_manifest(self, distillation_dataset_id: str):
        from ..training.serialization import distillation_dataset_manifest_v1_from_dict

        return self._get_sidecar(
            "distillation_dataset_manifests",
            distillation_dataset_id,
            distillation_dataset_manifest_v1_from_dict,
        )

    def _put_sidecar(
        self,
        *,
        collection: str,
        record_id: str,
        document: dict,
        kind: str,
    ) -> RepositoryPutResult:
        document = dict(document)
        document["_id"] = record_id
        with self._lock:
            store = self._stores[collection]
            existing = store.get(record_id)
            if existing is None:
                store[record_id] = copy.deepcopy(document)
                return RepositoryPutResult.INSERTED
            if canonical_semantic_equal(existing, document):
                return RepositoryPutResult.ALREADY_PRESENT
            raise RepositoryConflictError(
                f"IMMUTABLE_CONFLICT:{kind}:{record_id}",
                details={"kind": kind, "id": record_id},
            )

    def _get_sidecar(self, collection: str, record_id: str, decoder):
        with self._lock:
            body = self._stores[collection].get(record_id)
        if body is None:
            return None
        payload = {k: v for k, v in body.items() if k != "_id"}
        return decoder(payload)

    def put_run_manifest(self, manifest: RunManifestV1) -> RepositoryPutResult:
        return self._put(manifest)

    def get_run_manifest(self, run_id: str) -> RunManifestV1 | None:
        return self._get(RunManifestV1, "run_manifests", run_id)

    def query_events_as_of(
        self,
        decision_time_ns: int,
        *,
        instrument_id: str | None = None,
        event_type: str | None = None,
        limit: int = 1000,
        require_usable: bool = False,
        policy: TemporalIntegrityPolicy | None = None,
    ) -> tuple[EventV1, ...]:
        with self._lock:
            events = [self._decode(EventV1, body) for body in self._stores["events"].values()]
        return query_events_as_of(
            events,
            decision_time_ns,
            instrument_id=instrument_id,
            event_type=event_type,
            limit=limit,
            require_usable=require_usable,
            policy=policy,
        )

    def iter_events_by_availability(
        self,
        *,
        start_time_ns: int,
        end_time_ns: int,
        instrument_id: str | None = None,
        event_type: str | None = None,
        provider_id: str | None = None,
        limit: int | None = None,
    ) -> tuple[EventV1, ...]:
        with self._lock:
            events = [self._decode(EventV1, body) for body in self._stores["events"].values()]
        return filter_events_by_availability(
            events,
            start_time_ns=start_time_ns,
            end_time_ns=end_time_ns,
            instrument_id=instrument_id,
            event_type=event_type,
            provider_id=provider_id,
            limit=limit,
        )

    def query_signals_as_of(
        self,
        decision_time_ns: int,
        *,
        instrument_id: str | None = None,
        limit: int = 1000,
        policy: TemporalIntegrityPolicy | None = None,
    ) -> tuple[SignalV1, ...]:
        with self._lock:
            signals = [self._decode(SignalV1, body) for body in self._stores["signals"].values()]
        return query_signals_as_of(
            signals,
            decision_time_ns,
            instrument_id=instrument_id,
            limit=limit,
            policy=policy,
        )

    def get_evidence_by_snapshot(self, snapshot_id: str) -> tuple[EvidenceV1, ...]:
        with self._lock:
            rows = [self._decode(EvidenceV1, body) for body in self._stores["evidence"].values()]
        return filter_evidence_by_snapshot(rows, snapshot_id)

    def get_forecasts_by_instrument(
        self,
        instrument_id: str,
        *,
        decision_from_ns: int | None = None,
        decision_to_ns: int | None = None,
        limit: int = 1000,
    ) -> tuple[ForecastV1, ...]:
        with self._lock:
            rows = [self._decode(ForecastV1, body) for body in self._stores["forecasts"].values()]
        return filter_forecasts_by_instrument(
            rows,
            instrument_id,
            decision_from_ns=decision_from_ns,
            decision_to_ns=decision_to_ns,
            limit=limit,
        )

    def get_outcomes_by_forecast(self, forecast_id: str) -> tuple[OutcomeV1, ...]:
        with self._lock:
            rows = [self._decode(OutcomeV1, body) for body in self._stores["outcomes"].values()]
        return filter_outcomes_by_forecast(rows, forecast_id)

    def get_opportunities_by_instrument(
        self,
        instrument_id: str,
        *,
        valid_at_ns: int | None = None,
        limit: int = 1000,
    ) -> tuple[OpportunityV1, ...]:
        with self._lock:
            rows = [
                self._decode(OpportunityV1, body) for body in self._stores["opportunities"].values()
            ]
        return filter_opportunities_by_instrument(
            rows,
            instrument_id,
            valid_at_ns=valid_at_ns,
            limit=limit,
        )

    def check_health(self) -> dict[str, object]:
        return {
            "available": True,
            "backend": "in_memory",
            "database": None,
        }

    def _put(self, record: RecordT) -> RepositoryPutResult:
        codec = codec_for_record(record)
        document = encode_document(record)
        record_id = document[codec.id_field]
        with self._lock:
            store = self._stores[codec.collection_name]
            existing = store.get(record_id)
            if existing is None:
                store[record_id] = copy.deepcopy(document)
                return RepositoryPutResult.INSERTED
            if canonical_semantic_equal(existing, document):
                return RepositoryPutResult.ALREADY_PRESENT
            raise RepositoryConflictError(
                f"IMMUTABLE_CONFLICT:{codec.kind.value}:{record_id}",
                details={"kind": codec.kind.value, "id": record_id},
            )

    def _get(self, record_type: type, collection_name: str, record_id: str) -> Any | None:
        with self._lock:
            body = self._stores[collection_name].get(record_id)
            if body is None:
                return None
            return self._decode(record_type, body)

    def _decode(self, record_type: type, body: dict[str, Any]) -> Any:
        codec = _CODEC_BY_TYPE[record_type]
        return codec.from_dict(copy.deepcopy({k: v for k, v in body.items() if k != "_id"}))


__all__ = ["InMemoryIntelligenceRepository"]
