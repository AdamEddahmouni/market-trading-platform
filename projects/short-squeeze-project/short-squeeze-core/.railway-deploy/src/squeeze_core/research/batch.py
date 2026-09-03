from pathlib import Path

from squeeze_core.adapters.diagnostics import DiagnosticSeverity

from .classification import classify_research_case
from .detection import evaluate_research_detection
from .diagnostics import ResearchDiagnostic, ResearchDiagnosticCode
from .io import (
    ResearchArtifactError,
    load_case_registry,
    load_outcome_observation,
    load_phase_3a_result,
)
from .models import (
    BatchEvaluationRequest,
    BatchEvaluationResult,
    CandidateCaseRegistryEntry,
    CandidateCaseStatus,
    CandidateResearchCase,
    SkippedResearchCase,
)
from .outcomes import label_outcome
from .policies import load_detection_policy, load_outcome_policy
from .registry import ResearchRegistryError, resolve_registry_cases


class ResearchBatchError(ValueError):
    def __init__(self, code: str, case_id: str | None = None):
        self.code = code
        self.case_id = case_id
        super().__init__(code, case_id)


def _build_case(
    entry: CandidateCaseRegistryEntry,
    registry_path: Path,
    request: BatchEvaluationRequest,
) -> CandidateResearchCase:
    evaluation = load_phase_3a_result(entry, registry_path)
    observation = load_outcome_observation(entry, registry_path)
    detection = evaluate_research_detection(
        evaluation, load_detection_policy(request.research_detection_policy_version)
    )
    outcome = label_outcome(
        observation, load_outcome_policy(request.outcome_label_policy_version)
    )
    classification = classify_research_case(
        entry.case_id,
        detection.status,
        outcome.label,
        str(detection.deterministic_id),
        str(outcome.deterministic_id),
    )
    return CandidateResearchCase(
        case_id=entry.case_id,
        symbol=entry.symbol,
        asset_class=entry.asset_class,
        case_type=entry.case_type,
        case_status=entry.case_status,
        original_platform_status=entry.original_platform_status,
        original_platform_artifact_ids=entry.original_platform_artifact_ids,
        evaluation_as_of=evaluation.as_of,
        phase_3a_policy_version=evaluation.policy_version,
        phase_3a_evaluation_id=str(evaluation.deterministic_id),
        phase_3a_rule_results=evaluation.rule_results,
        detection_policy_version=detection.policy_version,
        research_detection_status=detection.status,
        detection_result_id=str(detection.deterministic_id),
        outcome_policy_version=outcome.policy_version,
        outcome_label=outcome.label,
        outcome_observation_id=outcome.outcome_observation_id,
        outcome_label_result_id=str(outcome.deterministic_id),
        outcome_reference_policy=outcome.reference_price_policy,
        outcome_horizon=outcome.horizon,
        maximum_observed_move_percent=outcome.maximum_observed_move_percent,
        maximum_adverse_move_percent=outcome.maximum_adverse_move_percent,
        outcome_completeness=outcome.completeness,
        outcome_supporting_observation_ids=outcome.supporting_observation_ids,
        research_classification=classification.classification,
        research_classification_id=str(classification.deterministic_id),
        fixture_classification=entry.fixture_classification,
        limitations=entry.limitations,
        diagnostics=detection.diagnostics + outcome.diagnostics,
    )


def _skip(entry: CandidateCaseRegistryEntry) -> SkippedResearchCase:
    diagnostics = [ResearchDiagnostic(
        code=ResearchDiagnosticCode.RESEARCH_CASE_STATUS_INCOMPLETE,
        severity=DiagnosticSeverity.WARNING,
        case_id=entry.case_id,
    )]
    if entry.evaluation_result_path is None and entry.evaluation_request_path is None:
        diagnostics.append(ResearchDiagnostic(
            code=ResearchDiagnosticCode.RESEARCH_CASE_EVALUATION_MISSING,
            severity=DiagnosticSeverity.WARNING,
            case_id=entry.case_id,
        ))
    if entry.outcome_observation_path is None:
        diagnostics.append(ResearchDiagnostic(
            code=ResearchDiagnosticCode.RESEARCH_CASE_OUTCOME_MISSING,
            severity=DiagnosticSeverity.WARNING,
            case_id=entry.case_id,
        ))
    return SkippedResearchCase(
        case_id=entry.case_id,
        symbol=entry.symbol,
        case_status=entry.case_status,
        diagnostics=tuple(diagnostics),
    )


def run_research_batch(
    request: BatchEvaluationRequest,
    registry_path: Path,
) -> BatchEvaluationResult:
    if not request.case_ids:
        raise ResearchBatchError("RESEARCH_BATCH_EMPTY")
    registry = load_case_registry(registry_path)
    if registry.registry_version != request.case_registry_version:
        raise ResearchBatchError("RESEARCH_BATCH_CASE_FAILED")
    try:
        entries = resolve_registry_cases(registry, request.case_ids, request.ordering_policy)
    except ResearchRegistryError as exc:
        raise ResearchBatchError(exc.code) from exc

    results: list[CandidateResearchCase] = []
    skipped: list[SkippedResearchCase] = []
    diagnostics: list[ResearchDiagnostic] = []
    for entry in entries:
        incomplete = (
            entry.case_status is not CandidateCaseStatus.COMPLETE
            or (entry.evaluation_result_path is None and entry.evaluation_request_path is None)
            or entry.outcome_observation_path is None
        )
        if incomplete:
            if request.fail_fast:
                raise ResearchBatchError("RESEARCH_BATCH_CASE_FAILED", entry.case_id)
            skipped.append(_skip(entry))
            diagnostics.append(ResearchDiagnostic(
                code=ResearchDiagnosticCode.RESEARCH_BATCH_CASE_SKIPPED,
                severity=DiagnosticSeverity.WARNING,
                case_id=entry.case_id,
            ))
            continue
        try:
            results.append(_build_case(entry, registry_path, request))
        except (ResearchArtifactError, ValueError) as exc:
            if request.fail_fast:
                raise ResearchBatchError("RESEARCH_BATCH_CASE_FAILED", entry.case_id) from exc
            skipped.append(_skip(entry))
            diagnostics.append(ResearchDiagnostic(
                code=ResearchDiagnosticCode.RESEARCH_BATCH_CASE_FAILED,
                severity=DiagnosticSeverity.ERROR,
                case_id=entry.case_id,
            ))
    if skipped:
        diagnostics.append(ResearchDiagnostic(
            code=ResearchDiagnosticCode.RESEARCH_BATCH_PARTIAL,
            severity=DiagnosticSeverity.WARNING,
        ))
    if len(results) < 30:
        diagnostics.append(ResearchDiagnostic(
            code=ResearchDiagnosticCode.RESEARCH_BATCH_SMALL_SAMPLE,
            severity=DiagnosticSeverity.INFO,
        ))
    return BatchEvaluationResult(
        batch_version=request.batch_version,
        request_id=str(request.deterministic_id),
        case_registry_id=str(registry.deterministic_id),
        phase_3a_policy_version=request.phase_3a_policy_version,
        research_detection_policy_version=request.research_detection_policy_version,
        outcome_label_policy_version=request.outcome_label_policy_version,
        case_results=tuple(results),
        skipped_cases=tuple(skipped),
        diagnostics=tuple(diagnostics),
    )


__all__ = ["ResearchBatchError", "run_research_batch"]
