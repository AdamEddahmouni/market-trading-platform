"""Replay visibility boundary — separates source history from decision-visible state (BUILD 07)."""

from __future__ import annotations

from dataclasses import dataclass

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
from ..persistence.queries import query_events_as_of, query_signals_as_of
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from ..temporal.policy import TemporalIntegrityPolicy
from .models import DeliveryAction, ReplayDeliveryEnvelope


@dataclass(frozen=True, slots=True)
class ReplayVisibilityIndex:
    """Immutable delivery overlay preserving counterfactual visibility history."""

    envelopes: tuple[ReplayDeliveryEnvelope, ...]

    def __post_init__(self) -> None:
        by_id = {envelope.event_id: envelope for envelope in self.envelopes}
        if len(by_id) != len(self.envelopes):
            raise ValueError("REPLAY_VISIBILITY_DUPLICATE_EVENT")

    @classmethod
    def from_envelopes(cls, envelopes: tuple[ReplayDeliveryEnvelope, ...]) -> ReplayVisibilityIndex:
        ordered = tuple(sorted(envelopes, key=lambda row: (row.event_id,)))
        return cls(envelopes=ordered)

    def envelope_for(self, event_id: str) -> ReplayDeliveryEnvelope | None:
        for envelope in self.envelopes:
            if envelope.event_id == event_id:
                return envelope
        return None

    def visible_event_ids_at(self, decision_time_ns: int) -> frozenset[str]:
        visible: set[str] = set()
        for envelope in self.envelopes:
            if envelope.delivery_action in {
                DeliveryAction.DROP,
                DeliveryAction.DISCONNECT_DROP,
                DeliveryAction.ENTITLEMENT_BLOCK,
            }:
                continue
            if envelope.effective_delivery_time_ns <= decision_time_ns:
                visible.add(envelope.event_id)
        return frozenset(visible)


class ReplayVisibleRepository:
    """Decision-visible repository view — never exposes undelivered future source events."""

    def __init__(
        self,
        *,
        source_repository: IntelligenceRepository,
        output_repository: IntelligenceRepository,
        visibility_index: ReplayVisibilityIndex,
        decision_time_ns: int,
    ) -> None:
        self._source = source_repository
        self._output = output_repository
        self._visibility = visibility_index
        self._decision_time_ns = decision_time_ns

    def with_decision_time(self, decision_time_ns: int) -> ReplayVisibleRepository:
        return ReplayVisibleRepository(
            source_repository=self._source,
            output_repository=self._output,
            visibility_index=self._visibility,
            decision_time_ns=decision_time_ns,
        )

    @property
    def decision_time_ns(self) -> int:
        return self._decision_time_ns

    @property
    def visibility_index(self) -> ReplayVisibilityIndex:
        return self._visibility

    def put_event(self, event: EventV1) -> RepositoryPutResult:
        return self._output.put_event(event)

    def get_event(self, event_id: str) -> EventV1 | None:
        return self._source.get_event(event_id)

    def get_events(self, event_ids: tuple[str, ...] | list[str]) -> tuple[EventV1, ...]:
        return self._source.get_events(event_ids)

    def put_detection(self, detection: DetectionV1) -> RepositoryPutResult:
        return self._output.put_detection(detection)

    def get_detection(self, detection_id: str) -> DetectionV1 | None:
        return self._output.get_detection(detection_id)

    def get_detections_by_snapshot(self, snapshot_id: str) -> tuple[DetectionV1, ...]:
        return self._output.get_detections_by_snapshot(snapshot_id)

    def put_routing_decision(self, decision: RoutingDecisionV1) -> RepositoryPutResult:
        return self._output.put_routing_decision(decision)

    def get_routing_decision(self, routing_decision_id: str) -> RoutingDecisionV1 | None:
        return self._output.get_routing_decision(routing_decision_id)

    def get_routes_by_detection(self, detection_id: str) -> tuple[RoutingDecisionV1, ...]:
        return self._output.get_routes_by_detection(detection_id)

    def put_inference_job(self, job: InferenceJobV1) -> RepositoryPutResult:
        return self._output.put_inference_job(job)

    def get_inference_job(self, job_id: str) -> InferenceJobV1 | None:
        return self._output.get_inference_job(job_id)

    def put_snapshot(self, snapshot: SnapshotV1) -> RepositoryPutResult:
        return self._output.put_snapshot(snapshot)

    def get_snapshot(self, snapshot_id: str) -> SnapshotV1 | None:
        return self._output.get_snapshot(snapshot_id) or self._source.get_snapshot(snapshot_id)

    def put_signal(self, signal: SignalV1) -> RepositoryPutResult:
        return self._output.put_signal(signal)

    def get_signal(self, signal_id: str) -> SignalV1 | None:
        return self._output.get_signal(signal_id) or self._source.get_signal(signal_id)

    def get_signals(self, signal_ids: tuple[str, ...] | list[str]) -> tuple[SignalV1, ...]:
        rows: list[SignalV1] = []
        for signal_id in sorted({str(value) for value in signal_ids}):
            signal = self.get_signal(signal_id)
            if signal is not None:
                rows.append(signal)
        return tuple(rows)

    def put_evidence(self, evidence: EvidenceV1) -> RepositoryPutResult:
        return self._output.put_evidence(evidence)

    def get_evidence(self, evidence_id: str) -> EvidenceV1 | None:
        return self._output.get_evidence(evidence_id) or self._source.get_evidence(evidence_id)

    def put_hypothesis(self, hypothesis: HypothesisV1) -> RepositoryPutResult:
        return self._output.put_hypothesis(hypothesis)

    def get_hypothesis(self, hypothesis_id: str) -> HypothesisV1 | None:
        return self._output.get_hypothesis(hypothesis_id) or self._source.get_hypothesis(hypothesis_id)

    def put_forecast(self, forecast: ForecastV1) -> RepositoryPutResult:
        return self._output.put_forecast(forecast)

    def get_forecast(self, forecast_id: str) -> ForecastV1 | None:
        return self._output.get_forecast(forecast_id) or self._source.get_forecast(forecast_id)

    def put_opportunity(self, opportunity: OpportunityV1) -> RepositoryPutResult:
        return self._output.put_opportunity(opportunity)

    def get_opportunity(self, opportunity_id: str) -> OpportunityV1 | None:
        return self._output.get_opportunity(opportunity_id) or self._source.get_opportunity(opportunity_id)

    def put_outcome(self, outcome: OutcomeV1) -> RepositoryPutResult:
        return self._output.put_outcome(outcome)

    def get_outcome(self, outcome_id: str) -> OutcomeV1 | None:
        return self._output.get_outcome(outcome_id) or self._source.get_outcome(outcome_id)

    def put_prediction_ledger_entry(self, entry: PredictionLedgerEntryV1) -> RepositoryPutResult:
        return self._output.put_prediction_ledger_entry(entry)

    def get_prediction_ledger_entry(self, ledger_entry_id: str) -> PredictionLedgerEntryV1 | None:
        return self._output.get_prediction_ledger_entry(
            ledger_entry_id
        ) or self._source.get_prediction_ledger_entry(ledger_entry_id)

    def get_prediction_ledger_entries_by_forecast(
        self, forecast_id: str
    ) -> tuple[PredictionLedgerEntryV1, ...]:
        output_rows = self._output.get_prediction_ledger_entries_by_forecast(forecast_id)
        if output_rows:
            return output_rows
        return self._source.get_prediction_ledger_entries_by_forecast(forecast_id)

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
        output_rows = self._output.query_prediction_ledger_entries(
            decision_start_ns=decision_start_ns,
            decision_end_ns=decision_end_ns,
            mode=mode,
            scenario_id=scenario_id,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            limit=limit,
        )
        if output_rows:
            return output_rows
        return self._source.query_prediction_ledger_entries(
            decision_start_ns=decision_start_ns,
            decision_end_ns=decision_end_ns,
            mode=mode,
            scenario_id=scenario_id,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            limit=limit,
        )

    def put_run_manifest(self, manifest: RunManifestV1) -> RepositoryPutResult:
        return self._output.put_run_manifest(manifest)

    def get_run_manifest(self, run_id: str) -> RunManifestV1 | None:
        return self._output.get_run_manifest(run_id) or self._source.get_run_manifest(run_id)

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
        visible_ids = self._visibility.visible_event_ids_at(decision_time_ns)
        if not visible_ids:
            return ()
        events = self._source.get_events(tuple(sorted(visible_ids)))
        return query_events_as_of(
            events,
            decision_time_ns,
            instrument_id=instrument_id,
            event_type=event_type,
            limit=limit,
            require_usable=require_usable,
            policy=policy,
        )

    def query_signals_as_of(
        self,
        decision_time_ns: int,
        *,
        instrument_id: str | None = None,
        limit: int = 1000,
        policy: TemporalIntegrityPolicy | None = None,
    ) -> tuple[SignalV1, ...]:
        with_output = list(self._output.query_signals_as_of(
            decision_time_ns,
            instrument_id=instrument_id,
            limit=limit,
            policy=policy,
        ))
        with_source = list(self._source.query_signals_as_of(
            decision_time_ns,
            instrument_id=instrument_id,
            limit=limit,
            policy=policy,
        ))
        merged = {signal.signal_id: signal for signal in (*with_source, *with_output)}
        return query_signals_as_of(
            list(merged.values()),
            decision_time_ns,
            instrument_id=instrument_id,
            limit=limit,
            policy=policy,
        )

    def get_evidence_by_snapshot(self, snapshot_id: str) -> tuple[EvidenceV1, ...]:
        output_rows = self._output.get_evidence_by_snapshot(snapshot_id)
        if output_rows:
            return output_rows
        return self._source.get_evidence_by_snapshot(snapshot_id)

    def get_forecasts_by_instrument(
        self,
        instrument_id: str,
        *,
        decision_from_ns: int | None = None,
        decision_to_ns: int | None = None,
        limit: int = 1000,
    ) -> tuple[ForecastV1, ...]:
        return self._output.get_forecasts_by_instrument(
            instrument_id,
            decision_from_ns=decision_from_ns,
            decision_to_ns=decision_to_ns,
            limit=limit,
        )

    def get_outcomes_by_forecast(self, forecast_id: str) -> tuple[OutcomeV1, ...]:
        return self._output.get_outcomes_by_forecast(forecast_id)

    def get_opportunities_by_instrument(
        self,
        instrument_id: str,
        *,
        valid_at_ns: int | None = None,
        limit: int = 1000,
    ) -> tuple[OpportunityV1, ...]:
        return self._output.get_opportunities_by_instrument(
            instrument_id,
            valid_at_ns=valid_at_ns,
            limit=limit,
        )

    def put_research_finding(self, finding) -> RepositoryPutResult:
        return self._output.put_research_finding(finding)

    def get_research_finding(self, finding_id: str):
        return self._output.get_research_finding(finding_id) or self._source.get_research_finding(
            finding_id
        )

    def put_research_hypothesis(self, hypothesis) -> RepositoryPutResult:
        return self._output.put_research_hypothesis(hypothesis)

    def get_research_hypothesis(self, research_hypothesis_id: str):
        return self._output.get_research_hypothesis(
            research_hypothesis_id
        ) or self._source.get_research_hypothesis(research_hypothesis_id)

    def put_experiment_manifest(self, manifest) -> RepositoryPutResult:
        return self._output.put_experiment_manifest(manifest)

    def get_experiment_manifest(self, experiment_id: str):
        return self._output.get_experiment_manifest(experiment_id) or self._source.get_experiment_manifest(
            experiment_id
        )

    def query_experiment_manifests_by_hypothesis(self, research_hypothesis_id: str) -> tuple:
        output_rows = self._output.query_experiment_manifests_by_hypothesis(research_hypothesis_id)
        if output_rows:
            return output_rows
        return self._source.query_experiment_manifests_by_hypothesis(research_hypothesis_id)

    def put_research_lifecycle_event(self, event) -> RepositoryPutResult:
        return self._output.put_research_lifecycle_event(event)

    def get_research_lifecycle_events(self, entity_id: str) -> tuple:
        output_rows = self._output.get_research_lifecycle_events(entity_id)
        if output_rows:
            return output_rows
        return self._source.get_research_lifecycle_events(entity_id)

    def put_training_dataset_manifest(self, manifest) -> RepositoryPutResult:
        return self._output.put_training_dataset_manifest(manifest)

    def get_training_dataset_manifest(self, training_dataset_id: str):
        return self._output.get_training_dataset_manifest(
            training_dataset_id
        ) or self._source.get_training_dataset_manifest(training_dataset_id)

    def put_training_run_manifest(self, run) -> RepositoryPutResult:
        return self._output.put_training_run_manifest(run)

    def get_training_run_manifest(self, training_run_id: str):
        return self._output.get_training_run_manifest(
            training_run_id
        ) or self._source.get_training_run_manifest(training_run_id)

    def put_candidate_artifact(self, candidate) -> RepositoryPutResult:
        return self._output.put_candidate_artifact(candidate)

    def get_candidate_artifact(self, candidate_id: str):
        return self._output.get_candidate_artifact(
            candidate_id
        ) or self._source.get_candidate_artifact(candidate_id)

    def put_distillation_dataset_manifest(self, manifest) -> RepositoryPutResult:
        return self._output.put_distillation_dataset_manifest(manifest)

    def get_distillation_dataset_manifest(self, distillation_dataset_id: str):
        return self._output.get_distillation_dataset_manifest(
            distillation_dataset_id
        ) or self._source.get_distillation_dataset_manifest(distillation_dataset_id)

    def put_validation_plan(self, plan) -> RepositoryPutResult:
        return self._output.put_validation_plan(plan)

    def get_validation_plan(self, validation_plan_id: str):
        return self._output.get_validation_plan(
            validation_plan_id
        ) or self._source.get_validation_plan(validation_plan_id)

    def put_holdout_commitment(self, commitment) -> RepositoryPutResult:
        return self._output.put_holdout_commitment(commitment)

    def get_holdout_commitment(self, holdout_commitment_id: str):
        return self._output.get_holdout_commitment(
            holdout_commitment_id
        ) or self._source.get_holdout_commitment(holdout_commitment_id)

    def put_holdout_unlock_receipt(self, receipt) -> RepositoryPutResult:
        return self._output.put_holdout_unlock_receipt(receipt)

    def get_holdout_unlock_receipt(self, receipt_id: str):
        return self._output.get_holdout_unlock_receipt(
            receipt_id
        ) or self._source.get_holdout_unlock_receipt(receipt_id)

    def put_contamination_record(self, record) -> RepositoryPutResult:
        return self._output.put_contamination_record(record)

    def get_contamination_record(self, contamination_record_id: str):
        return self._output.get_contamination_record(
            contamination_record_id
        ) or self._source.get_contamination_record(contamination_record_id)

    def put_validation_report(self, report) -> RepositoryPutResult:
        return self._output.put_validation_report(report)

    def get_validation_report(self, validation_report_id: str):
        return self._output.get_validation_report(
            validation_report_id
        ) or self._source.get_validation_report(validation_report_id)

    def put_promotion_policy(self, policy) -> RepositoryPutResult:
        return self._output.put_promotion_policy(policy)

    def get_promotion_policy(self, promotion_policy_id: str):
        return self._output.get_promotion_policy(
            promotion_policy_id
        ) or self._source.get_promotion_policy(promotion_policy_id)

    def put_promotion_eligibility_assessment(self, assessment) -> RepositoryPutResult:
        return self._output.put_promotion_eligibility_assessment(assessment)

    def get_promotion_eligibility_assessment(self, assessment_id: str):
        return self._output.get_promotion_eligibility_assessment(
            assessment_id
        ) or self._source.get_promotion_eligibility_assessment(assessment_id)

    def put_challenger_registration(self, registration) -> RepositoryPutResult:
        return self._output.put_challenger_registration(registration)

    def get_challenger_registration(self, challenger_registration_id: str):
        return self._output.get_challenger_registration(
            challenger_registration_id
        ) or self._source.get_challenger_registration(challenger_registration_id)

    def put_shadow_evidence_manifest(self, manifest) -> RepositoryPutResult:
        return self._output.put_shadow_evidence_manifest(manifest)

    def get_shadow_evidence_manifest(self, shadow_evidence_id: str):
        return self._output.get_shadow_evidence_manifest(
            shadow_evidence_id
        ) or self._source.get_shadow_evidence_manifest(shadow_evidence_id)

    def put_promotion_decision(self, decision) -> RepositoryPutResult:
        return self._output.put_promotion_decision(decision)

    def get_promotion_decision(self, promotion_decision_id: str):
        return self._output.get_promotion_decision(
            promotion_decision_id
        ) or self._source.get_promotion_decision(promotion_decision_id)

    def put_champion_assignment(self, assignment) -> RepositoryPutResult:
        return self._output.put_champion_assignment(assignment)

    def get_champion_assignment(self, assignment_id: str):
        return self._output.get_champion_assignment(
            assignment_id
        ) or self._source.get_champion_assignment(assignment_id)

    def get_champion_assignments_for_scope(
        self,
        *,
        component: str,
        target_kind: str,
        horizon_ns: int,
        mode: str,
        scenario_id: str | None = None,
    ) -> tuple:
        output_rows = self._output.get_champion_assignments_for_scope(
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            scenario_id=scenario_id,
        )
        if output_rows:
            return output_rows
        return self._source.get_champion_assignments_for_scope(
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            scenario_id=scenario_id,
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
        current = self._output.get_current_champion_assignment(
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            as_of_ns=as_of_ns,
            scenario_id=scenario_id,
        )
        if current is not None:
            return current
        return self._source.get_current_champion_assignment(
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            as_of_ns=as_of_ns,
            scenario_id=scenario_id,
        )

    def put_challenger_lifecycle_event(self, event) -> RepositoryPutResult:
        return self._output.put_challenger_lifecycle_event(event)

    def get_challenger_lifecycle_events(self, challenger_registration_id: str) -> tuple:
        output_rows = self._output.get_challenger_lifecycle_events(challenger_registration_id)
        if output_rows:
            return output_rows
        return self._source.get_challenger_lifecycle_events(challenger_registration_id)

    def put_opportunity_policy(self, policy) -> RepositoryPutResult:
        return self._output.put_opportunity_policy(policy)

    def get_opportunity_policy(self, opportunity_policy_id: str):
        row = self._output.get_opportunity_policy(opportunity_policy_id)
        if row is not None:
            return row
        return self._source.get_opportunity_policy(opportunity_policy_id)

    def put_opportunity_assessment(self, assessment) -> RepositoryPutResult:
        return self._output.put_opportunity_assessment(assessment)

    def get_opportunity_assessment(self, assessment_id: str):
        row = self._output.get_opportunity_assessment(assessment_id)
        if row is not None:
            return row
        return self._source.get_opportunity_assessment(assessment_id)

    def get_opportunity_assessments_by_forecast(self, forecast_id: str) -> tuple:
        output_rows = self._output.get_opportunity_assessments_by_forecast(forecast_id)
        if output_rows:
            return output_rows
        return self._source.get_opportunity_assessments_by_forecast(forecast_id)

    def put_execution_policy(self, policy) -> RepositoryPutResult:
        return self._output.put_execution_policy(policy)

    def get_execution_policy(self, execution_policy_id: str):
        row = self._output.get_execution_policy(execution_policy_id)
        if row is not None:
            return row
        return self._source.get_execution_policy(execution_policy_id)

    def put_paper_portfolio_snapshot(self, snapshot) -> RepositoryPutResult:
        return self._output.put_paper_portfolio_snapshot(snapshot)

    def get_paper_portfolio_snapshot(self, snapshot_id: str):
        row = self._output.get_paper_portfolio_snapshot(snapshot_id)
        if row is not None:
            return row
        return self._source.get_paper_portfolio_snapshot(snapshot_id)

    def put_trade_proposal(self, proposal) -> RepositoryPutResult:
        return self._output.put_trade_proposal(proposal)

    def get_trade_proposal(self, proposal_id: str):
        row = self._output.get_trade_proposal(proposal_id)
        if row is not None:
            return row
        return self._source.get_trade_proposal(proposal_id)

    def put_risk_decision(self, decision) -> RepositoryPutResult:
        return self._output.put_risk_decision(decision)

    def get_risk_decision(self, risk_decision_id: str):
        row = self._output.get_risk_decision(risk_decision_id)
        if row is not None:
            return row
        return self._source.get_risk_decision(risk_decision_id)

    def put_runtime_activation_policy(self, policy) -> RepositoryPutResult:
        return self._output.put_runtime_activation_policy(policy)

    def get_runtime_activation_policy(self, activation_policy_id: str):
        row = self._output.get_runtime_activation_policy(activation_policy_id)
        if row is not None:
            return row
        return self._source.get_runtime_activation_policy(activation_policy_id)

    def put_runtime_activation(self, activation) -> RepositoryPutResult:
        return self._output.put_runtime_activation(activation)

    def get_runtime_activation(self, activation_id: str):
        row = self._output.get_runtime_activation(activation_id)
        if row is not None:
            return row
        return self._source.get_runtime_activation(activation_id)

    def get_runtime_activations_for_scope(self, **kwargs) -> tuple:
        output_rows = self._output.get_runtime_activations_for_scope(**kwargs)
        if output_rows:
            return output_rows
        return self._source.get_runtime_activations_for_scope(**kwargs)

    def get_current_runtime_activation(self, **kwargs):
        row = self._output.get_current_runtime_activation(**kwargs)
        if row is not None:
            return row
        return self._source.get_current_runtime_activation(**kwargs)

    def put_drift_policy(self, policy) -> RepositoryPutResult:
        return self._output.put_drift_policy(policy)

    def get_drift_policy(self, drift_policy_id: str):
        row = self._output.get_drift_policy(drift_policy_id)
        if row is not None:
            return row
        return self._source.get_drift_policy(drift_policy_id)

    def put_drift_assessment(self, assessment) -> RepositoryPutResult:
        return self._output.put_drift_assessment(assessment)

    def get_drift_assessment(self, drift_assessment_id: str):
        row = self._output.get_drift_assessment(drift_assessment_id)
        if row is not None:
            return row
        return self._source.get_drift_assessment(drift_assessment_id)

    def put_governance_alert(self, alert) -> RepositoryPutResult:
        return self._output.put_governance_alert(alert)

    def get_governance_alert(self, alert_id: str):
        row = self._output.get_governance_alert(alert_id)
        if row is not None:
            return row
        return self._source.get_governance_alert(alert_id)

    def put_fail_safe_policy(self, policy) -> RepositoryPutResult:
        return self._output.put_fail_safe_policy(policy)

    def get_fail_safe_policy(self, fail_safe_policy_id: str):
        row = self._output.get_fail_safe_policy(fail_safe_policy_id)
        if row is not None:
            return row
        return self._source.get_fail_safe_policy(fail_safe_policy_id)

    def put_fail_safe_decision(self, decision) -> RepositoryPutResult:
        return self._output.put_fail_safe_decision(decision)

    def get_fail_safe_decision(self, decision_id: str):
        row = self._output.get_fail_safe_decision(decision_id)
        if row is not None:
            return row
        return self._source.get_fail_safe_decision(decision_id)

    def put_rollback_policy(self, policy) -> RepositoryPutResult:
        return self._output.put_rollback_policy(policy)

    def get_rollback_policy(self, rollback_policy_id: str):
        row = self._output.get_rollback_policy(rollback_policy_id)
        if row is not None:
            return row
        return self._source.get_rollback_policy(rollback_policy_id)

    def put_rollback_decision(self, decision) -> RepositoryPutResult:
        return self._output.put_rollback_decision(decision)

    def get_rollback_decision(self, rollback_decision_id: str):
        row = self._output.get_rollback_decision(rollback_decision_id)
        if row is not None:
            return row
        return self._source.get_rollback_decision(rollback_decision_id)

    def put_governance_event(self, event) -> RepositoryPutResult:
        return self._output.put_governance_event(event)

    def get_governance_event(self, event_id: str):
        row = self._output.get_governance_event(event_id)
        if row is not None:
            return row
        return self._source.get_governance_event(event_id)

    def put_adaptation_policy(self, policy) -> RepositoryPutResult:
        return self._output.put_adaptation_policy(policy)

    def get_adaptation_policy(self, adaptation_policy_id: str):
        row = self._output.get_adaptation_policy(adaptation_policy_id)
        if row is not None:
            return row
        return self._source.get_adaptation_policy(adaptation_policy_id)

    def put_adaptation_assessment(self, assessment) -> RepositoryPutResult:
        return self._output.put_adaptation_assessment(assessment)

    def get_adaptation_assessment(self, adaptation_assessment_id: str):
        row = self._output.get_adaptation_assessment(adaptation_assessment_id)
        if row is not None:
            return row
        return self._source.get_adaptation_assessment(adaptation_assessment_id)

    def put_research_trigger(self, trigger) -> RepositoryPutResult:
        return self._output.put_research_trigger(trigger)

    def get_research_trigger(self, research_trigger_id: str):
        row = self._output.get_research_trigger(research_trigger_id)
        if row is not None:
            return row
        return self._source.get_research_trigger(research_trigger_id)

    def query_research_triggers_by_dedup_key(self, dedup_key: str) -> tuple:
        return self._output.query_research_triggers_by_dedup_key(dedup_key)

    def put_adaptation_campaign(self, campaign) -> RepositoryPutResult:
        return self._output.put_adaptation_campaign(campaign)

    def get_adaptation_campaign(self, adaptation_campaign_id: str):
        row = self._output.get_adaptation_campaign(adaptation_campaign_id)
        if row is not None:
            return row
        return self._source.get_adaptation_campaign(adaptation_campaign_id)

    def put_adaptation_event(self, event) -> RepositoryPutResult:
        return self._output.put_adaptation_event(event)

    def get_adaptation_event(self, event_id: str):
        row = self._output.get_adaptation_event(event_id)
        if row is not None:
            return row
        return self._source.get_adaptation_event(event_id)

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
        raise NotImplementedError("REPLAY_VISIBLE_REPOSITORY_RANGE_QUERY_FORBIDDEN")

    def check_health(self) -> dict[str, object]:
        return {
            "available": True,
            "backend": "replay_visible",
            "decision_time_ns": self._decision_time_ns,
        }


def recompose_snapshot_at(
    *,
    source_repository: IntelligenceRepository,
    visibility_index: ReplayVisibilityIndex,
    decision_time_ns: int,
    snapshot_request_builder,
):
    """Recompose snapshot at historical T using frozen delivery overlay."""
    visible_repo = ReplayVisibleRepository(
        source_repository=source_repository,
        output_repository=source_repository,
        visibility_index=visibility_index,
        decision_time_ns=decision_time_ns,
    )
    request = snapshot_request_builder(decision_time_ns)
    from ..snapshots.builder import inspect_snapshot_build

    return inspect_snapshot_build(visible_repo, request)


__all__ = [
    "ReplayVisibilityIndex",
    "ReplayVisibleRepository",
    "recompose_snapshot_at",
]
