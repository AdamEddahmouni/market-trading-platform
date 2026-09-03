"""Counterfactual outcome label policy evaluation from stored observations."""

from __future__ import annotations

from squeeze_core.research.classification import classify_research_case
from squeeze_core.research.models import (
    OutcomeCompleteness,
    OutcomeLabel,
    OutcomeLabelPolicy,
    ResearchDatasetRow,
    RetrospectiveOutcomeObservation,
)
from squeeze_core.research.outcomes import label_outcome


def outcome_policy_from_spec(spec) -> OutcomeLabelPolicy:
    return OutcomeLabelPolicy(
        policy_version=spec.policy_version,
        reference_price_policy=spec.reference_price_policy,
        horizon=spec.horizon,
        upward_threshold_percent=spec.upward_threshold_percent,
        downward_threshold_percent=spec.downward_threshold_percent,
        provisional=spec.provisional,
        rationale_code=spec.rationale_code,
    )


def _completeness_for_row(row: ResearchDatasetRow) -> OutcomeCompleteness:
    if row.outcome_label is OutcomeLabel.OUTCOME_UNKNOWN:
        return OutcomeCompleteness.UNAVAILABLE
    if row.outcome_label is OutcomeLabel.OUTCOME_INSUFFICIENT_DATA:
        return OutcomeCompleteness.PARTIAL
    return OutcomeCompleteness.COMPLETE


def _observation_from_row(row: ResearchDatasetRow) -> RetrospectiveOutcomeObservation:
    return RetrospectiveOutcomeObservation(
        case_id=row.case_id,
        symbol=row.symbol,
        detection_boundary=row.evaluation_as_of,
        reference_price_policy=row.outcome_reference_policy,
        horizon=row.outcome_horizon,
        maximum_observed_move_percent=row.maximum_observed_move_percent,
        maximum_adverse_move_percent=row.maximum_adverse_move_percent,
        completeness=_completeness_for_row(row),
        supporting_observation_ids=(row.outcome_observation_id,),
        limitations=row.limitations,
    )


def apply_outcome_policy(
    row: ResearchDatasetRow,
    policy: OutcomeLabelPolicy,
) -> ResearchDatasetRow:
    observation = _observation_from_row(row)
    outcome = label_outcome(observation, policy)
    classification = classify_research_case(
        row.case_id,
        row.research_detection_status,
        outcome.label,
        row.phase_3a_evaluation_id,
        str(outcome.deterministic_id),
    )
    return row.model_copy(
        update={
            "outcome_policy_version": policy.policy_version,
            "outcome_label": outcome.label,
            "research_classification": classification.classification,
        }
    )


__all__ = ["apply_outcome_policy", "outcome_policy_from_spec"]
