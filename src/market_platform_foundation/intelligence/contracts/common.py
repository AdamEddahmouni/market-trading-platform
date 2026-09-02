"""Shared primitives for intelligence contracts (BUILD 01).

These types are not top-level intelligence records. They compose the canonical
V1 contracts and enforce consistent identity, lineage, quality, and serialization.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Any, TypeVar

from ...contracts.schema_compat import round_trip_record

INTELLIGENCE_SCHEMA_VERSION = "1"
INTELLIGENCE_CONTRACTS_VERSION = "platform/intelligence/contracts/1"

T = TypeVar("T")


class ContractKind(StrEnum):
    EVENT = "event"
    DETECTION = "detection"
    ROUTING_DECISION = "routing_decision"
    INFERENCE_JOB = "inference_job"
    SNAPSHOT = "snapshot"
    SIGNAL = "signal"
    EVIDENCE = "evidence"
    HYPOTHESIS = "hypothesis"
    FORECAST = "forecast"
    OPPORTUNITY = "opportunity"
    OUTCOME = "outcome"
    PREDICTION_LEDGER_ENTRY = "prediction_ledger_entry"
    RUN_MANIFEST = "run_manifest"
    STRATEGY_MATCH = "strategy_match"
    STRATEGY_ATTRIBUTION = "strategy_attribution"


class QualityState(StrEnum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class Direction(StrEnum):
    """Signed market direction — not an order side."""

    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class OpportunitySide(StrEnum):
    """Economic opportunity orientation — not broker execution authority."""

    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class EvidenceApplicability(StrEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATA_QUALITY_FAILURE = "DATA_QUALITY_FAILURE"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    OUT_OF_DISTRIBUTION = "OUT_OF_DISTRIBUTION"
    EXPERT_CONFLICT = "EXPERT_CONFLICT"


class OutcomeResolutionStatus(StrEnum):
    SETTLED = "SETTLED"
    UNLABELABLE = "UNLABELABLE"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True, slots=True)
class ContractReference:
    """Typed pointer to an upstream intelligence or envelope record."""

    kind: str
    id: str
    schema_version: str = INTELLIGENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        validate_id(self.id, field_name="reference.id")
        if not self.kind or not str(self.kind).strip():
            raise ValueError("REFERENCE_KIND_REQUIRED")
        validate_schema_version(self.schema_version)


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Provider/source provenance without embedding upstream payloads."""

    provider_id: str
    source_type: str
    source_record_id: str
    raw_reference: str | None = None
    external_id: str | None = None

    def __post_init__(self) -> None:
        validate_id(self.provider_id, field_name="provider_id")
        validate_id(self.source_record_id, field_name="source_record_id")
        if not self.source_type or not str(self.source_type).strip():
            raise ValueError("SOURCE_TYPE_REQUIRED")


@dataclass(frozen=True, slots=True)
class QualitySummary:
    """Minimal interoperable quality envelope (BUILD 04 owns detailed taxonomy)."""

    state: QualityState
    flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state, QualityState):
            object.__setattr__(self, "state", QualityState(str(self.state)))
        object.__setattr__(self, "flags", normalize_unique_strings(self.flags))


@dataclass(frozen=True, slots=True)
class IntelligenceScope:
    """Instrument and/or market context scope for intelligence records."""

    instrument_ids: tuple[str, ...] = ()
    context_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "instrument_ids", normalize_unique_strings(self.instrument_ids))
        for instrument_id in self.instrument_ids:
            validate_id(instrument_id, field_name="instrument_id")


@dataclass(frozen=True, slots=True)
class TimeHorizonNs:
    """Explicit non-negative forecast/hypothesis horizon in nanoseconds."""

    duration_ns: int

    def __post_init__(self) -> None:
        if self.duration_ns < 0:
            raise ValueError("HORIZON_NEGATIVE")
        if self.duration_ns == 0:
            raise ValueError("HORIZON_ZERO_NOT_ALLOWED")


@dataclass(frozen=True, slots=True)
class ComponentLineage:
    """Optional producing component identity for evidence/forecast/manifest records."""

    component_id: str | None = None
    component_version: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    adapter_id: str | None = None
    adapter_version: str | None = None
    code_revision: str | None = None


@dataclass(frozen=True, slots=True)
class ForecastTarget:
    """Machine-testable forecast subject (not a narrative label)."""

    target_kind: str
    instrument_id: str
    parameters: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.target_kind or not str(self.target_kind).strip():
            raise ValueError("FORECAST_TARGET_KIND_REQUIRED")
        validate_id(self.instrument_id, field_name="instrument_id")
        if not isinstance(self.parameters, dict):
            raise ValueError("FORECAST_TARGET_PARAMETERS_INVALID")


@dataclass(frozen=True, slots=True)
class ForecastEstimate:
    """Structured prediction payload — distinguishes score vs calibrated probability."""

    estimate_kind: str
    probability: float | None = None
    raw_score: float | None = None
    calibrated_probability: float | None = None
    expected_value: float | None = None
    interval_lower: float | None = None
    interval_upper: float | None = None

    def __post_init__(self) -> None:
        if not self.estimate_kind or not str(self.estimate_kind).strip():
            raise ValueError("FORECAST_ESTIMATE_KIND_REQUIRED")
        if self.probability is not None:
            validate_probability(self.probability)
        if self.calibrated_probability is not None:
            validate_probability(self.calibrated_probability)
        if self.raw_score is not None:
            validate_finite(self.raw_score, field_name="raw_score")
        if self.expected_value is not None:
            validate_finite(self.expected_value, field_name="expected_value")
        if self.interval_lower is not None:
            validate_finite(self.interval_lower, field_name="interval_lower")
        if self.interval_upper is not None:
            validate_finite(self.interval_upper, field_name="interval_upper")


def validate_schema_version(value: str) -> None:
    if not value or not str(value).strip():
        raise ValueError("SCHEMA_VERSION_REQUIRED")
    major = str(value).split(".", maxsplit=1)[0]
    if major != INTELLIGENCE_SCHEMA_VERSION:
        raise ValueError("SCHEMA_VERSION_MAJOR_MISMATCH")


def validate_id(value: str, *, field_name: str = "id") -> None:
    if value is None:
        raise ValueError(f"{field_name.upper()}_REQUIRED")
    text = str(value)
    if not text or text.strip() != text or not text.strip():
        raise ValueError(f"{field_name.upper()}_INVALID")


def validate_finite(value: float, *, field_name: str = "value") -> None:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name.upper()}_NOT_NUMERIC")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name.upper()}_NOT_FINITE")


def validate_probability(value: float) -> None:
    validate_finite(value, field_name="probability")
    if value < 0.0 or value > 1.0:
        raise ValueError("PROBABILITY_OUT_OF_RANGE")


def validate_support_score(value: float) -> None:
    validate_finite(value, field_name="support_score")
    if value < 0.0 or value > 1.0:
        raise ValueError("SUPPORT_SCORE_OUT_OF_RANGE")


def validate_timestamp_ns(value: int, *, field_name: str = "timestamp_ns") -> None:
    if not isinstance(value, int):
        raise ValueError(f"{field_name.upper()}_NOT_INTEGER")
    if value < 0:
        raise ValueError(f"{field_name.upper()}_NEGATIVE")


def normalize_unique_strings(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        text = str(raw)
        if text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return tuple(ordered)


def normalize_unique_refs(values: tuple[ContractReference, ...] | list[ContractReference]) -> tuple[ContractReference, ...]:
    seen: set[tuple[str, str, str]] = set()
    ordered: list[ContractReference] = []
    for ref in values:
        key = (ref.kind, ref.id, ref.schema_version)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(ref)
    return tuple(ordered)


def new_record_id(prefix: str = "") -> str:
    token = str(uuid.uuid4())
    return f"{prefix}{token}" if prefix else token


def reject_unknown_keys(payload: dict[str, Any], allowed: frozenset[str]) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"UNKNOWN_FIELDS:{','.join(unknown)}")


def quality_summary_to_dict(quality: QualitySummary) -> dict[str, Any]:
    return {
        "state": quality.state.value,
        "flags": list(quality.flags),
    }


def quality_summary_from_dict(payload: dict[str, Any]) -> QualitySummary:
    return QualitySummary(
        state=QualityState(str(payload["state"])),
        flags=tuple(payload.get("flags") or ()),
    )


def contract_reference_to_dict(ref: ContractReference) -> dict[str, Any]:
    return {
        "kind": ref.kind,
        "id": ref.id,
        "schema_version": ref.schema_version,
    }


def contract_reference_from_dict(payload: dict[str, Any]) -> ContractReference:
    return ContractReference(
        kind=str(payload["kind"]),
        id=str(payload["id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
    )


def source_reference_to_dict(ref: SourceReference) -> dict[str, Any]:
    body: dict[str, Any] = {
        "provider_id": ref.provider_id,
        "source_type": ref.source_type,
        "source_record_id": ref.source_record_id,
    }
    if ref.raw_reference is not None:
        body["raw_reference"] = ref.raw_reference
    if ref.external_id is not None:
        body["external_id"] = ref.external_id
    return body


def source_reference_from_dict(payload: dict[str, Any]) -> SourceReference:
    return SourceReference(
        provider_id=str(payload["provider_id"]),
        source_type=str(payload["source_type"]),
        source_record_id=str(payload["source_record_id"]),
        raw_reference=payload.get("raw_reference"),
        external_id=payload.get("external_id"),
    )


def scope_to_dict(scope: IntelligenceScope) -> dict[str, Any]:
    body: dict[str, Any] = {"instrument_ids": list(scope.instrument_ids)}
    if scope.context_id is not None:
        body["context_id"] = scope.context_id
    return body


def scope_from_dict(payload: dict[str, Any]) -> IntelligenceScope:
    return IntelligenceScope(
        instrument_ids=tuple(payload.get("instrument_ids") or ()),
        context_id=payload.get("context_id"),
    )


def time_horizon_to_dict(horizon: TimeHorizonNs) -> dict[str, Any]:
    return {"duration_ns": horizon.duration_ns}


def time_horizon_from_dict(payload: dict[str, Any]) -> TimeHorizonNs:
    return TimeHorizonNs(duration_ns=int(payload["duration_ns"]))


def component_lineage_to_dict(lineage: ComponentLineage) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for key in (
        "component_id",
        "component_version",
        "model_id",
        "model_version",
        "adapter_id",
        "adapter_version",
        "code_revision",
    ):
        value = getattr(lineage, key)
        if value is not None:
            body[key] = value
    return body


def component_lineage_from_dict(payload: dict[str, Any] | None) -> ComponentLineage | None:
    if payload is None:
        return None
    return ComponentLineage(
        component_id=payload.get("component_id"),
        component_version=payload.get("component_version"),
        model_id=payload.get("model_id"),
        model_version=payload.get("model_version"),
        adapter_id=payload.get("adapter_id"),
        adapter_version=payload.get("adapter_version"),
        code_revision=payload.get("code_revision"),
    )


def forecast_target_to_dict(target: ForecastTarget) -> dict[str, Any]:
    return {
        "target_kind": target.target_kind,
        "instrument_id": target.instrument_id,
        "parameters": dict(target.parameters),
    }


def forecast_target_from_dict(payload: dict[str, Any]) -> ForecastTarget:
    return ForecastTarget(
        target_kind=str(payload["target_kind"]),
        instrument_id=str(payload["instrument_id"]),
        parameters=dict(payload.get("parameters") or {}),
    )


def forecast_estimate_to_dict(estimate: ForecastEstimate) -> dict[str, Any]:
    body: dict[str, Any] = {"estimate_kind": estimate.estimate_kind}
    for key in (
        "probability",
        "raw_score",
        "calibrated_probability",
        "expected_value",
        "interval_lower",
        "interval_upper",
    ):
        value = getattr(estimate, key)
        if value is not None:
            body[key] = value
    return body


def forecast_estimate_from_dict(payload: dict[str, Any]) -> ForecastEstimate:
    return ForecastEstimate(
        estimate_kind=str(payload["estimate_kind"]),
        probability=payload.get("probability"),
        raw_score=payload.get("raw_score"),
        calibrated_probability=payload.get("calibrated_probability"),
        expected_value=payload.get("expected_value"),
        interval_lower=payload.get("interval_lower"),
        interval_upper=payload.get("interval_upper"),
    )


def round_trip_contract_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return round_trip_record(payload)


def load_contract_dict_from_json(text: str) -> dict[str, Any]:
    import json

    from ...canonical import _pairs_no_duplicates

    loaded = json.loads(text, object_pairs_hook=_pairs_no_duplicates)
    if not isinstance(loaded, dict):
        raise ValueError("CONTRACT_JSON_MUST_BE_OBJECT")
    return loaded


def dataclass_field_names(cls: type[Any]) -> frozenset[str]:
    return frozenset(field.name for field in fields(cls))


__all__ = [
    "ComponentLineage",
    "ContractKind",
    "ContractReference",
    "Direction",
    "EvidenceApplicability",
    "ForecastEstimate",
    "ForecastTarget",
    "INTELLIGENCE_CONTRACTS_VERSION",
    "INTELLIGENCE_SCHEMA_VERSION",
    "IntelligenceScope",
    "OpportunitySide",
    "OutcomeResolutionStatus",
    "QualityState",
    "QualitySummary",
    "SourceReference",
    "TimeHorizonNs",
    "component_lineage_from_dict",
    "component_lineage_to_dict",
    "contract_reference_from_dict",
    "contract_reference_to_dict",
    "dataclass_field_names",
    "forecast_estimate_from_dict",
    "forecast_estimate_to_dict",
    "forecast_target_from_dict",
    "forecast_target_to_dict",
    "load_contract_dict_from_json",
    "new_record_id",
    "normalize_unique_refs",
    "normalize_unique_strings",
    "quality_summary_from_dict",
    "quality_summary_to_dict",
    "reject_unknown_keys",
    "round_trip_contract_dict",
    "scope_from_dict",
    "scope_to_dict",
    "source_reference_from_dict",
    "source_reference_to_dict",
    "time_horizon_from_dict",
    "time_horizon_to_dict",
    "validate_finite",
    "validate_id",
    "validate_probability",
    "validate_schema_version",
    "validate_support_score",
    "validate_timestamp_ns",
]
