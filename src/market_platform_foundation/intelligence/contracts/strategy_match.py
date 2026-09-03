"""Immutable strategy evaluation results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..quality.models import AvailabilityState
from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    IntelligenceScope,
    QualityState,
    QualitySummary,
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
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


class StrategyMatchDisposition(StrEnum):
    """The outcome of evaluating one strategy against one market situation."""

    MATCHED = "MATCHED"
    REJECTED = "REJECTED"
    ABSTAINED = "ABSTAINED"
    UNAVAILABLE = "UNAVAILABLE"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class StrategyConditionResult:
    """Immutable result for one named strategy condition."""

    condition_id: str
    matched: bool
    observed_value: Any = None
    expected_value: Any = None
    reason: str | None = None

    def __post_init__(self) -> None:
        validate_id(self.condition_id, field_name="condition_id")
        if not isinstance(self.matched, bool):
            raise ValueError("CONDITION_MATCHED_MUST_BE_BOOLEAN")
        object.__setattr__(self, "observed_value", _freeze(self.observed_value))
        object.__setattr__(self, "expected_value", _freeze(self.expected_value))
        if self.reason is not None and not str(self.reason).strip():
            raise ValueError("CONDITION_REASON_INVALID")


@dataclass(frozen=True, slots=True)
class StrategyMatch:
    """Decision-time strategy evaluation, including non-selection outcomes.

    This is an immutable evaluation record. It is not a signal, forecast,
    opportunity, order, or lifecycle transition.
    """

    match_id: str
    strategy_id: str
    strategy_identity_hash: str
    schema_version: str
    scope: IntelligenceScope
    decision_time_ns: int
    disposition: StrategyMatchDisposition
    capability_state: AvailabilityState
    quality: QualitySummary
    source_snapshot_ref: ContractReference | None = None
    source_evidence_refs: tuple[ContractReference, ...] = ()
    source_signal_refs: tuple[ContractReference, ...] = ()
    condition_results: tuple[StrategyConditionResult, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    abstention_reasons: tuple[str, ...] = ()
    unavailability_reasons: tuple[str, ...] = ()
    regime: str | None = None
    context: Mapping[str, Any] = field(default_factory=dict)
    source_forecast_refs: tuple[ContractReference, ...] = ()
    valid_from_ns: int | None = None
    expires_at_ns: int | None = None
    lineage_refs: tuple[ContractReference, ...] = ()
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        validate_id(self.match_id, field_name="match_id")
        validate_id(self.strategy_id, field_name="strategy_id")
        validate_id(self.strategy_identity_hash, field_name="strategy_identity_hash")
        validate_schema_version(self.schema_version)
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        if not isinstance(self.disposition, StrategyMatchDisposition):
            object.__setattr__(
                self,
                "disposition",
                StrategyMatchDisposition(str(self.disposition)),
            )
        if not isinstance(self.capability_state, AvailabilityState):
            object.__setattr__(
                self,
                "capability_state",
                AvailabilityState(str(self.capability_state)),
            )
        if self.source_snapshot_ref is not None and not isinstance(
            self.source_snapshot_ref, ContractReference
        ):
            object.__setattr__(
                self,
                "source_snapshot_ref",
                contract_reference_from_dict(self.source_snapshot_ref),
            )
        object.__setattr__(
            self,
            "scope",
            IntelligenceScope(
                instrument_ids=tuple(sorted(self.scope.instrument_ids)),
                context_id=self.scope.context_id,
            ),
        )
        object.__setattr__(self, "source_evidence_refs", _normalize_refs(self.source_evidence_refs))
        object.__setattr__(self, "source_signal_refs", _normalize_refs(self.source_signal_refs))
        object.__setattr__(self, "source_forecast_refs", _normalize_refs(self.source_forecast_refs))
        object.__setattr__(self, "lineage_refs", _normalize_refs(self.lineage_refs))
        object.__setattr__(
            self,
            "condition_results",
            _normalize_condition_results(self.condition_results),
        )
        object.__setattr__(
            self,
            "rejection_reasons",
            _normalize_reasons(self.rejection_reasons),
        )
        object.__setattr__(
            self,
            "abstention_reasons",
            _normalize_reasons(self.abstention_reasons),
        )
        object.__setattr__(
            self,
            "unavailability_reasons",
            _normalize_reasons(self.unavailability_reasons),
        )
        object.__setattr__(self, "context", _freeze_mapping(self.context))
        if self.regime is not None and not str(self.regime).strip():
            raise ValueError("REGIME_INVALID")
        if self.correlation_id is not None:
            validate_id(self.correlation_id, field_name="correlation_id")
        if self.valid_from_ns is not None:
            validate_timestamp_ns(self.valid_from_ns, field_name="valid_from_ns")
        if self.expires_at_ns is not None:
            validate_timestamp_ns(self.expires_at_ns, field_name="expires_at_ns")
        if (
            self.valid_from_ns is not None
            and self.expires_at_ns is not None
            and self.expires_at_ns <= self.valid_from_ns
        ):
            raise ValueError("MATCH_VALIDITY_WINDOW_INVALID")
        if self.expires_at_ns is not None and self.expires_at_ns < self.decision_time_ns:
            if self.disposition != StrategyMatchDisposition.EXPIRED:
                raise ValueError("MATCH_EXPIRED_DISPOSITION_REQUIRED")
        _validate_disposition_reasons(self)

    @classmethod
    def create(
        cls,
        *,
        strategy_id: str,
        strategy_identity_hash: str,
        scope: IntelligenceScope,
        decision_time_ns: int,
        disposition: StrategyMatchDisposition,
        capability_state: AvailabilityState,
        quality: QualitySummary,
        schema_version: str = INTELLIGENCE_SCHEMA_VERSION,
        match_id: str | None = None,
        source_snapshot_ref: ContractReference | None = None,
        source_evidence_refs: tuple[ContractReference, ...] = (),
        source_signal_refs: tuple[ContractReference, ...] = (),
        condition_results: tuple[StrategyConditionResult, ...] = (),
        rejection_reasons: tuple[str, ...] = (),
        abstention_reasons: tuple[str, ...] = (),
        unavailability_reasons: tuple[str, ...] = (),
        regime: str | None = None,
        context: Mapping[str, Any] | None = None,
        source_forecast_refs: tuple[ContractReference, ...] = (),
        valid_from_ns: int | None = None,
        expires_at_ns: int | None = None,
        lineage_refs: tuple[ContractReference, ...] = (),
        correlation_id: str | None = None,
    ) -> "StrategyMatch":
        """Construct a match, deriving its ID unless the caller supplies one."""
        record = cls(
            match_id=match_id or "SM-PENDING",
            strategy_id=strategy_id,
            strategy_identity_hash=strategy_identity_hash,
            schema_version=schema_version,
            scope=scope,
            decision_time_ns=decision_time_ns,
            disposition=disposition,
            capability_state=capability_state,
            quality=quality,
            source_snapshot_ref=source_snapshot_ref,
            source_evidence_refs=source_evidence_refs,
            source_signal_refs=source_signal_refs,
            condition_results=condition_results,
            rejection_reasons=rejection_reasons,
            abstention_reasons=abstention_reasons,
            unavailability_reasons=unavailability_reasons,
            regime=regime,
            context=context or {},
            source_forecast_refs=source_forecast_refs,
            valid_from_ns=valid_from_ns,
            expires_at_ns=expires_at_ns,
            lineage_refs=lineage_refs,
            correlation_id=correlation_id,
        )
        if match_id is None:
            object.__setattr__(record, "match_id", f"SM-{record.match_identity_hash}")
        return record

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StrategyMatch":
        return strategy_match_from_dict(payload)

    @property
    def match_identity_hash(self) -> str:
        return strategy_match_identity_hash(self)

    @property
    def identity_hash(self) -> str:
        return self.match_identity_hash

    @property
    def strategy_hash(self) -> str:
        return self.strategy_identity_hash

    @property
    def quality_state(self) -> QualityState:
        return self.quality.state

    @property
    def conditions(self) -> tuple[StrategyConditionResult, ...]:
        return self.condition_results

    @property
    def matched_results(self) -> tuple[StrategyConditionResult, ...]:
        return tuple(result for result in self.condition_results if result.matched)

    @property
    def failed_results(self) -> tuple[StrategyConditionResult, ...]:
        return tuple(result for result in self.condition_results if not result.matched)

    @property
    def matched_conditions(self) -> tuple[str, ...]:
        return tuple(result.condition_id for result in self.matched_results)

    @property
    def failed_conditions(self) -> tuple[str, ...]:
        return tuple(result.condition_id for result in self.failed_results)

    @property
    def forecast_refs(self) -> tuple[ContractReference, ...]:
        return self.source_forecast_refs

    @property
    def source_snapshot_refs(self) -> tuple[ContractReference, ...]:
        return (self.source_snapshot_ref,) if self.source_snapshot_ref is not None else ()

    @property
    def valid_until_ns(self) -> int | None:
        return self.expires_at_ns

    def is_expired(self, at_time_ns: int) -> bool:
        """Return whether the match is outside its explicit expiry boundary."""
        validate_timestamp_ns(at_time_ns, field_name="at_time_ns")
        return self.expires_at_ns is not None and at_time_ns >= self.expires_at_ns

    def is_valid_at(self, at_time_ns: int) -> bool:
        """Return whether the match is usable at a point in time."""
        validate_timestamp_ns(at_time_ns, field_name="at_time_ns")
        if self.disposition == StrategyMatchDisposition.EXPIRED:
            return False
        if self.valid_from_ns is not None and at_time_ns < self.valid_from_ns:
            return False
        return not self.is_expired(at_time_ns)


_STRATEGY_MATCH_ALLOWED = dataclass_field_names(StrategyMatch) | {"match_identity_hash"}
_CONDITION_RESULT_ALLOWED = dataclass_field_names(StrategyConditionResult)


def strategy_condition_result_to_dict(result: StrategyConditionResult) -> dict[str, Any]:
    body: dict[str, Any] = {
        "condition_id": result.condition_id,
        "matched": result.matched,
    }
    if result.observed_value is not None:
        body["observed_value"] = _thaw(result.observed_value)
    if result.expected_value is not None:
        body["expected_value"] = _thaw(result.expected_value)
    if result.reason is not None:
        body["reason"] = result.reason
    return body


def strategy_condition_result_from_dict(payload: dict[str, Any]) -> StrategyConditionResult:
    reject_unknown_keys(payload, _CONDITION_RESULT_ALLOWED)
    return StrategyConditionResult(
        condition_id=str(payload["condition_id"]),
        matched=payload["matched"],
        observed_value=payload.get("observed_value"),
        expected_value=payload.get("expected_value"),
        reason=payload.get("reason"),
    )


def strategy_match_to_dict(record: StrategyMatch) -> dict[str, Any]:
    body = _strategy_match_body_without_identity(record)
    body["match_identity_hash"] = strategy_match_identity_hash(record)
    return body


def _strategy_match_body_without_identity(record: StrategyMatch) -> dict[str, Any]:
    body: dict[str, Any] = {
        "match_id": record.match_id,
        "strategy_id": record.strategy_id,
        "strategy_identity_hash": record.strategy_identity_hash,
        "schema_version": record.schema_version,
        "scope": scope_to_dict(record.scope),
        "decision_time_ns": record.decision_time_ns,
        "disposition": record.disposition.value,
        "capability_state": record.capability_state.value,
        "quality": quality_summary_to_dict(record.quality),
        "condition_results": [
            strategy_condition_result_to_dict(result) for result in record.condition_results
        ],
    }
    if record.source_snapshot_ref is not None:
        body["source_snapshot_ref"] = contract_reference_to_dict(record.source_snapshot_ref)
    if record.source_evidence_refs:
        body["source_evidence_refs"] = [
            contract_reference_to_dict(ref) for ref in record.source_evidence_refs
        ]
    if record.source_signal_refs:
        body["source_signal_refs"] = [
            contract_reference_to_dict(ref) for ref in record.source_signal_refs
        ]
    for field_name in ("rejection_reasons", "abstention_reasons", "unavailability_reasons"):
        values = getattr(record, field_name)
        if values:
            body[field_name] = list(values)
    if record.regime is not None:
        body["regime"] = record.regime
    if record.context:
        body["context"] = _thaw(record.context)
    if record.source_forecast_refs:
        body["source_forecast_refs"] = [
            contract_reference_to_dict(ref) for ref in record.source_forecast_refs
        ]
    if record.valid_from_ns is not None:
        body["valid_from_ns"] = record.valid_from_ns
    if record.expires_at_ns is not None:
        body["expires_at_ns"] = record.expires_at_ns
    if record.lineage_refs:
        body["lineage_refs"] = [contract_reference_to_dict(ref) for ref in record.lineage_refs]
    if record.correlation_id is not None:
        body["correlation_id"] = record.correlation_id
    return body


def strategy_match_from_dict(payload: dict[str, Any]) -> StrategyMatch:
    reject_unknown_keys(payload, _STRATEGY_MATCH_ALLOWED)
    record = StrategyMatch(
        match_id=str(payload["match_id"]),
        strategy_id=str(payload["strategy_id"]),
        strategy_identity_hash=str(payload["strategy_identity_hash"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        scope=scope_from_dict(payload["scope"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        disposition=StrategyMatchDisposition(str(payload["disposition"])),
        capability_state=AvailabilityState(
            str(payload.get("capability_state", AvailabilityState.UNKNOWN))
        ),
        quality=quality_summary_from_dict(payload["quality"]),
        source_snapshot_ref=(
            contract_reference_from_dict(payload["source_snapshot_ref"])
            if payload.get("source_snapshot_ref") is not None
            else None
        ),
        source_evidence_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_evidence_refs") or [])
        ),
        source_signal_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_signal_refs") or [])
        ),
        condition_results=tuple(
            strategy_condition_result_from_dict(item)
            for item in (payload.get("condition_results") or [])
        ),
        rejection_reasons=tuple(payload.get("rejection_reasons") or ()),
        abstention_reasons=tuple(payload.get("abstention_reasons") or ()),
        unavailability_reasons=tuple(payload.get("unavailability_reasons") or ()),
        regime=payload.get("regime"),
        context=payload.get("context") or {},
        source_forecast_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_forecast_refs") or [])
        ),
        valid_from_ns=payload.get("valid_from_ns"),
        expires_at_ns=payload.get("expires_at_ns"),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        correlation_id=payload.get("correlation_id"),
    )
    serialized_identity_hash = payload.get("match_identity_hash")
    if serialized_identity_hash is not None and serialized_identity_hash != record.match_identity_hash:
        raise ValueError("MATCH_IDENTITY_HASH_MISMATCH")
    return record


def strategy_match_identity_hash(record: StrategyMatch) -> str:
    body = _strategy_match_body_without_identity(record)
    body.pop("match_id", None)
    return sha256_bytes(canonical_bytes(body))


def strategy_match_canonical_bytes(record: StrategyMatch) -> bytes:
    return canonical_bytes(strategy_match_to_dict(record))


def _validate_disposition_reasons(record: StrategyMatch) -> None:
    required = {
        StrategyMatchDisposition.REJECTED: record.rejection_reasons,
        StrategyMatchDisposition.ABSTAINED: record.abstention_reasons,
        StrategyMatchDisposition.UNAVAILABLE: record.unavailability_reasons,
    }.get(record.disposition)
    if required is not None and not required:
        raise ValueError(f"{record.disposition.value}_REASON_REQUIRED")
    if record.disposition == StrategyMatchDisposition.EXPIRED and record.expires_at_ns is None:
        raise ValueError("EXPIRED_AT_REQUIRED")


def _normalize_refs(
    values: tuple[ContractReference, ...] | list[ContractReference],
) -> tuple[ContractReference, ...]:
    normalized = normalize_unique_refs(values)
    return tuple(sorted(normalized, key=lambda ref: (ref.kind, ref.id, ref.schema_version)))


def _normalize_condition_results(
    values: tuple[StrategyConditionResult, ...] | list[StrategyConditionResult],
) -> tuple[StrategyConditionResult, ...]:
    normalized = tuple(
        value
        if isinstance(value, StrategyConditionResult)
        else strategy_condition_result_from_dict(value)
        for value in values
    )
    by_id = {value.condition_id: value for value in normalized}
    if len(by_id) != len(normalized):
        raise ValueError("DUPLICATE_CONDITION_ID")
    return tuple(sorted(normalized, key=lambda value: value.condition_id))


def _normalize_reasons(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized = normalize_unique_strings(values)
    if any(not value.strip() for value in normalized):
        raise ValueError("MATCH_REASON_INVALID")
    return tuple(sorted(normalized))


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


def _freeze_mapping(value: Mapping[str, Any]) -> MappingProxyType:
    if not isinstance(value, Mapping):
        raise ValueError("MATCH_CONTEXT_INVALID")
    return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


__all__ = [
    "StrategyConditionResult",
    "StrategyMatch",
    "StrategyMatchDisposition",
    "strategy_condition_result_from_dict",
    "strategy_condition_result_to_dict",
    "strategy_match_canonical_bytes",
    "strategy_match_from_dict",
    "strategy_match_identity_hash",
    "strategy_match_to_dict",
]
