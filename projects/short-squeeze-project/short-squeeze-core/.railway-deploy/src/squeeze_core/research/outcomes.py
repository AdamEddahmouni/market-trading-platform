from squeeze_core.adapters.diagnostics import DiagnosticSeverity

from .diagnostics import ResearchDiagnostic, ResearchDiagnosticCode
from .models import (
    OutcomeCompleteness,
    OutcomeLabel,
    OutcomeLabelPolicy,
    OutcomeLabelResult,
    RetrospectiveOutcomeObservation,
)


def label_outcome(
    observation: RetrospectiveOutcomeObservation,
    policy: OutcomeLabelPolicy,
) -> OutcomeLabelResult:
    if observation.reference_price_policy != policy.reference_price_policy:
        raise ValueError("RESEARCH_OUTCOME_POLICY_UNSUPPORTED", observation.reference_price_policy)
    if observation.horizon != policy.horizon:
        raise ValueError("RESEARCH_OUTCOME_POLICY_UNSUPPORTED", observation.horizon)

    upward = (
        observation.maximum_observed_move_percent is not None
        and observation.maximum_observed_move_percent >= policy.upward_threshold_percent
    )
    downward = (
        observation.maximum_adverse_move_percent is not None
        and observation.maximum_adverse_move_percent <= policy.downward_threshold_percent
    )
    diagnostics: list[ResearchDiagnostic] = []
    if observation.completeness is OutcomeCompleteness.UNAVAILABLE:
        label = OutcomeLabel.OUTCOME_UNKNOWN
        diagnostics.append(ResearchDiagnostic(
            code=ResearchDiagnosticCode.RESEARCH_OUTCOME_UNKNOWN,
            severity=DiagnosticSeverity.WARNING,
            case_id=observation.case_id,
        ))
    elif upward and downward:
        label = OutcomeLabel.MIXED_OR_VOLATILE
        diagnostics.append(ResearchDiagnostic(
            code=ResearchDiagnosticCode.RESEARCH_OUTCOME_MIXED,
            severity=DiagnosticSeverity.INFO,
            case_id=observation.case_id,
        ))
    elif upward:
        label = OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE
    elif downward:
        label = OutcomeLabel.SUBSTANTIAL_DOWNWARD_MOVE
    elif observation.completeness is OutcomeCompleteness.COMPLETE:
        label = OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE
    else:
        label = OutcomeLabel.OUTCOME_INSUFFICIENT_DATA
        diagnostics.extend((
            ResearchDiagnostic(
                code=ResearchDiagnosticCode.RESEARCH_OUTCOME_PARTIAL,
                severity=DiagnosticSeverity.WARNING,
                case_id=observation.case_id,
            ),
            ResearchDiagnostic(
                code=ResearchDiagnosticCode.RESEARCH_OUTCOME_INSUFFICIENT,
                severity=DiagnosticSeverity.WARNING,
                case_id=observation.case_id,
            ),
        ))

    return OutcomeLabelResult(
        outcome_observation_id=str(observation.deterministic_id),
        policy_version=policy.policy_version,
        label=label,
        reference_price_policy=observation.reference_price_policy,
        detection_boundary=observation.detection_boundary,
        horizon=observation.horizon,
        upward_threshold_percent=policy.upward_threshold_percent,
        downward_threshold_percent=policy.downward_threshold_percent,
        maximum_observed_move_percent=observation.maximum_observed_move_percent,
        maximum_adverse_move_percent=observation.maximum_adverse_move_percent,
        completeness=observation.completeness,
        supporting_observation_ids=observation.supporting_observation_ids,
        diagnostics=tuple(diagnostics),
    )


__all__ = ["label_outcome"]
