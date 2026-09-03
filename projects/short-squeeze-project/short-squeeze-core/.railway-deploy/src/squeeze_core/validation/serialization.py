import json

from squeeze_core.serialization.canonical_json import canonical_hash, canonical_json_bytes

from .models import (
    CandidateOutcomeObservation,
    DetectionTimeEvidence,
    FieldComparisonEntry,
    OriginalCandidateSnapshot,
    PublicValidationCase,
    RebuiltAsOfSnapshot,
    RuleValidationEntry,
    ValidationCase,
    ValidationCaseConclusion,
)


def serialize_detection_time(result: DetectionTimeEvidence) -> bytes:
    return canonical_json_bytes(result)


def deserialize_detection_time(serialized: bytes | str) -> DetectionTimeEvidence:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return DetectionTimeEvidence.model_validate(json.loads(raw))


def detection_time_hash(result: DetectionTimeEvidence) -> str:
    return canonical_hash(result)


def serialize_original_snapshot(result: OriginalCandidateSnapshot) -> bytes:
    return canonical_json_bytes(result)


def deserialize_original_snapshot(serialized: bytes | str) -> OriginalCandidateSnapshot:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return OriginalCandidateSnapshot.model_validate(json.loads(raw))


def original_snapshot_hash(result: OriginalCandidateSnapshot) -> str:
    return canonical_hash(result)


def serialize_replay(result: RebuiltAsOfSnapshot) -> bytes:
    return canonical_json_bytes(result)


def deserialize_replay(serialized: bytes | str) -> RebuiltAsOfSnapshot:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return RebuiltAsOfSnapshot.model_validate(json.loads(raw))


def replay_hash(result: RebuiltAsOfSnapshot) -> str:
    return canonical_hash(result)


def serialize_field_comparison(result: FieldComparisonEntry) -> bytes:
    return canonical_json_bytes(result)


def deserialize_field_comparison(serialized: bytes | str) -> FieldComparisonEntry:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return FieldComparisonEntry.model_validate(json.loads(raw))


def field_comparison_hash(result: FieldComparisonEntry) -> str:
    return canonical_hash(result)


def serialize_rule_validation(result: RuleValidationEntry) -> bytes:
    return canonical_json_bytes(result)


def deserialize_rule_validation(serialized: bytes | str) -> RuleValidationEntry:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return RuleValidationEntry.model_validate(json.loads(raw))


def rule_validation_hash(result: RuleValidationEntry) -> str:
    return canonical_hash(result)


def serialize_outcome_observation(result: CandidateOutcomeObservation) -> bytes:
    return canonical_json_bytes(result)


def deserialize_outcome_observation(serialized: bytes | str) -> CandidateOutcomeObservation:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return CandidateOutcomeObservation.model_validate(json.loads(raw))


def outcome_observation_hash(result: CandidateOutcomeObservation) -> str:
    return canonical_hash(result)


def serialize_case_conclusion(result: ValidationCaseConclusion) -> bytes:
    return canonical_json_bytes(result)


def deserialize_case_conclusion(serialized: bytes | str) -> ValidationCaseConclusion:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return ValidationCaseConclusion.model_validate(json.loads(raw))


def case_conclusion_hash(result: ValidationCaseConclusion) -> str:
    return canonical_hash(result)


def serialize_validation_case(result: ValidationCase) -> bytes:
    return canonical_json_bytes(result)


def deserialize_validation_case(serialized: bytes | str) -> ValidationCase:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return ValidationCase.model_validate(json.loads(raw))


def validation_case_hash(result: ValidationCase) -> str:
    return canonical_hash(result)


def serialize_public_case(result: PublicValidationCase) -> bytes:
    return canonical_json_bytes(result)


def deserialize_public_case(serialized: bytes | str) -> PublicValidationCase:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return PublicValidationCase.model_validate(json.loads(raw))


def public_case_hash(result: PublicValidationCase) -> str:
    return canonical_hash(result)


__all__ = [
    "case_conclusion_hash",
    "deserialize_case_conclusion",
    "deserialize_detection_time",
    "deserialize_field_comparison",
    "deserialize_original_snapshot",
    "deserialize_outcome_observation",
    "deserialize_public_case",
    "deserialize_replay",
    "deserialize_rule_validation",
    "deserialize_validation_case",
    "detection_time_hash",
    "field_comparison_hash",
    "original_snapshot_hash",
    "outcome_observation_hash",
    "public_case_hash",
    "replay_hash",
    "rule_validation_hash",
    "serialize_case_conclusion",
    "serialize_detection_time",
    "serialize_field_comparison",
    "serialize_original_snapshot",
    "serialize_outcome_observation",
    "serialize_public_case",
    "serialize_replay",
    "serialize_rule_validation",
    "serialize_validation_case",
    "validation_case_hash",
]
