"""MongoDB operational intelligence repository (BUILD 04.5)."""

from __future__ import annotations

from typing import Any

from ..codec import (
    RECORD_CODECS,
    RecordT,
    canonical_semantic_equal,
    codec_for_record,
    decode_document,
    encode_document,
)
from ..errors import RepositoryConflictError, RepositoryUnavailableError, RepositoryValidationError
from ..queries import (
    filter_evidence_by_snapshot,
    filter_events_by_availability,
    filter_forecasts_by_instrument,
    filter_opportunities_by_instrument,
    filter_outcomes_by_forecast,
    filter_prediction_ledger_entries,
    filter_prediction_ledger_entries_by_forecast,
    mongo_event_availability_range_filter,
    mongo_event_candidate_filter,
    mongo_event_sort,
    query_events_as_of,
    query_signals_as_of,
    validate_limit,
)
from ..repository import RepositoryPutResult
from ...contracts.event import EventV1
from ...contracts.detection import DetectionV1
from ...contracts.evidence import EvidenceV1
from ...contracts.forecast import ForecastV1
from ...contracts.hypothesis import HypothesisV1
from ...contracts.opportunity import OpportunityV1
from ...contracts.outcome import OutcomeV1
from ...contracts.prediction_ledger import PredictionLedgerEntryV1
from ...contracts.run_manifest import RunManifestV1
from ...contracts.signal import SignalV1
from ...contracts.snapshot import SnapshotV1
from ...contracts.routing_decision import RoutingDecisionV1
from ...contracts.inference_job import InferenceJobV1
from ...temporal.policy import TemporalIntegrityPolicy
from .config import MongoRepositoryConfig, redact_mongo_uri
from .schema import MongoSchemaManager

_CODEC_BY_COLLECTION = {codec.collection_name: codec for codec in RECORD_CODECS}


def _import_pymongo() -> Any:
    try:
        from pymongo import MongoClient
        from pymongo.errors import DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError
    except ImportError as exc:
        raise RepositoryUnavailableError(
            "PYMONGO_NOT_INSTALLED",
            details={"reason": str(exc)},
        ) from exc
    return MongoClient, DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError


class MongoIntelligenceRepository:
    """Synchronous PyMongo persistence backend."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        database_name: str | None = None,
        owns_client: bool = False,
        config: MongoRepositoryConfig | None = None,
    ) -> None:
        MongoClient, _, _, _ = _import_pymongo()
        if client is None:
            if config is None:
                raise ValueError("MONGO_CLIENT_OR_CONFIG_REQUIRED")
            client = MongoClient(
                config.uri,
                serverSelectionTimeoutMS=config.server_selection_timeout_ms,
                appname=config.application_name,
            )
            owns_client = True
            database_name = config.database_name
        if database_name is None:
            raise ValueError("MONGODB_DATABASE_REQUIRED")
        self._client = client
        self._database = client[database_name]
        self._owns_client = owns_client
        self._database_name = database_name
        self._schema_manager = MongoSchemaManager(self._database)

    @classmethod
    def from_config(cls, config: MongoRepositoryConfig) -> MongoIntelligenceRepository:
        return cls(config=config)

    @classmethod
    def from_uri(
        cls,
        uri: str,
        *,
        database_name: str,
        server_selection_timeout_ms: int = 2000,
        application_name: str | None = "imp-intelligence",
    ) -> MongoIntelligenceRepository:
        config = MongoRepositoryConfig(
            uri=uri,
            database_name=database_name,
            server_selection_timeout_ms=server_selection_timeout_ms,
            application_name=application_name,
        )
        return cls.from_config(config)

    def ensure_schema(self) -> None:
        self._schema_manager.ensure_schema()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def put_event(self, event: EventV1) -> RepositoryPutResult:
        return self._put(event)

    def get_event(self, event_id: str) -> EventV1 | None:
        return self._get("events", event_id, EventV1)

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
        return self._get("detections", detection_id, DetectionV1)

    def get_detections_by_snapshot(self, snapshot_id: str) -> tuple[DetectionV1, ...]:
        codec = _CODEC_BY_COLLECTION["detections"]
        documents = self._database["detections"].find({"source_snapshot_ref.id": snapshot_id}).sort("detection_id", 1)
        return tuple(decode_document(document, codec) for document in documents)

    def put_routing_decision(self, decision: RoutingDecisionV1) -> RepositoryPutResult:
        return self._put(decision)

    def get_routing_decision(self, routing_decision_id: str) -> RoutingDecisionV1 | None:
        return self._get("routing_decisions", routing_decision_id, RoutingDecisionV1)

    def get_routes_by_detection(self, detection_id: str) -> tuple[RoutingDecisionV1, ...]:
        codec = _CODEC_BY_COLLECTION["routing_decisions"]
        documents = self._database["routing_decisions"].find({"detection_ref.id": detection_id}).sort("routing_decision_id", 1)
        return tuple(decode_document(document, codec) for document in documents)

    def put_inference_job(self, job: InferenceJobV1) -> RepositoryPutResult:
        return self._put(job)

    def get_inference_job(self, job_id: str) -> InferenceJobV1 | None:
        return self._get("inference_jobs", job_id, InferenceJobV1)

    def put_snapshot(self, snapshot: SnapshotV1) -> RepositoryPutResult:
        return self._put(snapshot)

    def get_snapshot(self, snapshot_id: str) -> SnapshotV1 | None:
        return self._get("snapshots", snapshot_id, SnapshotV1)

    def put_signal(self, signal: SignalV1) -> RepositoryPutResult:
        return self._put(signal)

    def get_signal(self, signal_id: str) -> SignalV1 | None:
        return self._get("signals", signal_id, SignalV1)

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
        return self._get("evidence", evidence_id, EvidenceV1)

    def put_hypothesis(self, hypothesis: HypothesisV1) -> RepositoryPutResult:
        return self._put(hypothesis)

    def get_hypothesis(self, hypothesis_id: str) -> HypothesisV1 | None:
        return self._get("hypotheses", hypothesis_id, HypothesisV1)

    def put_forecast(self, forecast: ForecastV1) -> RepositoryPutResult:
        return self._put(forecast)

    def get_forecast(self, forecast_id: str) -> ForecastV1 | None:
        return self._get("forecasts", forecast_id, ForecastV1)

    def put_opportunity(self, opportunity: OpportunityV1) -> RepositoryPutResult:
        return self._put(opportunity)

    def get_opportunity(self, opportunity_id: str) -> OpportunityV1 | None:
        return self._get("opportunities", opportunity_id, OpportunityV1)

    def put_outcome(self, outcome: OutcomeV1) -> RepositoryPutResult:
        return self._put(outcome)

    def get_outcome(self, outcome_id: str) -> OutcomeV1 | None:
        return self._get("outcomes", outcome_id, OutcomeV1)

    def put_prediction_ledger_entry(self, entry: PredictionLedgerEntryV1) -> RepositoryPutResult:
        return self._put(entry)

    def get_prediction_ledger_entry(self, ledger_entry_id: str) -> PredictionLedgerEntryV1 | None:
        return self._get("prediction_ledger", ledger_entry_id, PredictionLedgerEntryV1)

    def get_prediction_ledger_entries_by_forecast(
        self, forecast_id: str
    ) -> tuple[PredictionLedgerEntryV1, ...]:
        codec = _CODEC_BY_COLLECTION["prediction_ledger"]
        cursor = self._database["prediction_ledger"].find({"forecast_id": forecast_id})
        rows = [decode_document(document, codec) for document in cursor]
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
        query: dict[str, Any] = {
            "forecast_decision_time_ns": {"$gte": decision_start_ns, "$lt": decision_end_ns},
        }
        if mode is not None:
            query["mode"] = mode
        if scenario_id is not None:
            query["scenario_id"] = scenario_id
        if target_kind is not None:
            query["target.target_kind"] = target_kind
        if horizon_ns is not None:
            query["horizon_ns"] = horizon_ns
        codec = _CODEC_BY_COLLECTION["prediction_ledger"]
        cursor = self._database["prediction_ledger"].find(query).limit(limit * 2)
        rows = [decode_document(document, codec) for document in cursor]
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
        from ...evaluation.report import evaluation_report_v1_to_dict

        document = evaluation_report_v1_to_dict(report)
        document["_id"] = report.report_id
        collection = self._database["evaluation_reports"]
        existing = collection.find_one({"_id": report.report_id})
        if existing is None:
            collection.insert_one(document)
            return RepositoryPutResult.INSERTED
        if canonical_semantic_equal(existing, document):
            return RepositoryPutResult.ALREADY_PRESENT
        raise RepositoryConflictError(
            f"IMMUTABLE_CONFLICT:evaluation_report:{report.report_id}",
            details={"kind": "evaluation_report", "id": report.report_id},
        )

    def get_evaluation_report(self, report_id: str):
        from ...evaluation.report import evaluation_report_v1_from_dict

        document = self._database["evaluation_reports"].find_one({"_id": report_id})
        if document is None:
            return None
        payload = {k: v for k, v in document.items() if k != "_id"}
        return evaluation_report_v1_from_dict(payload)

    def _put_sidecar_document(
        self,
        collection_name: str,
        record_id: str,
        document: dict[str, Any],
        kind: str,
    ) -> RepositoryPutResult:
        document = dict(document)
        document["_id"] = record_id
        collection = self._database[collection_name]
        existing = collection.find_one({"_id": record_id})
        if existing is None:
            collection.insert_one(document)
            return RepositoryPutResult.INSERTED
        if canonical_semantic_equal(existing, document):
            return RepositoryPutResult.ALREADY_PRESENT
        raise RepositoryConflictError(
            f"IMMUTABLE_CONFLICT:{kind}:{record_id}",
            details={"kind": kind, "id": record_id},
        )

    def put_research_finding(self, finding) -> RepositoryPutResult:
        from ...research_experiments.serialization import research_finding_v1_to_dict

        return self._put_sidecar_document(
            "research_findings",
            finding.finding_id,
            research_finding_v1_to_dict(finding),
            "research_finding",
        )

    def get_research_finding(self, finding_id: str):
        from ...research_experiments.serialization import research_finding_v1_from_dict

        document = self._database["research_findings"].find_one({"_id": finding_id})
        if document is None:
            return None
        return research_finding_v1_from_dict({k: v for k, v in document.items() if k != "_id"})

    def put_research_hypothesis(self, hypothesis) -> RepositoryPutResult:
        from ...research_experiments.serialization import research_hypothesis_v1_to_dict

        return self._put_sidecar_document(
            "research_hypotheses",
            hypothesis.research_hypothesis_id,
            research_hypothesis_v1_to_dict(hypothesis),
            "research_hypothesis",
        )

    def get_research_hypothesis(self, research_hypothesis_id: str):
        from ...research_experiments.serialization import research_hypothesis_v1_from_dict

        document = self._database["research_hypotheses"].find_one({"_id": research_hypothesis_id})
        if document is None:
            return None
        return research_hypothesis_v1_from_dict({k: v for k, v in document.items() if k != "_id"})

    def put_experiment_manifest(self, manifest) -> RepositoryPutResult:
        from ...research_experiments.serialization import experiment_manifest_v1_to_dict

        return self._put_sidecar_document(
            "experiment_manifests",
            manifest.experiment_id,
            experiment_manifest_v1_to_dict(manifest),
            "experiment_manifest",
        )

    def get_experiment_manifest(self, experiment_id: str):
        from ...research_experiments.serialization import experiment_manifest_v1_from_dict

        document = self._database["experiment_manifests"].find_one({"_id": experiment_id})
        if document is None:
            return None
        return experiment_manifest_v1_from_dict({k: v for k, v in document.items() if k != "_id"})

    def query_experiment_manifests_by_hypothesis(self, research_hypothesis_id: str) -> tuple:
        from ...research_experiments.serialization import experiment_manifest_v1_from_dict

        cursor = self._database["experiment_manifests"].find(
            {"research_hypothesis_id": research_hypothesis_id}
        )
        rows = [
            experiment_manifest_v1_from_dict({k: v for k, v in doc.items() if k != "_id"})
            for doc in cursor
        ]
        return tuple(sorted(rows, key=lambda row: row.experiment_id))

    def put_research_lifecycle_event(self, event) -> RepositoryPutResult:
        from ...research_experiments.serialization import research_lifecycle_event_v1_to_dict

        return self._put_sidecar_document(
            "research_lifecycle_events",
            event.event_id,
            research_lifecycle_event_v1_to_dict(event),
            "research_lifecycle_event",
        )

    def get_research_lifecycle_events(self, entity_id: str) -> tuple:
        from ...research_experiments.serialization import research_lifecycle_event_v1_from_dict

        cursor = self._database["research_lifecycle_events"].find({"entity_id": entity_id})
        rows = [
            research_lifecycle_event_v1_from_dict({k: v for k, v in doc.items() if k != "_id"})
            for doc in cursor
        ]
        return tuple(sorted(rows, key=lambda row: (row.recorded_at_ns, row.event_id)))

    def put_training_dataset_manifest(self, manifest) -> RepositoryPutResult:
        from ...training.serialization import training_dataset_manifest_v1_to_dict

        return self._put_sidecar_document(
            "training_dataset_manifests",
            manifest.training_dataset_id,
            training_dataset_manifest_v1_to_dict(manifest),
            "training_dataset_manifest",
        )

    def get_training_dataset_manifest(self, training_dataset_id: str):
        from ...training.serialization import training_dataset_manifest_v1_from_dict

        document = self._database["training_dataset_manifests"].find_one({"_id": training_dataset_id})
        if document is None:
            return None
        return training_dataset_manifest_v1_from_dict({k: v for k, v in document.items() if k != "_id"})

    def put_training_run_manifest(self, run) -> RepositoryPutResult:
        from ...training.serialization import training_run_manifest_v1_to_dict

        return self._put_sidecar_document(
            "training_run_manifests",
            run.training_run_id,
            training_run_manifest_v1_to_dict(run),
            "training_run_manifest",
        )

    def get_training_run_manifest(self, training_run_id: str):
        from ...training.serialization import training_run_manifest_v1_from_dict

        document = self._database["training_run_manifests"].find_one({"_id": training_run_id})
        if document is None:
            return None
        return training_run_manifest_v1_from_dict({k: v for k, v in document.items() if k != "_id"})

    def put_candidate_artifact(self, candidate) -> RepositoryPutResult:
        from ...training.serialization import candidate_artifact_v1_to_dict

        return self._put_sidecar_document(
            "candidate_artifacts",
            candidate.candidate_id,
            candidate_artifact_v1_to_dict(candidate),
            "candidate_artifact",
        )

    def get_candidate_artifact(self, candidate_id: str):
        from ...training.serialization import candidate_artifact_v1_from_dict

        document = self._database["candidate_artifacts"].find_one({"_id": candidate_id})
        if document is None:
            return None
        return candidate_artifact_v1_from_dict({k: v for k, v in document.items() if k != "_id"})

    def put_distillation_dataset_manifest(self, manifest) -> RepositoryPutResult:
        from ...training.serialization import distillation_dataset_manifest_v1_to_dict

        return self._put_sidecar_document(
            "distillation_dataset_manifests",
            manifest.distillation_dataset_id,
            distillation_dataset_manifest_v1_to_dict(manifest),
            "distillation_dataset_manifest",
        )

    def get_distillation_dataset_manifest(self, distillation_dataset_id: str):
        from ...training.serialization import distillation_dataset_manifest_v1_from_dict

        document = self._database["distillation_dataset_manifests"].find_one(
            {"_id": distillation_dataset_id}
        )
        if document is None:
            return None
        return distillation_dataset_manifest_v1_from_dict(
            {k: v for k, v in document.items() if k != "_id"}
        )

    def put_run_manifest(self, manifest: RunManifestV1) -> RepositoryPutResult:
        return self._put(manifest)

    def get_run_manifest(self, run_id: str) -> RunManifestV1 | None:
        return self._get("run_manifests", run_id, RunManifestV1)

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
        active_limit = validate_limit(limit)
        query = mongo_event_candidate_filter(
            decision_time_ns,
            instrument_id=instrument_id,
            event_type=event_type,
        )
        codec = _CODEC_BY_COLLECTION["events"]
        collection = self._database["events"]
        cursor = collection.find(query).sort(mongo_event_sort()).limit(active_limit * 4)
        events = [decode_document(document, codec) for document in cursor]
        return query_events_as_of(
            events,
            decision_time_ns,
            instrument_id=instrument_id,
            event_type=event_type,
            limit=active_limit,
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
        query = mongo_event_availability_range_filter(
            start_time_ns=start_time_ns,
            end_time_ns=end_time_ns,
            instrument_id=instrument_id,
            event_type=event_type,
            provider_id=provider_id,
        )
        codec = _CODEC_BY_COLLECTION["events"]
        collection = self._database["events"]
        cursor = collection.find(query).sort(mongo_event_sort())
        if limit is not None:
            cursor = cursor.limit(validate_limit(limit))
        events = [decode_document(document, codec) for document in cursor]
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
        active_limit = validate_limit(limit)
        query: dict[str, object] = {"as_of_time_ns": {"$lte": decision_time_ns}}
        if instrument_id is not None:
            query["scope.instrument_ids"] = instrument_id
        codec = _CODEC_BY_COLLECTION["signals"]
        collection = self._database["signals"]
        cursor = collection.find(query).sort([("as_of_time_ns", 1), ("signal_id", 1)]).limit(
            active_limit * 2
        )
        signals = [decode_document(document, codec) for document in cursor]
        return query_signals_as_of(
            signals,
            decision_time_ns,
            instrument_id=instrument_id,
            limit=active_limit,
            policy=policy,
        )

    def get_evidence_by_snapshot(self, snapshot_id: str) -> tuple[EvidenceV1, ...]:
        codec = _CODEC_BY_COLLECTION["evidence"]
        cursor = self._database["evidence"].find({"snapshot_id": snapshot_id})
        rows = [decode_document(document, codec) for document in cursor]
        return filter_evidence_by_snapshot(rows, snapshot_id)

    def get_forecasts_by_instrument(
        self,
        instrument_id: str,
        *,
        decision_from_ns: int | None = None,
        decision_to_ns: int | None = None,
        limit: int = 1000,
    ) -> tuple[ForecastV1, ...]:
        active_limit = validate_limit(limit)
        query: dict[str, object] = {"scope.instrument_ids": instrument_id}
        if decision_from_ns is not None:
            query["decision_time_ns"] = {"$gte": decision_from_ns}
        if decision_to_ns is not None:
            existing = query.get("decision_time_ns")
            if isinstance(existing, dict):
                existing["$lte"] = decision_to_ns
            else:
                query["decision_time_ns"] = {"$lte": decision_to_ns}
        codec = _CODEC_BY_COLLECTION["forecasts"]
        cursor = (
            self._database["forecasts"]
            .find(query)
            .sort([("decision_time_ns", 1), ("forecast_id", 1)])
            .limit(active_limit)
        )
        rows = [decode_document(document, codec) for document in cursor]
        return filter_forecasts_by_instrument(
            rows,
            instrument_id,
            decision_from_ns=decision_from_ns,
            decision_to_ns=decision_to_ns,
            limit=active_limit,
        )

    def get_outcomes_by_forecast(self, forecast_id: str) -> tuple[OutcomeV1, ...]:
        codec = _CODEC_BY_COLLECTION["outcomes"]
        cursor = self._database["outcomes"].find({"forecast_id": forecast_id})
        rows = [decode_document(document, codec) for document in cursor]
        return filter_outcomes_by_forecast(rows, forecast_id)

    def get_opportunities_by_instrument(
        self,
        instrument_id: str,
        *,
        valid_at_ns: int | None = None,
        limit: int = 1000,
    ) -> tuple[OpportunityV1, ...]:
        active_limit = validate_limit(limit)
        query: dict[str, object] = {"scope.instrument_ids": instrument_id}
        if valid_at_ns is not None:
            query["valid_until_ns"] = {"$gte": valid_at_ns}
        codec = _CODEC_BY_COLLECTION["opportunities"]
        cursor = (
            self._database["opportunities"]
            .find(query)
            .sort([("created_at_ns", 1), ("opportunity_id", 1)])
            .limit(active_limit)
        )
        rows = [decode_document(document, codec) for document in cursor]
        return filter_opportunities_by_instrument(
            rows,
            instrument_id,
            valid_at_ns=valid_at_ns,
            limit=active_limit,
        )

    def check_health(self) -> dict[str, object]:
        try:
            self._client.admin.command("ping")
            return {
                "available": True,
                "backend": "mongo",
                "database": self._database_name,
            }
        except Exception as exc:
            raise RepositoryUnavailableError(
                "MONGO_HEALTH_CHECK_FAILED",
                details={"database": self._database_name, "reason": str(exc)},
            ) from exc

    def _put(self, record: RecordT) -> RepositoryPutResult:
        _, DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError = _import_pymongo()
        codec = codec_for_record(record)
        document = encode_document(record)
        record_id = document[codec.id_field]
        collection = self._database[codec.collection_name]
        try:
            collection.insert_one(document)
            return RepositoryPutResult.INSERTED
        except DuplicateKeyError:
            existing = collection.find_one({"_id": document["_id"]})
            if existing is None:
                raise RepositoryConflictError(
                    f"IMMUTABLE_CONFLICT:{codec.kind.value}:{record_id}",
                    details={"kind": codec.kind.value, "id": record_id},
                )
            if canonical_semantic_equal(existing, document):
                return RepositoryPutResult.ALREADY_PRESENT
            raise RepositoryConflictError(
                f"IMMUTABLE_CONFLICT:{codec.kind.value}:{record_id}",
                details={"kind": codec.kind.value, "id": record_id},
            )
        except ServerSelectionTimeoutError as exc:
            raise RepositoryUnavailableError(
                "MONGO_UNAVAILABLE",
                details={"uri": redact_mongo_uri(str(self._client.address)), "reason": str(exc)},
            ) from exc
        except PyMongoError as exc:
            raise RepositoryUnavailableError(
                "MONGO_WRITE_FAILED",
                details={"collection": codec.collection_name, "reason": str(exc)},
            ) from exc

    def _get(self, collection_name: str, record_id: str, record_type: type) -> Any | None:
        codec = _CODEC_BY_COLLECTION[collection_name]
        document = self._database[collection_name].find_one({"_id": record_id})
        if document is None:
            return None
        try:
            return decode_document(document, codec)
        except RepositoryValidationError:
            raise
        except Exception as exc:
            raise RepositoryValidationError(
                f"DOMAIN_DESERIALIZATION_FAILED:{codec.kind.value}",
                details={"id": record_id, "reason": str(exc)},
            ) from exc


__all__ = ["MongoIntelligenceRepository"]
