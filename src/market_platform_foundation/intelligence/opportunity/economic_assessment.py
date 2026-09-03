"""Typed universal economic-assessment sidecar for OpportunityV1."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    IntelligenceScope,
    contract_reference_from_dict,
    contract_reference_to_dict,
    normalize_unique_refs,
    scope_from_dict,
    scope_to_dict,
    validate_finite,
    validate_id,
    validate_probability,
    validate_schema_version,
    validate_timestamp_ns,
)

ECONOMIC_ASSESSMENT_IMPLEMENTATION_VERSION = "universal-economic-assessment-v1"
MONEY_UNIT = "minor_units"
NANOSECOND_UNIT = "ns"
BPS_UNIT = "bps"
PROBABILITY_UNIT = "probability"
SEMANTIC_UNITS = {
    "money": MONEY_UNIT,
    "time": NANOSECOND_UNIT,
    "rate": BPS_UNIT,
    "probability": PROBABILITY_UNIT,
}


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(v) for v in value))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class MoneyMinorUnits:
    """Money represented as integer minor units with explicit currency/scale."""

    amount_minor: int
    currency: str
    scale: int

    def __post_init__(self) -> None:
        if isinstance(self.amount_minor, bool) or not isinstance(self.amount_minor, int):
            raise ValueError("MONEY_MINOR_UNITS_MUST_BE_INTEGER")
        currency = str(self.currency).strip().upper()
        if len(currency) != 3:
            raise ValueError("MONEY_CURRENCY_INVALID")
        if isinstance(self.scale, bool) or not isinstance(self.scale, int) or self.scale < 0:
            raise ValueError("MONEY_SCALE_INVALID")
        object.__setattr__(self, "currency", currency)


@dataclass(frozen=True, slots=True)
class EconomicAssumptionsV1:
    """Versioned assumptions identity used by an economic assessment."""

    assumptions_id: str
    version: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.assumptions_id, field_name="assumptions_id")
        if not str(self.version).strip():
            raise ValueError("ASSUMPTIONS_VERSION_REQUIRED")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("ASSUMPTIONS_METADATA_INVALID")
        object.__setattr__(self, "metadata", _freeze(self.metadata))


class AccountActionability(StrEnum):
    ACTIONABLE = "ACTIONABLE"
    NOT_ACTIONABLE = "NOT_ACTIONABLE"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class LiquidityState(StrEnum):
    AVAILABLE = "AVAILABLE"
    CONSTRAINED = "CONSTRAINED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class LiquidityCapacityV1:
    """Explicit liquidity state and capacity quantity, never a universal score."""

    state: LiquidityState
    capacity_quantity: float | None = None
    capacity_unit: str | None = None
    source_ref: ContractReference | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, LiquidityState):
            object.__setattr__(self, "state", LiquidityState(str(self.state)))
        if self.capacity_quantity is not None:
            validate_finite(self.capacity_quantity, field_name="capacity_quantity")
            if self.capacity_quantity < 0:
                raise ValueError("CAPACITY_QUANTITY_NEGATIVE")
        if self.capacity_quantity is not None and not str(self.capacity_unit or "").strip():
            raise ValueError("CAPACITY_UNIT_REQUIRED")
        if self.source_ref is not None and not isinstance(self.source_ref, ContractReference):
            object.__setattr__(self, "source_ref", contract_reference_from_dict(self.source_ref))


@dataclass(frozen=True, slots=True)
class EconomicUncertaintyV1:
    """Uncertainty interval with explicit P&L and probability semantics."""

    net_pnl_lower: MoneyMinorUnits | None = None
    net_pnl_upper: MoneyMinorUnits | None = None
    confidence_probability: float | None = None
    method: str = "UNSPECIFIED"

    def __post_init__(self) -> None:
        if self.confidence_probability is not None:
            validate_probability(self.confidence_probability)
        if not str(self.method).strip():
            raise ValueError("UNCERTAINTY_METHOD_REQUIRED")


@dataclass(frozen=True, slots=True)
class FactorExposureV1:
    """One named factor exposure with explicit loading and money exposure."""

    factor_id: str
    correlation_coefficient: float | None = None
    loading_bps: float | None = None
    exposure: MoneyMinorUnits | None = None

    def __post_init__(self) -> None:
        validate_id(self.factor_id, field_name="factor_id")
        if self.correlation_coefficient is not None:
            validate_finite(self.correlation_coefficient, field_name="correlation_coefficient")
            if not -1.0 <= self.correlation_coefficient <= 1.0:
                raise ValueError("CORRELATION_COEFFICIENT_OUT_OF_RANGE")
        if self.loading_bps is not None:
            validate_finite(self.loading_bps, field_name="loading_bps")


@dataclass(frozen=True, slots=True)
class UniversalEconomicAssessmentV1:
    """Immutable, dimension-preserving economic assessment sidecar."""

    assessment_id: str
    schema_version: str
    scope: IntelligenceScope
    account_id: str
    mode: str
    assessed_at_ns: int
    assumptions: EconomicAssumptionsV1
    expected_gross_pnl: MoneyMinorUnits | None = None
    expected_net_pnl: MoneyMinorUnits | None = None
    expected_return_bps: float | None = None
    capital_required: MoneyMinorUnits | None = None
    buying_power_required: MoneyMinorUnits | None = None
    initial_margin_required: MoneyMinorUnits | None = None
    maintenance_margin_required: MoneyMinorUnits | None = None
    maximum_loss: MoneyMinorUnits | None = None
    tail_loss: MoneyMinorUnits | None = None
    loss_probability: float | None = None
    expected_hold_ns: int | None = None
    maximum_hold_ns: int | None = None
    capital_lock_ns: int | None = None
    expires_at_ns: int | None = None
    spread_bps: float | None = None
    slippage_bps: float | None = None
    fees_bps: float | None = None
    borrow_bps: float | None = None
    roll_bps: float | None = None
    funding_bps: float | None = None
    fill_probability: float | None = None
    adverse_selection_probability: float | None = None
    liquidity: LiquidityCapacityV1 | None = None
    uncertainty: EconomicUncertaintyV1 | None = None
    factor_exposures: tuple[FactorExposureV1, ...] = ()
    account_actionability: AccountActionability = AccountActionability.UNKNOWN
    source_refs: tuple[ContractReference, ...] = ()
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    implementation_version: str = ECONOMIC_ASSESSMENT_IMPLEMENTATION_VERSION

    def __post_init__(self) -> None:
        validate_id(self.assessment_id, field_name="assessment_id")
        validate_schema_version(self.schema_version)
        validate_id(self.account_id, field_name="account_id")
        if not str(self.mode).strip():
            raise ValueError("ECONOMIC_MODE_REQUIRED")
        validate_timestamp_ns(self.assessed_at_ns, field_name="assessed_at_ns")
        if not isinstance(self.assumptions, EconomicAssumptionsV1):
            raise ValueError("ECONOMIC_ASSUMPTIONS_REQUIRED")
        for field_name in (
            "expected_return_bps",
            "spread_bps",
            "slippage_bps",
            "fees_bps",
            "borrow_bps",
            "roll_bps",
            "funding_bps",
        ):
            value = getattr(self, field_name)
            if value is not None:
                validate_finite(value, field_name=field_name)
        for field_name in ("loss_probability", "fill_probability", "adverse_selection_probability"):
            value = getattr(self, field_name)
            if value is not None:
                validate_probability(value)
        for field_name in ("expected_hold_ns", "maximum_hold_ns", "capital_lock_ns", "expires_at_ns"):
            value = getattr(self, field_name)
            if value is not None:
                validate_timestamp_ns(value, field_name=field_name)
        if self.expected_hold_ns is not None and self.maximum_hold_ns is not None:
            if self.expected_hold_ns > self.maximum_hold_ns:
                raise ValueError("HOLD_WINDOW_INVALID")
        if self.expires_at_ns is not None and self.expires_at_ns <= self.assessed_at_ns:
            raise ValueError("ECONOMIC_EXPIRY_INVALID")
        monies = tuple(
            value
            for value in (
                self.expected_gross_pnl,
                self.expected_net_pnl,
                self.capital_required,
                self.buying_power_required,
                self.initial_margin_required,
                self.maintenance_margin_required,
                self.maximum_loss,
                self.tail_loss,
            )
            if value is not None
        )
        nested_monies = []
        if self.uncertainty is not None:
            nested_monies.extend(
                value
                for value in (self.uncertainty.net_pnl_lower, self.uncertainty.net_pnl_upper)
                if value is not None
            )
        nested_monies.extend(
            exposure.exposure
            for exposure in self.factor_exposures
            if exposure.exposure is not None
        )
        monies += tuple(nested_monies)
        if any(not isinstance(value, MoneyMinorUnits) for value in monies):
            raise ValueError("MONEY_VALUE_TYPE_INVALID")
        if monies:
            currency_scale = {(value.currency, value.scale) for value in monies}
            if len(currency_scale) != 1:
                raise ValueError("MONEY_CURRENCY_SCALE_MISMATCH")
        if not isinstance(self.account_actionability, AccountActionability):
            object.__setattr__(
                self,
                "account_actionability",
                AccountActionability(str(self.account_actionability)),
            )
        object.__setattr__(self, "source_refs", _normalize_refs(self.source_refs))
        object.__setattr__(self, "lineage_refs", _normalize_refs(self.lineage_refs))
        object.__setattr__(
            self,
            "factor_exposures",
            tuple(sorted(self.factor_exposures, key=lambda item: item.factor_id)),
        )
        if not isinstance(self.metadata, Mapping):
            raise ValueError("ECONOMIC_METADATA_INVALID")
        if any(
            key in {"universal_score", "opaque_score", "economic_score"}
            for key in self.metadata
        ):
            raise ValueError("OPAQUE_ECONOMIC_SCORE_FORBIDDEN")
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    @classmethod
    def create(cls, *, scope: IntelligenceScope, account_id: str, mode: str, assessed_at_ns: int,
               assumptions: EconomicAssumptionsV1, **kwargs: Any) -> "UniversalEconomicAssessmentV1":
        record = cls(
            assessment_id="UEA-PENDING",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            scope=scope,
            account_id=account_id,
            mode=mode,
            assessed_at_ns=assessed_at_ns,
            assumptions=assumptions,
            **kwargs,
        )
        object.__setattr__(record, "assessment_id", f"UEA-{economic_assessment_identity_hash(record)}")
        return record

    @property
    def assumptions_version(self) -> str:
        return self.assumptions.version

    @property
    def currency(self) -> str | None:
        money = self.expected_net_pnl or self.expected_gross_pnl
        return money.currency if money is not None else None

    @property
    def scale(self) -> int | None:
        money = self.expected_net_pnl or self.expected_gross_pnl
        return money.scale if money is not None else None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UniversalEconomicAssessmentV1":
        return economic_assessment_v1_from_dict(payload)


def _normalize_refs(values: tuple[ContractReference, ...] | list[ContractReference]) -> tuple[ContractReference, ...]:
    refs = normalize_unique_refs(values)
    return tuple(sorted(refs, key=lambda ref: (ref.kind, ref.id, ref.schema_version)))


def _money_to_dict(value: MoneyMinorUnits | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "amount_minor": value.amount_minor,
        "currency": value.currency,
        "scale": value.scale,
        "unit": MONEY_UNIT,
    }


def _money_from_dict(value: dict[str, Any] | None) -> MoneyMinorUnits | None:
    if value is None:
        return None
    if value.get("unit") != MONEY_UNIT:
        raise ValueError("MONEY_UNIT_INVALID")
    amount_minor = value.get("amount_minor")
    scale = value.get("scale")
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
        raise ValueError("MONEY_MINOR_UNITS_MUST_BE_INTEGER")
    if isinstance(scale, bool) or not isinstance(scale, int):
        raise ValueError("MONEY_SCALE_INVALID")
    return MoneyMinorUnits(amount_minor, str(value["currency"]), scale)


def _assumptions_to_dict(value: EconomicAssumptionsV1) -> dict[str, Any]:
    return {
        "assumptions_id": value.assumptions_id,
        "version": value.version,
        "metadata": _thaw(value.metadata),
    }


def _assumptions_from_dict(value: dict[str, Any]) -> EconomicAssumptionsV1:
    return EconomicAssumptionsV1(
        assumptions_id=str(value["assumptions_id"]),
        version=str(value["version"]),
        metadata=value.get("metadata") or {},
    )


def _liquidity_to_dict(value: LiquidityCapacityV1 | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "state": value.state.value,
        "capacity_quantity": value.capacity_quantity,
        "capacity_unit": value.capacity_unit,
        "source_ref": contract_reference_to_dict(value.source_ref) if value.source_ref else None,
    }


def _liquidity_from_dict(value: dict[str, Any] | None) -> LiquidityCapacityV1 | None:
    if value is None:
        return None
    return LiquidityCapacityV1(
        state=LiquidityState(str(value["state"])),
        capacity_quantity=value.get("capacity_quantity"),
        capacity_unit=value.get("capacity_unit"),
        source_ref=contract_reference_from_dict(value["source_ref"]) if value.get("source_ref") else None,
    )


def _uncertainty_to_dict(value: EconomicUncertaintyV1 | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "net_pnl_lower": _money_to_dict(value.net_pnl_lower),
        "net_pnl_upper": _money_to_dict(value.net_pnl_upper),
        "confidence_probability": value.confidence_probability,
        "method": value.method,
    }


def _uncertainty_from_dict(value: dict[str, Any] | None) -> EconomicUncertaintyV1 | None:
    if value is None:
        return None
    return EconomicUncertaintyV1(
        net_pnl_lower=_money_from_dict(value.get("net_pnl_lower")),
        net_pnl_upper=_money_from_dict(value.get("net_pnl_upper")),
        confidence_probability=value.get("confidence_probability"),
        method=str(value.get("method", "UNSPECIFIED")),
    )


def _factor_to_dict(value: FactorExposureV1) -> dict[str, Any]:
    return {
        "factor_id": value.factor_id,
        "correlation_coefficient": value.correlation_coefficient,
        "loading_bps": value.loading_bps,
        "exposure": _money_to_dict(value.exposure),
    }


def _factor_from_dict(value: dict[str, Any]) -> FactorExposureV1:
    return FactorExposureV1(
        factor_id=str(value["factor_id"]),
        correlation_coefficient=value.get("correlation_coefficient"),
        loading_bps=value.get("loading_bps"),
        exposure=_money_from_dict(value.get("exposure")),
    )


def _body(record: UniversalEconomicAssessmentV1, *, include_id: bool = True) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": record.schema_version,
        "scope": scope_to_dict(record.scope),
        "account_id": record.account_id,
        "mode": record.mode,
        "assessed_at_ns": record.assessed_at_ns,
        "assumptions": _assumptions_to_dict(record.assumptions),
        "expected_gross_pnl": _money_to_dict(record.expected_gross_pnl),
        "expected_net_pnl": _money_to_dict(record.expected_net_pnl),
        "expected_return_bps": record.expected_return_bps,
        "capital_required": _money_to_dict(record.capital_required),
        "buying_power_required": _money_to_dict(record.buying_power_required),
        "initial_margin_required": _money_to_dict(record.initial_margin_required),
        "maintenance_margin_required": _money_to_dict(record.maintenance_margin_required),
        "maximum_loss": _money_to_dict(record.maximum_loss),
        "tail_loss": _money_to_dict(record.tail_loss),
        "loss_probability": record.loss_probability,
        "expected_hold_ns": record.expected_hold_ns,
        "maximum_hold_ns": record.maximum_hold_ns,
        "capital_lock_ns": record.capital_lock_ns,
        "expires_at_ns": record.expires_at_ns,
        "spread_bps": record.spread_bps,
        "slippage_bps": record.slippage_bps,
        "fees_bps": record.fees_bps,
        "borrow_bps": record.borrow_bps,
        "roll_bps": record.roll_bps,
        "funding_bps": record.funding_bps,
        "fill_probability": record.fill_probability,
        "adverse_selection_probability": record.adverse_selection_probability,
        "liquidity": _liquidity_to_dict(record.liquidity),
        "uncertainty": _uncertainty_to_dict(record.uncertainty),
        "factor_exposures": [_factor_to_dict(item) for item in record.factor_exposures],
        "account_actionability": record.account_actionability.value,
        "source_refs": [contract_reference_to_dict(ref) for ref in record.source_refs],
        "lineage_refs": [contract_reference_to_dict(ref) for ref in record.lineage_refs],
        "metadata": _thaw(record.metadata),
        "implementation_version": record.implementation_version,
    }
    if include_id:
        body["assessment_id"] = record.assessment_id
    return body


def economic_assessment_identity_hash(record: UniversalEconomicAssessmentV1) -> str:
    return sha256_bytes(canonical_bytes(_body(record, include_id=False)))


def economic_assessment_v1_to_dict(record: UniversalEconomicAssessmentV1) -> dict[str, Any]:
    body = _body(record)
    body["identity_hash"] = economic_assessment_identity_hash(record)
    body["units"] = dict(SEMANTIC_UNITS)
    return body


def economic_assessment_v1_from_dict(payload: dict[str, Any]) -> UniversalEconomicAssessmentV1:
    allowed = {item.name for item in fields(UniversalEconomicAssessmentV1)} | {
        "identity_hash",
        "units",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"UNKNOWN_FIELDS:{','.join(unknown)}")
    if payload.get("units") is not None and payload["units"] != SEMANTIC_UNITS:
        raise ValueError("ECONOMIC_SEMANTIC_UNITS_INVALID")
    record = UniversalEconomicAssessmentV1(
        assessment_id=str(payload["assessment_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        scope=scope_from_dict(payload["scope"]),
        account_id=str(payload["account_id"]),
        mode=str(payload["mode"]),
        assessed_at_ns=int(payload["assessed_at_ns"]),
        assumptions=_assumptions_from_dict(payload["assumptions"]),
        **{
            field_name: _money_from_dict(payload.get(field_name))
            for field_name in (
                "expected_gross_pnl",
                "expected_net_pnl",
                "capital_required",
                "buying_power_required",
                "initial_margin_required",
                "maintenance_margin_required",
                "maximum_loss",
                "tail_loss",
            )
        },
        expected_return_bps=payload.get("expected_return_bps"),
        loss_probability=payload.get("loss_probability"),
        expected_hold_ns=payload.get("expected_hold_ns"),
        maximum_hold_ns=payload.get("maximum_hold_ns"),
        capital_lock_ns=payload.get("capital_lock_ns"),
        expires_at_ns=payload.get("expires_at_ns"),
        spread_bps=payload.get("spread_bps"),
        slippage_bps=payload.get("slippage_bps"),
        fees_bps=payload.get("fees_bps"),
        borrow_bps=payload.get("borrow_bps"),
        roll_bps=payload.get("roll_bps"),
        funding_bps=payload.get("funding_bps"),
        fill_probability=payload.get("fill_probability"),
        adverse_selection_probability=payload.get("adverse_selection_probability"),
        liquidity=_liquidity_from_dict(payload.get("liquidity")),
        uncertainty=_uncertainty_from_dict(payload.get("uncertainty")),
        factor_exposures=tuple(_factor_from_dict(item) for item in payload.get("factor_exposures") or ()),
        account_actionability=AccountActionability(str(payload.get("account_actionability", "UNKNOWN"))),
        source_refs=tuple(contract_reference_from_dict(item) for item in payload.get("source_refs") or ()),
        lineage_refs=tuple(contract_reference_from_dict(item) for item in payload.get("lineage_refs") or ()),
        metadata=payload.get("metadata") or {},
        implementation_version=str(
            payload.get("implementation_version", ECONOMIC_ASSESSMENT_IMPLEMENTATION_VERSION)
        ),
    )
    serialized_hash = payload.get("identity_hash")
    if serialized_hash is not None and serialized_hash != economic_assessment_identity_hash(record):
        raise ValueError("ECONOMIC_ASSESSMENT_IDENTITY_HASH_MISMATCH")
    return record


# Compatibility names make the sidecar discoverable without creating a second contract.
EconomicAssessmentV1 = UniversalEconomicAssessmentV1
EconomicAssessmentSidecarV1 = UniversalEconomicAssessmentV1
UniversalEconomicAssessmentSidecarV1 = UniversalEconomicAssessmentV1

__all__ = [
    "AccountActionability",
    "BPS_UNIT",
    "EconomicAssessmentSidecarV1",
    "EconomicAssessmentV1",
    "EconomicAssumptionsV1",
    "EconomicUncertaintyV1",
    "FactorExposureV1",
    "LiquidityCapacityV1",
    "LiquidityState",
    "MONEY_UNIT",
    "MoneyMinorUnits",
    "NANOSECOND_UNIT",
    "PROBABILITY_UNIT",
    "SEMANTIC_UNITS",
    "UniversalEconomicAssessmentV1",
    "UniversalEconomicAssessmentSidecarV1",
    "economic_assessment_identity_hash",
    "economic_assessment_v1_from_dict",
    "economic_assessment_v1_to_dict",
]
