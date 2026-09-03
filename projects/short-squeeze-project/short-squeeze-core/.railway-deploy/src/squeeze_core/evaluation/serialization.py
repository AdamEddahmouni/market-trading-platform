import json

from squeeze_core.serialization import canonical_hash, canonical_json_bytes

from .models import CandidateEvaluationResult, RuleEvaluationResult


def serialize_rule_result(result: RuleEvaluationResult) -> bytes:
    return canonical_json_bytes(result)


def deserialize_rule_result(value: bytes | str) -> RuleEvaluationResult:
    raw = value.decode("utf-8") if isinstance(value, bytes) else value
    return RuleEvaluationResult.model_validate(json.loads(raw))


def rule_result_hash(result: RuleEvaluationResult) -> str:
    return canonical_hash(result)


def serialize_candidate_evaluation(result: CandidateEvaluationResult) -> bytes:
    return canonical_json_bytes(result)


def deserialize_candidate_evaluation(value: bytes | str) -> CandidateEvaluationResult:
    raw = value.decode("utf-8") if isinstance(value, bytes) else value
    return CandidateEvaluationResult.model_validate(json.loads(raw))


def candidate_evaluation_hash(result: CandidateEvaluationResult) -> str:
    return canonical_hash(result)


__all__ = [
    "candidate_evaluation_hash", "deserialize_candidate_evaluation",
    "deserialize_rule_result", "rule_result_hash", "serialize_candidate_evaluation",
    "serialize_rule_result",
]

