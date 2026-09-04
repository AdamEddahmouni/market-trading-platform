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
from ..contracts.strategy_match import StrategyMatch
from ..temporal.policy import TemporalIntegrityPolicy
from .codec import (
    CODEC_BY_TYPE,
    RECORD_CODECS,
    RecordT,
    canonical_semantic_equal,
    codec_for_kind,
    codec_for_record,
    encode_document,
)
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
    validate_limit,
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
        self._stores["validation_plans"] = {}
        self._stores["holdout_commitments"] = {}
        self._stores["holdout_unlock_receipts"] = {}
        self._stores["contamination_records"] = {}
        self._stores["validation_reports"] = {}
        self._stores["promotion_policies"] = {}
        self._stores["promotion_eligibility_assessments"] = {}
        self._stores["challenger_registrations"] = {}
        self._stores["shadow_evidence_manifests"] = {}
        self._stores["promotion_decisions"] = {}
        self._stores["champion_assignments"] = {}
        self._stores["challenger_lifecycle_events"] = {}
        self._stores["opportunity_policies"] = {}
        self._stores["opportunity_assessments"] = {}
        self._stores["economic_assessments"] = {}
        self._stores["allocation_decisions"] = {}
        self._stores["execution_policies"] = {}
        self._stores["paper_portfolio_snapshots"] = {}
        self._stores["trade_proposals"] = {}
        self._stores["risk_decisions"] = {}
        self._stores["order_ready"] = {}
        self._stores["runtime_activation_policies"] = {}
        self._stores["runtime_activations"] = {}
        self._stores["drift_policies"] = {}
        self._stores["drift_assessments"] = {}
        self._stores["governance_alerts"] = {}
        self._stores["fail_safe_policies"] = {}
        self._stores["fail_safe_decisions"] = {}
        self._stores["rollback_policies"] = {}
        self._stores["rollback_decisions"] = {}
        self._stores["governance_events"] = {}
        self._stores["adaptation_policies"] = {}
        self._stores["adaptation_assessments"] = {}
        self._stores["research_triggers"] = {}
        self._stores["adaptation_campaigns"] = {}
        self._stores["adaptation_events"] = {}

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

    def put_allocation_decision(self, decision) -> RepositoryPutResult:
        from ..opportunity.allocation_persistence import allocation_decision_v1_to_dict

        return self._put_sidecar(
            collection="allocation_decisions",
            record_id=decision.allocation_decision_id,
            document=allocation_decision_v1_to_dict(decision),
            kind="allocation_decision",
        )

    def get_allocation_decision(self, allocation_decision_id: str):
        from ..opportunity.allocation_persistence import allocation_decision_v1_from_dict

        return self._get_sidecar(
            "allocation_decisions",
            allocation_decision_id,
            allocation_decision_v1_from_dict,
        )

    def get_allocation_decisions_by_set(
        self,
        decision_set_id: str,
        *,
        account_id: str | None = None,
        mode: str | None = None,
    ) -> tuple:
        from ..opportunity.allocation_persistence import allocation_decision_v1_from_dict

        with self._lock:
            bodies = list(self._stores["allocation_decisions"].values())
        rows = []
        for body in bodies:
            payload = {key: value for key, value in body.items() if key != "_id"}
            decision = allocation_decision_v1_from_dict(payload)
            if decision.decision_set_id != decision_set_id:
                continue
            if account_id is not None and decision.account_id != account_id:
                continue
            if mode is not None and decision.mode != mode:
                continue
            rows.append(decision)
        return tuple(sorted(rows, key=lambda row: (row.rank, row.allocation_decision_id)))

    def query_allocation_decisions(
        self,
        *,
        account_id: str | None = None,
        mode: str | None = None,
        decision_from_ns: int | None = None,
        decision_to_ns: int | None = None,
        limit: int = 1000,
    ) -> tuple:
        from ..opportunity.allocation_persistence import allocation_decision_v1_from_dict

        active_limit = validate_limit(limit)
        normalized_mode = str(mode).strip().upper() if mode is not None else None
        normalized_mode = (
            {"LIVE": "ACTUAL_LIVE"}.get(normalized_mode, normalized_mode)
            if normalized_mode is not None
            else None
        )
        with self._lock:
            bodies = list(self._stores["allocation_decisions"].values())
        rows = []
        for body in bodies:
            payload = {key: value for key, value in body.items() if key != "_id"}
            decision = allocation_decision_v1_from_dict(payload)
            if account_id is not None and decision.account_id != account_id:
                continue
            if normalized_mode is not None and decision.mode != normalized_mode:
                continue
            if decision_from_ns is not None and decision.decision_time_ns < decision_from_ns:
                continue
            if decision_to_ns is not None and decision.decision_time_ns > decision_to_ns:
                continue
            rows.append(decision)
        rows.sort(key=lambda row: (-row.decision_time_ns, row.allocation_decision_id))
        return tuple(rows[:active_limit])

    def put_strategy_match(self, match: StrategyMatch) -> RepositoryPutResult:
        return self._put(match)

    def get_strategy_match(self, match_id: str) -> StrategyMatch | None:
        return self._get(StrategyMatch, "strategy_matches", match_id)

    def put_strategy_attribution(self, attribution: StrategyAttributionV1) -> RepositoryPutResult:
        return self._put(attribution)

    def get_strategy_attribution(
        self,
        attribution_id: str,
        *,
        account_id: str | None = None,
        mode: str | None = None,
        as_of_ns: int | None = None,
    ) -> StrategyAttributionV1 | None:
        from ...portfolio.attribution import StrategyAttributionV1, validate_attribution_scope

        record = self._get(StrategyAttributionV1, "strategy_attributions", attribution_id)
        if record is None:
            return None
        if account_id is not None or mode is not None or as_of_ns is not None:
            if account_id is None or mode is None or as_of_ns is None:
                raise ValueError("ATTRIBUTION_SCOPE_GUARDS_INCOMPLETE")
            validate_attribution_scope(
                record,
                account_id=account_id,
                mode=mode,
                as_of_ns=as_of_ns,
            )
        return record

    def get_strategy_attributions_by_allocation(
        self,
        allocation_decision_id: str,
        *,
        account_id: str | None = None,
        mode: str | None = None,
        as_of_ns: int | None = None,
    ) -> tuple:
        from ...portfolio.attribution import (
            StrategyAttributionV1,
            validate_attribution_scope,
        )

        with self._lock:
            bodies = list(self._stores["strategy_attributions"].values())
        rows = []
        for body in bodies:
            record = self._decode(StrategyAttributionV1, body)
            if record.allocation_ref.id != allocation_decision_id:
                continue
            if record.allocation_ref.kind not in {"allocation", "allocation_decision"}:
                continue
            if account_id is not None and record.account_id != account_id:
                continue
            if mode is not None:
                normalized_mode = str(mode).strip().upper()
                normalized_mode = {"LIVE": "ACTUAL_LIVE"}.get(
                    normalized_mode,
                    normalized_mode,
                )
                if record.mode != normalized_mode:
                    continue
            if as_of_ns is not None:
                if account_id is None or mode is None:
                    raise ValueError("ATTRIBUTION_SCOPE_GUARDS_INCOMPLETE")
                validate_attribution_scope(
                    record,
                    account_id=account_id,
                    mode=mode,
                    as_of_ns=as_of_ns,
                )
            rows.append(record)
        return tuple(
            sorted(
                rows,
                key=lambda row: (
                    len(row.fill_refs),
                    max((fill.fill_time_ns for fill in row.fills), default=-1),
                    row.attribution_id,
                ),
            )
        )

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

    def put_validation_plan(self, plan) -> RepositoryPutResult:
        from ..validation.serialization import validation_plan_v1_to_dict

        return self._put_sidecar(
            collection="validation_plans",
            record_id=plan.validation_plan_id,
            document=validation_plan_v1_to_dict(plan),
            kind="validation_plan",
        )

    def get_validation_plan(self, validation_plan_id: str):
        from ..validation.serialization import validation_plan_v1_from_dict

        return self._get_sidecar("validation_plans", validation_plan_id, validation_plan_v1_from_dict)

    def put_holdout_commitment(self, commitment) -> RepositoryPutResult:
        from ..validation.serialization import holdout_commitment_v1_to_dict

        return self._put_sidecar(
            collection="holdout_commitments",
            record_id=commitment.holdout_commitment_id,
            document=holdout_commitment_v1_to_dict(commitment),
            kind="holdout_commitment",
        )

    def get_holdout_commitment(self, holdout_commitment_id: str):
        from ..validation.serialization import holdout_commitment_v1_from_dict

        return self._get_sidecar(
            "holdout_commitments", holdout_commitment_id, holdout_commitment_v1_from_dict
        )

    def put_holdout_unlock_receipt(self, receipt) -> RepositoryPutResult:
        from ..validation.serialization import holdout_unlock_receipt_v1_to_dict

        return self._put_sidecar(
            collection="holdout_unlock_receipts",
            record_id=receipt.receipt_id,
            document=holdout_unlock_receipt_v1_to_dict(receipt),
            kind="holdout_unlock_receipt",
        )

    def get_holdout_unlock_receipt(self, receipt_id: str):
        from ..validation.serialization import holdout_unlock_receipt_v1_from_dict

        return self._get_sidecar(
            "holdout_unlock_receipts", receipt_id, holdout_unlock_receipt_v1_from_dict
        )

    def put_contamination_record(self, record) -> RepositoryPutResult:
        from ..validation.serialization import contamination_record_v1_to_dict

        return self._put_sidecar(
            collection="contamination_records",
            record_id=record.contamination_record_id,
            document=contamination_record_v1_to_dict(record),
            kind="contamination_record",
        )

    def get_contamination_record(self, contamination_record_id: str):
        from ..validation.serialization import contamination_record_v1_from_dict

        return self._get_sidecar(
            "contamination_records", contamination_record_id, contamination_record_v1_from_dict
        )

    def put_validation_report(self, report) -> RepositoryPutResult:
        from ..validation.serialization import validation_report_v1_to_dict

        return self._put_sidecar(
            collection="validation_reports",
            record_id=report.validation_report_id,
            document=validation_report_v1_to_dict(report),
            kind="validation_report",
        )

    def get_validation_report(self, validation_report_id: str):
        from ..validation.serialization import validation_report_v1_from_dict

        return self._get_sidecar(
            "validation_reports", validation_report_id, validation_report_v1_from_dict
        )

    def put_promotion_policy(self, policy) -> RepositoryPutResult:
        from ..promotion.serialization import promotion_policy_v1_to_dict

        return self._put_sidecar(
            collection="promotion_policies",
            record_id=policy.promotion_policy_id,
            document=promotion_policy_v1_to_dict(policy),
            kind="promotion_policy",
        )

    def get_promotion_policy(self, promotion_policy_id: str):
        from ..promotion.serialization import promotion_policy_v1_from_dict

        return self._get_sidecar("promotion_policies", promotion_policy_id, promotion_policy_v1_from_dict)

    def put_promotion_eligibility_assessment(self, assessment) -> RepositoryPutResult:
        from ..promotion.serialization import promotion_eligibility_assessment_v1_to_dict

        return self._put_sidecar(
            collection="promotion_eligibility_assessments",
            record_id=assessment.assessment_id,
            document=promotion_eligibility_assessment_v1_to_dict(assessment),
            kind="promotion_eligibility_assessment",
        )

    def get_promotion_eligibility_assessment(self, assessment_id: str):
        from ..promotion.serialization import promotion_eligibility_assessment_v1_from_dict

        return self._get_sidecar(
            "promotion_eligibility_assessments",
            assessment_id,
            promotion_eligibility_assessment_v1_from_dict,
        )

    def put_challenger_registration(self, registration) -> RepositoryPutResult:
        from ..promotion.serialization import challenger_registration_v1_to_dict

        return self._put_sidecar(
            collection="challenger_registrations",
            record_id=registration.challenger_registration_id,
            document=challenger_registration_v1_to_dict(registration),
            kind="challenger_registration",
        )

    def get_challenger_registration(self, challenger_registration_id: str):
        from ..promotion.serialization import challenger_registration_v1_from_dict

        return self._get_sidecar(
            "challenger_registrations",
            challenger_registration_id,
            challenger_registration_v1_from_dict,
        )

    def put_shadow_evidence_manifest(self, manifest) -> RepositoryPutResult:
        from ..promotion.serialization import shadow_evidence_manifest_v1_to_dict

        return self._put_sidecar(
            collection="shadow_evidence_manifests",
            record_id=manifest.shadow_evidence_id,
            document=shadow_evidence_manifest_v1_to_dict(manifest),
            kind="shadow_evidence_manifest",
        )

    def get_shadow_evidence_manifest(self, shadow_evidence_id: str):
        from ..promotion.serialization import shadow_evidence_manifest_v1_from_dict

        return self._get_sidecar(
            "shadow_evidence_manifests",
            shadow_evidence_id,
            shadow_evidence_manifest_v1_from_dict,
        )

    def put_promotion_decision(self, decision) -> RepositoryPutResult:
        from ..promotion.serialization import promotion_decision_v1_to_dict

        return self._put_sidecar(
            collection="promotion_decisions",
            record_id=decision.promotion_decision_id,
            document=promotion_decision_v1_to_dict(decision),
            kind="promotion_decision",
        )

    def get_promotion_decision(self, promotion_decision_id: str):
        from ..promotion.serialization import promotion_decision_v1_from_dict

        return self._get_sidecar(
            "promotion_decisions", promotion_decision_id, promotion_decision_v1_from_dict
        )

    def put_champion_assignment(self, assignment) -> RepositoryPutResult:
        from ..promotion.serialization import champion_assignment_v1_to_dict

        return self._put_sidecar(
            collection="champion_assignments",
            record_id=assignment.assignment_id,
            document=champion_assignment_v1_to_dict(assignment),
            kind="champion_assignment",
        )

    def get_champion_assignment(self, assignment_id: str):
        from ..promotion.serialization import champion_assignment_v1_from_dict

        return self._get_sidecar(
            "champion_assignments", assignment_id, champion_assignment_v1_from_dict
        )

    def get_champion_assignments_for_scope(
        self,
        *,
        component: str,
        target_kind: str,
        horizon_ns: int,
        mode: str,
        scenario_id: str | None = None,
    ) -> tuple:
        from ..promotion.serialization import champion_assignment_v1_from_dict
        from .champion_queries import scope_matches

        with self._lock:
            bodies = list(self._stores["champion_assignments"].values())
        assignments = tuple(
            champion_assignment_v1_from_dict({k: v for k, v in body.items() if k != "_id"})
            for body in bodies
        )
        return tuple(
            assignment
            for assignment in assignments
            if scope_matches(
                assignment,
                component=component,
                target_kind=target_kind,
                horizon_ns=horizon_ns,
                mode=mode,
                scenario_id=scenario_id,
            )
        )

    def get_current_champion_assignment(
        self,
        *,
        component: str,
        target_kind: str,
        horizon_ns: int,
        mode: str,
        as_of_ns: int,
        scenario_id: str | None = None,
    ):
        from .champion_queries import get_current_champion_assignment

        assignments = self.get_champion_assignments_for_scope(
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            scenario_id=scenario_id,
        )
        return get_current_champion_assignment(
            assignments,
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            as_of_ns=as_of_ns,
            scenario_id=scenario_id,
        )

    def put_challenger_lifecycle_event(self, event) -> RepositoryPutResult:
        from ..promotion.serialization import challenger_lifecycle_event_v1_to_dict

        return self._put_sidecar(
            collection="challenger_lifecycle_events",
            record_id=event.event_id,
            document=challenger_lifecycle_event_v1_to_dict(event),
            kind="challenger_lifecycle_event",
        )

    def get_challenger_lifecycle_events(self, challenger_registration_id: str) -> tuple:
        from ..promotion.serialization import challenger_lifecycle_event_v1_from_dict

        with self._lock:
            bodies = list(self._stores["challenger_lifecycle_events"].values())
        events = [
            challenger_lifecycle_event_v1_from_dict({k: v for k, v in body.items() if k != "_id"})
            for body in bodies
            if body.get("challenger_registration_id") == challenger_registration_id
        ]
        events.sort(key=lambda item: item.effective_at_ns)
        return tuple(events)

    def put_opportunity_policy(self, policy) -> RepositoryPutResult:
        from ..opportunity.serialization import opportunity_policy_v1_to_dict

        return self._put_sidecar(
            collection="opportunity_policies",
            record_id=policy.opportunity_policy_id,
            document=opportunity_policy_v1_to_dict(policy),
            kind="opportunity_policy",
        )

    def get_opportunity_policy(self, opportunity_policy_id: str):
        from ..opportunity.serialization import opportunity_policy_v1_from_dict

        return self._get_sidecar("opportunity_policies", opportunity_policy_id, opportunity_policy_v1_from_dict)

    def put_opportunity_assessment(self, assessment) -> RepositoryPutResult:
        from ..opportunity.serialization import opportunity_assessment_v1_to_dict

        return self._put_sidecar(
            collection="opportunity_assessments",
            record_id=assessment.assessment_id,
            document=opportunity_assessment_v1_to_dict(assessment),
            kind="opportunity_assessment",
        )

    def get_opportunity_assessment(self, assessment_id: str):
        from ..opportunity.serialization import opportunity_assessment_v1_from_dict

        return self._get_sidecar(
            "opportunity_assessments", assessment_id, opportunity_assessment_v1_from_dict
        )

    def get_opportunity_assessments_by_forecast(self, forecast_id: str) -> tuple:
        from ..opportunity.serialization import opportunity_assessment_v1_from_dict

        with self._lock:
            bodies = list(self._stores["opportunity_assessments"].values())
        rows = [
            opportunity_assessment_v1_from_dict({k: v for k, v in body.items() if k != "_id"})
            for body in bodies
            if body.get("forecast_id") == forecast_id
        ]
        rows.sort(key=lambda item: (item.opportunity_decision_time_ns, item.assessment_id))
        return tuple(rows)

    def put_economic_assessment(self, assessment) -> RepositoryPutResult:
        from ..opportunity.economic_assessment import economic_assessment_v1_to_dict

        return self._put_sidecar(
            collection="economic_assessments",
            record_id=assessment.assessment_id,
            document=economic_assessment_v1_to_dict(assessment),
            kind="economic_assessment",
        )

    def get_economic_assessment(self, assessment_id: str):
        from ..opportunity.economic_assessment import economic_assessment_v1_from_dict

        return self._get_sidecar(
            "economic_assessments",
            assessment_id,
            economic_assessment_v1_from_dict,
        )

    put_universal_economic_assessment = put_economic_assessment
    get_universal_economic_assessment = get_economic_assessment

    def put_execution_policy(self, policy) -> RepositoryPutResult:
        from ..execution.serialization import execution_policy_v1_to_dict

        return self._put_sidecar(
            collection="execution_policies",
            record_id=policy.execution_policy_id,
            document=execution_policy_v1_to_dict(policy),
            kind="execution_policy",
        )

    def get_execution_policy(self, execution_policy_id: str):
        from ..execution.serialization import execution_policy_v1_from_dict

        return self._get_sidecar("execution_policies", execution_policy_id, execution_policy_v1_from_dict)

    def put_paper_portfolio_snapshot(self, snapshot) -> RepositoryPutResult:
        from ..execution.serialization import paper_portfolio_snapshot_v1_to_dict

        return self._put_sidecar(
            collection="paper_portfolio_snapshots",
            record_id=snapshot.snapshot_id,
            document=paper_portfolio_snapshot_v1_to_dict(snapshot),
            kind="paper_portfolio_snapshot",
        )

    def get_paper_portfolio_snapshot(self, snapshot_id: str):
        from ..execution.serialization import paper_portfolio_snapshot_v1_from_dict

        return self._get_sidecar(
            "paper_portfolio_snapshots", snapshot_id, paper_portfolio_snapshot_v1_from_dict
        )

    def put_trade_proposal(self, proposal) -> RepositoryPutResult:
        from ..contracts.trade_proposal import trade_proposal_v1_to_dict

        return self._put_sidecar(
            collection="trade_proposals",
            record_id=proposal.proposal_id,
            document=trade_proposal_v1_to_dict(proposal),
            kind="trade_proposal",
        )

    def get_trade_proposal(self, proposal_id: str):
        from ..contracts.trade_proposal import trade_proposal_v1_from_dict

        return self._get_sidecar("trade_proposals", proposal_id, trade_proposal_v1_from_dict)

    def put_risk_decision(self, decision) -> RepositoryPutResult:
        from ..execution.serialization import risk_decision_v1_to_dict

        return self._put_sidecar(
            collection="risk_decisions",
            record_id=decision.risk_decision_id,
            document=risk_decision_v1_to_dict(decision),
            kind="risk_decision",
        )

    def get_risk_decision(self, risk_decision_id: str):
        from ..execution.serialization import risk_decision_v1_from_dict

        return self._get_sidecar("risk_decisions", risk_decision_id, risk_decision_v1_from_dict)

    def put_order_ready(self, order_ready) -> RepositoryPutResult:
        from ..execution.serialization import order_ready_v1_to_dict

        return self._put_sidecar(
            collection="order_ready",
            record_id=order_ready.order_ready_id,
            document=order_ready_v1_to_dict(order_ready),
            kind="order_ready",
        )

    def get_order_ready(self, order_ready_id: str):
        from ..execution.serialization import order_ready_v1_from_dict

        return self._get_sidecar("order_ready", order_ready_id, order_ready_v1_from_dict)

    def get_order_ready_by_allocation(self, allocation_decision_id: str) -> tuple:
        from ..execution.serialization import order_ready_v1_from_dict

        with self._lock:
            bodies = list(self._stores["order_ready"].values())
        records = [
            order_ready_v1_from_dict({key: value for key, value in body.items() if key != "_id"})
            for body in bodies
        ]
        return tuple(
            sorted(
                (
                    record
                    for record in records
                    if record.allocation_decision_id == allocation_decision_id
                ),
                key=lambda record: (record.decision_time_ns, record.order_ready_id),
            )
        )

    def put_runtime_activation_policy(self, policy) -> RepositoryPutResult:
        from ..governance.serialization import runtime_activation_policy_v1_to_dict

        return self._put_sidecar(
            collection="runtime_activation_policies",
            record_id=policy.activation_policy_id,
            document=runtime_activation_policy_v1_to_dict(policy),
            kind="runtime_activation_policy",
        )

    def get_runtime_activation_policy(self, activation_policy_id: str):
        from ..governance.serialization import runtime_activation_policy_v1_from_dict

        return self._get_sidecar(
            "runtime_activation_policies", activation_policy_id, runtime_activation_policy_v1_from_dict
        )

    def put_runtime_activation(self, activation) -> RepositoryPutResult:
        from ..governance.serialization import runtime_activation_v1_to_dict

        return self._put_sidecar(
            collection="runtime_activations",
            record_id=activation.activation_id,
            document=runtime_activation_v1_to_dict(activation),
            kind="runtime_activation",
        )

    def get_runtime_activation(self, activation_id: str):
        from ..governance.serialization import runtime_activation_v1_from_dict

        return self._get_sidecar("runtime_activations", activation_id, runtime_activation_v1_from_dict)

    def get_runtime_activations_for_scope(
        self,
        *,
        component: str,
        target_kind: str,
        horizon_ns: int,
        mode: str,
        scenario_id: str | None = None,
    ) -> tuple:
        from ..governance.serialization import runtime_activation_v1_from_dict

        with self._lock:
            bodies = list(self._stores["runtime_activations"].values())
        activations = []
        for body in bodies:
            payload = {k: v for k, v in body.items() if k != "_id"}
            activation = runtime_activation_v1_from_dict(payload)
            scope = activation.champion_scope
            if scope.component != component:
                continue
            if scope.target_kind != target_kind:
                continue
            if scope.horizon_ns != horizon_ns:
                continue
            if scope.mode != mode:
                continue
            if scenario_id is not None and scope.scenario_id != scenario_id:
                continue
            activations.append(activation)
        return tuple(activations)

    def get_current_runtime_activation(
        self,
        *,
        component: str,
        target_kind: str,
        horizon_ns: int,
        mode: str,
        as_of_ns: int,
        scenario_id: str | None = None,
    ):
        from ..governance.activation_queries import get_current_runtime_activation

        activations = self.get_runtime_activations_for_scope(
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            scenario_id=scenario_id,
        )
        return get_current_runtime_activation(
            activations,
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            as_of_ns=as_of_ns,
            scenario_id=scenario_id,
        )

    def put_drift_policy(self, policy) -> RepositoryPutResult:
        from ..governance.serialization import drift_policy_v1_to_dict

        return self._put_sidecar(
            collection="drift_policies",
            record_id=policy.drift_policy_id,
            document=drift_policy_v1_to_dict(policy),
            kind="drift_policy",
        )

    def get_drift_policy(self, drift_policy_id: str):
        from ..governance.serialization import drift_policy_v1_from_dict

        return self._get_sidecar("drift_policies", drift_policy_id, drift_policy_v1_from_dict)

    def put_drift_assessment(self, assessment) -> RepositoryPutResult:
        from ..governance.serialization import drift_assessment_v1_to_dict

        return self._put_sidecar(
            collection="drift_assessments",
            record_id=assessment.drift_assessment_id,
            document=drift_assessment_v1_to_dict(assessment),
            kind="drift_assessment",
        )

    def get_drift_assessment(self, drift_assessment_id: str):
        from ..governance.serialization import drift_assessment_v1_from_dict

        return self._get_sidecar("drift_assessments", drift_assessment_id, drift_assessment_v1_from_dict)

    def put_governance_alert(self, alert) -> RepositoryPutResult:
        from ..governance.serialization import governance_alert_v1_to_dict

        return self._put_sidecar(
            collection="governance_alerts",
            record_id=alert.alert_id,
            document=governance_alert_v1_to_dict(alert),
            kind="governance_alert",
        )

    def get_governance_alert(self, alert_id: str):
        from ..governance.serialization import governance_alert_v1_from_dict

        return self._get_sidecar("governance_alerts", alert_id, governance_alert_v1_from_dict)

    def put_fail_safe_policy(self, policy) -> RepositoryPutResult:
        from ..governance.serialization import fail_safe_policy_v1_to_dict

        return self._put_sidecar(
            collection="fail_safe_policies",
            record_id=policy.fail_safe_policy_id,
            document=fail_safe_policy_v1_to_dict(policy),
            kind="fail_safe_policy",
        )

    def get_fail_safe_policy(self, fail_safe_policy_id: str):
        from ..governance.serialization import fail_safe_policy_v1_from_dict

        return self._get_sidecar("fail_safe_policies", fail_safe_policy_id, fail_safe_policy_v1_from_dict)

    def put_fail_safe_decision(self, decision) -> RepositoryPutResult:
        from ..governance.serialization import fail_safe_decision_v1_to_dict

        return self._put_sidecar(
            collection="fail_safe_decisions",
            record_id=decision.decision_id,
            document=fail_safe_decision_v1_to_dict(decision),
            kind="fail_safe_decision",
        )

    def get_fail_safe_decision(self, decision_id: str):
        from ..governance.serialization import fail_safe_decision_v1_from_dict

        return self._get_sidecar("fail_safe_decisions", decision_id, fail_safe_decision_v1_from_dict)

    def put_rollback_policy(self, policy) -> RepositoryPutResult:
        from ..governance.serialization import rollback_policy_v1_to_dict

        return self._put_sidecar(
            collection="rollback_policies",
            record_id=policy.rollback_policy_id,
            document=rollback_policy_v1_to_dict(policy),
            kind="rollback_policy",
        )

    def get_rollback_policy(self, rollback_policy_id: str):
        from ..governance.serialization import rollback_policy_v1_from_dict

        return self._get_sidecar("rollback_policies", rollback_policy_id, rollback_policy_v1_from_dict)

    def put_rollback_decision(self, decision) -> RepositoryPutResult:
        from ..governance.serialization import rollback_decision_v1_to_dict

        return self._put_sidecar(
            collection="rollback_decisions",
            record_id=decision.rollback_decision_id,
            document=rollback_decision_v1_to_dict(decision),
            kind="rollback_decision",
        )

    def get_rollback_decision(self, rollback_decision_id: str):
        from ..governance.serialization import rollback_decision_v1_from_dict

        return self._get_sidecar("rollback_decisions", rollback_decision_id, rollback_decision_v1_from_dict)

    def put_governance_event(self, event) -> RepositoryPutResult:
        from ..governance.serialization import governance_event_v1_to_dict

        return self._put_sidecar(
            collection="governance_events",
            record_id=event.event_id,
            document=governance_event_v1_to_dict(event),
            kind="governance_event",
        )

    def get_governance_event(self, event_id: str):
        from ..governance.serialization import governance_event_v1_from_dict

        return self._get_sidecar("governance_events", event_id, governance_event_v1_from_dict)

    def put_adaptation_policy(self, policy) -> RepositoryPutResult:
        from ..adaptation.serialization import adaptation_policy_v1_to_dict

        return self._put_sidecar(
            collection="adaptation_policies",
            record_id=policy.adaptation_policy_id,
            document=adaptation_policy_v1_to_dict(policy),
            kind="adaptation_policy",
        )

    def get_adaptation_policy(self, adaptation_policy_id: str):
        from ..adaptation.serialization import adaptation_policy_v1_from_dict

        return self._get_sidecar("adaptation_policies", adaptation_policy_id, adaptation_policy_v1_from_dict)

    def put_adaptation_assessment(self, assessment) -> RepositoryPutResult:
        from ..adaptation.serialization import adaptation_assessment_v1_to_dict

        return self._put_sidecar(
            collection="adaptation_assessments",
            record_id=assessment.adaptation_assessment_id,
            document=adaptation_assessment_v1_to_dict(assessment),
            kind="adaptation_assessment",
        )

    def get_adaptation_assessment(self, adaptation_assessment_id: str):
        from ..adaptation.serialization import adaptation_assessment_v1_from_dict

        return self._get_sidecar(
            "adaptation_assessments",
            adaptation_assessment_id,
            adaptation_assessment_v1_from_dict,
        )

    def put_research_trigger(self, trigger) -> RepositoryPutResult:
        from ..adaptation.serialization import research_trigger_v1_to_dict

        return self._put_sidecar(
            collection="research_triggers",
            record_id=trigger.research_trigger_id,
            document=research_trigger_v1_to_dict(trigger),
            kind="research_trigger",
        )

    def get_research_trigger(self, research_trigger_id: str):
        from ..adaptation.serialization import research_trigger_v1_from_dict

        return self._get_sidecar("research_triggers", research_trigger_id, research_trigger_v1_from_dict)

    def query_research_triggers_by_dedup_key(self, dedup_key: str) -> tuple:
        from ..adaptation.serialization import research_trigger_v1_from_dict

        with self._lock:
            rows = [
                research_trigger_v1_from_dict({k: v for k, v in body.items() if k != "_id"})
                for body in self._stores["research_triggers"].values()
                if body.get("dedup_key") == dedup_key
            ]
        return tuple(sorted(rows, key=lambda row: row.research_trigger_id))

    def put_adaptation_campaign(self, campaign) -> RepositoryPutResult:
        from ..adaptation.serialization import adaptation_campaign_v1_to_dict

        return self._put_sidecar(
            collection="adaptation_campaigns",
            record_id=campaign.adaptation_campaign_id,
            document=adaptation_campaign_v1_to_dict(campaign),
            kind="adaptation_campaign",
        )

    def get_adaptation_campaign(self, adaptation_campaign_id: str):
        from ..adaptation.serialization import adaptation_campaign_v1_from_dict

        return self._get_sidecar(
            "adaptation_campaigns",
            adaptation_campaign_id,
            adaptation_campaign_v1_from_dict,
        )

    def put_adaptation_event(self, event) -> RepositoryPutResult:
        from ..adaptation.serialization import adaptation_event_v1_to_dict

        return self._put_sidecar(
            collection="adaptation_events",
            record_id=event.event_id,
            document=adaptation_event_v1_to_dict(event),
            kind="adaptation_event",
        )

    def get_adaptation_event(self, event_id: str):
        from ..adaptation.serialization import adaptation_event_v1_from_dict

        return self._get_sidecar("adaptation_events", event_id, adaptation_event_v1_from_dict)

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
        codec = _CODEC_BY_TYPE.get(record_type)
        if codec is None:
            from ...portfolio.attribution import StrategyAttributionV1
            from ..contracts.common import ContractKind

            if record_type is not StrategyAttributionV1:
                raise KeyError(record_type)
            codec = codec_for_kind(ContractKind.STRATEGY_ATTRIBUTION)
        return codec.from_dict(copy.deepcopy({k: v for k, v in body.items() if k != "_id"}))


__all__ = ["InMemoryIntelligenceRepository"]
