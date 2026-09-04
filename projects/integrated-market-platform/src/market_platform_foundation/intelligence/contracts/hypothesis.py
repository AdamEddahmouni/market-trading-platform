"""HypothesisV1 — falsifiable market-mechanism hypothesis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    IntelligenceScope,
    QualitySummary,
    TimeHorizonNs,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    normalize_unique_refs,
    normalize_unique_strings,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    scope_from_dict,
    scope_to_dict,
    time_horizon_from_dict,
    time_horizon_to_dict,
    validate_id,
    validate_schema_version,
    validate_support_score,
    validate_timestamp_ns,
)


@dataclass(frozen=True, slots=True)
class HypothesisV1:
    """Testable mechanism hypothesis derived from evidence.

    What: structured thesis about market mechanism (squeeze, accumulation, etc.).
    Not: a directional forecast or trade opportunity.
    Producers: composite hypothesis layer (future BUILD).
    Consumers: forecast generation, opportunity screening.
    Immutable after construction.
    """

    hypothesis_id: str
    schema_version: str
    hypothesis_type: str
    scope: IntelligenceScope
    generated_at_ns: int
    snapshot_id: str
    quality: QualitySummary
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    support_score: float | None = None
    mechanism: dict[str, Any] = field(default_factory=dict)
    invalidation_conditions: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    applicable_horizon: TimeHorizonNs | None = None
    lineage_refs: tuple[ContractReference, ...] = ()
    explanation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.hypothesis_id, field_name="hypothesis_id")
        validate_schema_version(self.schema_version)
        if not self.hypothesis_type or not str(self.hypothesis_type).strip():
            raise ValueError("HYPOTHESIS_TYPE_REQUIRED")
        validate_timestamp_ns(self.generated_at_ns, field_name="generated_at_ns")
        validate_id(self.snapshot_id, field_name="snapshot_id")
        if self.support_score is not None:
            validate_support_score(self.support_score)
        object.__setattr__(
            self, "supporting_evidence_ids", normalize_unique_strings(self.supporting_evidence_ids)
        )
        object.__setattr__(
            self, "contradicting_evidence_ids", normalize_unique_strings(self.contradicting_evidence_ids)
        )
        object.__setattr__(
            self, "invalidation_conditions", normalize_unique_strings(self.invalidation_conditions)
        )
        object.__setattr__(self, "missing_information", normalize_unique_strings(self.missing_information))
        object.__setattr__(self, "lineage_refs", normalize_unique_refs(self.lineage_refs))
        if not isinstance(self.mechanism, dict):
            raise ValueError("HYPOTHESIS_MECHANISM_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("HYPOTHESIS_METADATA_INVALID")


_HYPOTHESIS_ALLOWED = dataclass_field_names(HypothesisV1)


def hypothesis_v1_to_dict(record: HypothesisV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "hypothesis_id": record.hypothesis_id,
        "schema_version": record.schema_version,
        "hypothesis_type": record.hypothesis_type,
        "scope": scope_to_dict(record.scope),
        "generated_at_ns": record.generated_at_ns,
        "snapshot_id": record.snapshot_id,
        "quality": quality_summary_to_dict(record.quality),
    }
    if record.supporting_evidence_ids:
        body["supporting_evidence_ids"] = list(record.supporting_evidence_ids)
    if record.contradicting_evidence_ids:
        body["contradicting_evidence_ids"] = list(record.contradicting_evidence_ids)
    if record.support_score is not None:
        body["support_score"] = record.support_score
    if record.mechanism:
        body["mechanism"] = dict(record.mechanism)
    if record.invalidation_conditions:
        body["invalidation_conditions"] = list(record.invalidation_conditions)
    if record.missing_information:
        body["missing_information"] = list(record.missing_information)
    if record.applicable_horizon is not None:
        body["applicable_horizon"] = time_horizon_to_dict(record.applicable_horizon)
    if record.lineage_refs:
        body["lineage_refs"] = [contract_reference_to_dict(ref) for ref in record.lineage_refs]
    if record.explanation is not None:
        body["explanation"] = record.explanation
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def hypothesis_v1_from_dict(payload: dict[str, Any]) -> HypothesisV1:
    reject_unknown_keys(payload, _HYPOTHESIS_ALLOWED)
    return HypothesisV1(
        hypothesis_id=str(payload["hypothesis_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        hypothesis_type=str(payload["hypothesis_type"]),
        scope=scope_from_dict(payload["scope"]),
        generated_at_ns=int(payload["generated_at_ns"]),
        snapshot_id=str(payload["snapshot_id"]),
        quality=quality_summary_from_dict(payload["quality"]),
        supporting_evidence_ids=tuple(payload.get("supporting_evidence_ids") or ()),
        contradicting_evidence_ids=tuple(payload.get("contradicting_evidence_ids") or ()),
        support_score=payload.get("support_score"),
        mechanism=dict(payload.get("mechanism") or {}),
        invalidation_conditions=tuple(payload.get("invalidation_conditions") or ()),
        missing_information=tuple(payload.get("missing_information") or ()),
        applicable_horizon=(
            time_horizon_from_dict(payload["applicable_horizon"])
            if payload.get("applicable_horizon") is not None
            else None
        ),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        explanation=payload.get("explanation"),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = ["HypothesisV1", "hypothesis_v1_from_dict", "hypothesis_v1_to_dict"]
