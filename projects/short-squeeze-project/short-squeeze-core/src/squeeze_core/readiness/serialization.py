import json

from squeeze_core.serialization.canonical_json import canonical_hash, canonical_json_bytes

from .models import (
    DomainCoverageSnapshot,
    EvidenceAgeAlignment,
    EvidenceConflictSummary,
    EvidenceMissingnessSummary,
    EvidenceReadinessSnapshot,
    InputSufficiencyResult,
    ReportingPeriodAlignment,
)


def serialize_coverage_snapshot(result: DomainCoverageSnapshot) -> bytes:
    return canonical_json_bytes(result)


def deserialize_coverage_snapshot(serialized: bytes | str) -> DomainCoverageSnapshot:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return DomainCoverageSnapshot.model_validate(json.loads(raw))


def coverage_snapshot_hash(result: DomainCoverageSnapshot) -> str:
    return canonical_hash(result)


def serialize_age_alignment(result: EvidenceAgeAlignment) -> bytes:
    return canonical_json_bytes(result)


def deserialize_age_alignment(serialized: bytes | str) -> EvidenceAgeAlignment:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return EvidenceAgeAlignment.model_validate(json.loads(raw))


def age_alignment_hash(result: EvidenceAgeAlignment) -> str:
    return canonical_hash(result)


def serialize_reporting_alignment(result: ReportingPeriodAlignment) -> bytes:
    return canonical_json_bytes(result)


def deserialize_reporting_alignment(serialized: bytes | str) -> ReportingPeriodAlignment:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return ReportingPeriodAlignment.model_validate(json.loads(raw))


def reporting_alignment_hash(result: ReportingPeriodAlignment) -> str:
    return canonical_hash(result)


def serialize_conflict_summary(result: EvidenceConflictSummary) -> bytes:
    return canonical_json_bytes(result)


def deserialize_conflict_summary(serialized: bytes | str) -> EvidenceConflictSummary:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return EvidenceConflictSummary.model_validate(json.loads(raw))


def conflict_summary_hash(result: EvidenceConflictSummary) -> str:
    return canonical_hash(result)


def serialize_missingness_summary(result: EvidenceMissingnessSummary) -> bytes:
    return canonical_json_bytes(result)


def deserialize_missingness_summary(serialized: bytes | str) -> EvidenceMissingnessSummary:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return EvidenceMissingnessSummary.model_validate(json.loads(raw))


def missingness_summary_hash(result: EvidenceMissingnessSummary) -> str:
    return canonical_hash(result)


def serialize_sufficiency_result(result: InputSufficiencyResult) -> bytes:
    return canonical_json_bytes(result)


def deserialize_sufficiency_result(serialized: bytes | str) -> InputSufficiencyResult:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return InputSufficiencyResult.model_validate(json.loads(raw))


def sufficiency_result_hash(result: InputSufficiencyResult) -> str:
    return canonical_hash(result)


def serialize_readiness_snapshot(result: EvidenceReadinessSnapshot) -> bytes:
    return canonical_json_bytes(result)


def deserialize_readiness_snapshot(serialized: bytes | str) -> EvidenceReadinessSnapshot:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return EvidenceReadinessSnapshot.model_validate(json.loads(raw))


def readiness_snapshot_hash(result: EvidenceReadinessSnapshot) -> str:
    return canonical_hash(result)
