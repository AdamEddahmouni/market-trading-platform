import json
from pathlib import Path

from squeeze_core.evaluation import CandidateEvaluationResult, RuleEvaluationRequest, evaluate_candidate
from squeeze_core.evaluation.io import load_evaluation_evidence
from squeeze_core.evaluation.policies import load_policy
from squeeze_core.evaluation.serialization import deserialize_candidate_evaluation

from .models import (
    CandidateCaseRegistry,
    CandidateCaseRegistryEntry,
    Phase3AEvaluationRequestArtifact,
    RetrospectiveOutcomeObservation,
)


class ResearchArtifactError(ValueError):
    pass


def resolve_artifact_path(registry_path: Path, declared_path: str) -> Path:
    candidate = Path(declared_path)
    if candidate.is_absolute():
        raise ResearchArtifactError("absolute artifact paths are forbidden")
    fixture_root = registry_path.resolve().parent.parent
    resolved = (registry_path.resolve().parent / candidate).resolve()
    try:
        resolved.relative_to(fixture_root)
    except ValueError as exc:
        raise ResearchArtifactError("artifact path escapes project root") from exc
    return resolved


def load_case_registry(path: Path) -> CandidateCaseRegistry:
    return CandidateCaseRegistry.model_validate_json(path.read_bytes())


def load_phase_3a_result(
    entry: CandidateCaseRegistryEntry,
    registry_path: Path,
) -> CandidateEvaluationResult:
    if entry.evaluation_result_path is not None:
        result = deserialize_candidate_evaluation(
            resolve_artifact_path(registry_path, entry.evaluation_result_path).read_bytes()
        )
    elif entry.evaluation_request_path is not None:
        artifact = Phase3AEvaluationRequestArtifact.model_validate_json(
            resolve_artifact_path(registry_path, entry.evaluation_request_path).read_bytes()
        )
        policy = load_policy(resolve_artifact_path(registry_path, artifact.policy_path))
        observations, metrics, readiness, defaults = load_evaluation_evidence(
            resolve_artifact_path(registry_path, artifact.evidence_path)
        )
        request_values = artifact.model_dump(
            exclude={"schema_version", "policy_path", "evidence_path"}
        )
        request_values.update({
            "input_observations": observations,
            "input_metrics": metrics,
            "input_readiness_results": readiness,
            "default_substitution_fields": defaults,
        })
        result = evaluate_candidate(RuleEvaluationRequest.model_validate(request_values), policy)
    else:
        raise ResearchArtifactError("RESEARCH_CASE_EVALUATION_MISSING")
    if result.policy_version != entry.phase_3a_policy_version:
        raise ResearchArtifactError("RESEARCH_DETECTION_POLICY_UNSUPPORTED")
    if result.symbol != entry.symbol or result.as_of != entry.evaluation_as_of:
        raise ResearchArtifactError("RESEARCH_CASE_IDENTITY_CONFLICT")
    return result


def load_outcome_observation(
    entry: CandidateCaseRegistryEntry,
    registry_path: Path,
) -> RetrospectiveOutcomeObservation:
    if entry.outcome_observation_path is None:
        raise ResearchArtifactError("RESEARCH_CASE_OUTCOME_MISSING")
    result = RetrospectiveOutcomeObservation.model_validate_json(
        resolve_artifact_path(registry_path, entry.outcome_observation_path).read_bytes()
    )
    if result.case_id != entry.case_id or result.symbol != entry.symbol:
        raise ResearchArtifactError("RESEARCH_CASE_IDENTITY_CONFLICT")
    return result


__all__ = [
    "ResearchArtifactError", "load_case_registry", "load_outcome_observation",
    "load_phase_3a_result",
    "resolve_artifact_path",
]
