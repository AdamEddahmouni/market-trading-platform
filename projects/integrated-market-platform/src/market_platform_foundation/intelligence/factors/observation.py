"""Point-in-time quantitative factor observation row.

A factor observation is not `symbol, date, score`. Ticker is display metadata.
Fiscal period end is not feature availability. The row is not a forecast,
opportunity, order, or Live/Paper execution grant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    QualityState,
    QualitySummary,
    dataclass_field_names,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    validate_finite,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)
from .construction import FactorConstructionSpecV1
from .errors import FactorContractError
from .families import FactorEvidenceClass, FactorExpressionClass
from .identity import IDENTITY_VERSION, OBSERVATION_ID_PREFIX, factor_hash
from .promotion import assert_research_only, reject_promotion_fields


def observation_identity_payload(
    *,
    schema_version: str,
    security_id: str,
    issuer_id: str,
    as_of_ns: int,
    source_observed_at_ns: int,
    available_time_ns: int,
    feature_id: str,
    feature_version: str,
    construction_spec_id: str,
    raw_input_snapshot_hash: str,
    transform_version: str,
    universe_version: str,
    breakpoint_version: str,
    portfolio_rule_version: str,
    hypothesis_family_id: str,
    export_hash: str,
    evidence_class: FactorEvidenceClass,
    expression_class: FactorExpressionClass,
    value: float | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "identity_version": IDENTITY_VERSION,
        "schema_version": schema_version,
        "security_id": security_id,
        "issuer_id": issuer_id,
        "as_of_ns": as_of_ns,
        "source_observed_at_ns": source_observed_at_ns,
        "available_time_ns": available_time_ns,
        "feature_id": feature_id,
        "feature_version": feature_version,
        "construction_spec_id": construction_spec_id,
        "raw_input_snapshot_hash": raw_input_snapshot_hash,
        "transform_version": transform_version,
        "universe_version": universe_version,
        "breakpoint_version": breakpoint_version,
        "portfolio_rule_version": portfolio_rule_version,
        "hypothesis_family_id": hypothesis_family_id,
        "export_hash": export_hash,
        "evidence_class": evidence_class.value,
        "expression_class": expression_class.value,
        "value": value,
    }
    return body


def derive_observation_id_from_payload(payload: dict[str, Any]) -> str:
    return factor_hash(payload, prefix=OBSERVATION_ID_PREFIX)


@dataclass(frozen=True, slots=True)
class FactorObservationV1:
    """One PIT characteristic row bound to a frozen construction spec."""

    observation_id: str
    schema_version: str
    security_id: str
    issuer_id: str
    as_of_ns: int
    source_observed_at_ns: int
    available_time_ns: int
    feature_id: str
    feature_version: str
    construction_spec_id: str
    raw_input_snapshot_hash: str
    transform_version: str
    universe_version: str
    breakpoint_version: str
    portfolio_rule_version: str
    hypothesis_family_id: str
    export_hash: str
    quality: QualitySummary
    evidence_class: FactorEvidenceClass
    expression_class: FactorExpressionClass
    value: float | None = None
    fiscal_period_end_ns: int | None = None
    display_symbol: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.observation_id, field_name="observation_id")
        validate_schema_version(self.schema_version)
        validate_id(self.security_id, field_name="security_id")
        validate_id(self.issuer_id, field_name="issuer_id")
        validate_timestamp_ns(self.as_of_ns, field_name="as_of_ns")
        validate_timestamp_ns(self.source_observed_at_ns, field_name="source_observed_at_ns")
        validate_timestamp_ns(self.available_time_ns, field_name="available_time_ns")
        validate_id(self.feature_id, field_name="feature_id")
        validate_id(self.construction_spec_id, field_name="construction_spec_id")
        validate_id(self.hypothesis_family_id, field_name="hypothesis_family_id")
        if not self.feature_version or self.feature_version.strip() != self.feature_version:
            raise FactorContractError("FEATURE_VERSION_INVALID")
        if not self.raw_input_snapshot_hash or self.raw_input_snapshot_hash.strip() != self.raw_input_snapshot_hash:
            raise FactorContractError("RAW_INPUT_SNAPSHOT_HASH_INVALID")
        if not self.transform_version or self.transform_version.strip() != self.transform_version:
            raise FactorContractError("TRANSFORM_VERSION_INVALID")
        if not self.universe_version or self.universe_version.strip() != self.universe_version:
            raise FactorContractError("UNIVERSE_VERSION_INVALID")
        if not self.breakpoint_version or self.breakpoint_version.strip() != self.breakpoint_version:
            raise FactorContractError("BREAKPOINT_VERSION_INVALID")
        if not self.portfolio_rule_version or self.portfolio_rule_version.strip() != self.portfolio_rule_version:
            raise FactorContractError("PORTFOLIO_RULE_VERSION_INVALID")
        if not self.export_hash or self.export_hash.strip() != self.export_hash:
            raise FactorContractError("EXPORT_HASH_INVALID")
        if self.display_symbol is not None:
            if not self.display_symbol.strip() or self.display_symbol.strip() != self.display_symbol:
                raise FactorContractError("DISPLAY_SYMBOL_INVALID")
            if self.display_symbol == self.security_id:
                raise FactorContractError("FACTOR_TICKER_IS_NOT_SECURITY_IDENTITY")
        if self.available_time_ns < self.source_observed_at_ns:
            raise FactorContractError("FACTOR_AVAILABLE_BEFORE_SOURCE")
        if self.source_observed_at_ns < self.as_of_ns:
            raise FactorContractError("FACTOR_SOURCE_BEFORE_AS_OF")
        if self.fiscal_period_end_ns is not None:
            validate_timestamp_ns(self.fiscal_period_end_ns, field_name="fiscal_period_end_ns")
            if self.available_time_ns <= self.fiscal_period_end_ns:
                raise FactorContractError("FACTOR_FISCAL_PERIOD_END_IS_NOT_AVAILABILITY")
        if not isinstance(self.evidence_class, FactorEvidenceClass):
            object.__setattr__(self, "evidence_class", FactorEvidenceClass(str(self.evidence_class)))
        if not isinstance(self.expression_class, FactorExpressionClass):
            object.__setattr__(
                self, "expression_class", FactorExpressionClass(str(self.expression_class))
            )
        if self.value is not None:
            validate_finite(self.value, field_name="value")
        elif self.quality.state not in (QualityState.INVALID, QualityState.UNKNOWN, QualityState.DEGRADED):
            raise FactorContractError("FACTOR_MISSING_VALUE_REQUIRES_NON_GOOD_QUALITY")
        if not isinstance(self.metadata, dict):
            raise FactorContractError("FACTOR_METADATA_INVALID")
        reject_promotion_fields(self.metadata)
        expected = derive_observation_id_from_payload(
            observation_identity_payload(
                schema_version=self.schema_version,
                security_id=self.security_id,
                issuer_id=self.issuer_id,
                as_of_ns=self.as_of_ns,
                source_observed_at_ns=self.source_observed_at_ns,
                available_time_ns=self.available_time_ns,
                feature_id=self.feature_id,
                feature_version=self.feature_version,
                construction_spec_id=self.construction_spec_id,
                raw_input_snapshot_hash=self.raw_input_snapshot_hash,
                transform_version=self.transform_version,
                universe_version=self.universe_version,
                breakpoint_version=self.breakpoint_version,
                portfolio_rule_version=self.portfolio_rule_version,
                hypothesis_family_id=self.hypothesis_family_id,
                export_hash=self.export_hash,
                evidence_class=self.evidence_class,
                expression_class=self.expression_class,
                value=self.value,
            )
        )
        if self.observation_id != expected:
            raise FactorContractError("FACTOR_OBSERVATION_IDENTITY_MISMATCH")
        assert_research_only()


def build_factor_observation(
    *,
    spec: FactorConstructionSpecV1,
    security_id: str,
    issuer_id: str,
    as_of_ns: int,
    source_observed_at_ns: int,
    available_time_ns: int,
    raw_input_snapshot_hash: str,
    export_hash: str,
    quality: QualitySummary,
    evidence_class: FactorEvidenceClass,
    expression_class: FactorExpressionClass = FactorExpressionClass.CHARACTERISTIC,
    value: float | None = None,
    fiscal_period_end_ns: int | None = None,
    display_symbol: str | None = None,
    metadata: dict[str, Any] | None = None,
    schema_version: str = INTELLIGENCE_SCHEMA_VERSION,
) -> FactorObservationV1:
    if spec.feature_id is None:
        raise FactorContractError("FACTOR_FEATURE_ID_REQUIRED")
    payload = observation_identity_payload(
        schema_version=schema_version,
        security_id=security_id,
        issuer_id=issuer_id,
        as_of_ns=as_of_ns,
        source_observed_at_ns=source_observed_at_ns,
        available_time_ns=available_time_ns,
        feature_id=spec.feature_id,
        feature_version=spec.feature_version,
        construction_spec_id=spec.spec_id,
        raw_input_snapshot_hash=raw_input_snapshot_hash,
        transform_version=spec.code_version,
        universe_version=spec.universe_version,
        breakpoint_version=spec.breakpoint_version,
        portfolio_rule_version=spec.portfolio_rule_version,
        hypothesis_family_id=spec.hypothesis_family_id,
        export_hash=export_hash,
        evidence_class=evidence_class,
        expression_class=expression_class,
        value=value,
    )
    if spec.hypothesis_family_id != payload["hypothesis_family_id"]:
        raise FactorContractError("FACTOR_HYPOTHESIS_FAMILY_MISMATCH")
    return FactorObservationV1(
        observation_id=derive_observation_id_from_payload(payload),
        schema_version=schema_version,
        security_id=security_id,
        issuer_id=issuer_id,
        as_of_ns=as_of_ns,
        source_observed_at_ns=source_observed_at_ns,
        available_time_ns=available_time_ns,
        feature_id=spec.feature_id,
        feature_version=spec.feature_version,
        construction_spec_id=spec.spec_id,
        raw_input_snapshot_hash=raw_input_snapshot_hash,
        transform_version=spec.code_version,
        universe_version=spec.universe_version,
        breakpoint_version=spec.breakpoint_version,
        portfolio_rule_version=spec.portfolio_rule_version,
        hypothesis_family_id=spec.hypothesis_family_id,
        export_hash=export_hash,
        quality=quality,
        evidence_class=evidence_class,
        expression_class=expression_class,
        value=value,
        fiscal_period_end_ns=fiscal_period_end_ns,
        display_symbol=display_symbol,
        metadata=dict(metadata or {}),
    )


_OBS_ALLOWED = dataclass_field_names(FactorObservationV1)


def factor_observation_to_dict(record: FactorObservationV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "observation_id": record.observation_id,
        "schema_version": record.schema_version,
        "security_id": record.security_id,
        "issuer_id": record.issuer_id,
        "as_of_ns": record.as_of_ns,
        "source_observed_at_ns": record.source_observed_at_ns,
        "available_time_ns": record.available_time_ns,
        "feature_id": record.feature_id,
        "feature_version": record.feature_version,
        "construction_spec_id": record.construction_spec_id,
        "raw_input_snapshot_hash": record.raw_input_snapshot_hash,
        "transform_version": record.transform_version,
        "universe_version": record.universe_version,
        "breakpoint_version": record.breakpoint_version,
        "portfolio_rule_version": record.portfolio_rule_version,
        "hypothesis_family_id": record.hypothesis_family_id,
        "export_hash": record.export_hash,
        "quality": quality_summary_to_dict(record.quality),
        "evidence_class": record.evidence_class.value,
        "expression_class": record.expression_class.value,
    }
    if record.value is not None:
        body["value"] = record.value
    if record.fiscal_period_end_ns is not None:
        body["fiscal_period_end_ns"] = record.fiscal_period_end_ns
    if record.display_symbol is not None:
        body["display_symbol"] = record.display_symbol
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def factor_observation_from_dict(payload: dict[str, Any]) -> FactorObservationV1:
    reject_unknown_keys(payload, _OBS_ALLOWED)
    return FactorObservationV1(
        observation_id=str(payload["observation_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        security_id=str(payload["security_id"]),
        issuer_id=str(payload["issuer_id"]),
        as_of_ns=int(payload["as_of_ns"]),
        source_observed_at_ns=int(payload["source_observed_at_ns"]),
        available_time_ns=int(payload["available_time_ns"]),
        feature_id=str(payload["feature_id"]),
        feature_version=str(payload["feature_version"]),
        construction_spec_id=str(payload["construction_spec_id"]),
        raw_input_snapshot_hash=str(payload["raw_input_snapshot_hash"]),
        transform_version=str(payload["transform_version"]),
        universe_version=str(payload["universe_version"]),
        breakpoint_version=str(payload["breakpoint_version"]),
        portfolio_rule_version=str(payload["portfolio_rule_version"]),
        hypothesis_family_id=str(payload["hypothesis_family_id"]),
        export_hash=str(payload["export_hash"]),
        quality=quality_summary_from_dict(payload["quality"]),
        evidence_class=FactorEvidenceClass(str(payload["evidence_class"])),
        expression_class=FactorExpressionClass(str(payload["expression_class"])),
        value=(None if payload.get("value") is None else float(payload["value"])),
        fiscal_period_end_ns=(
            None if payload.get("fiscal_period_end_ns") is None else int(payload["fiscal_period_end_ns"])
        ),
        display_symbol=payload.get("display_symbol"),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "FactorObservationV1",
    "build_factor_observation",
    "derive_observation_id_from_payload",
    "factor_observation_from_dict",
    "factor_observation_to_dict",
    "observation_identity_payload",
]
