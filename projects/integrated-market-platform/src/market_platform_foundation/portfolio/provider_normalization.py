"""Provider snapshot normalization into canonical positions (G2 §47–48).

Provider/broker position rows become canonical position inputs through the
XA-01 alias resolver: provider symbol -> canonical instrument identity ->
canonical position input -> account-scoped portfolio state. Provider symbols
are never persisted as canonical portfolio keys, and an ambiguous or unknown
row is classified ``UNRESOLVED_INSTRUMENT`` and left out of portfolio truth
until resolved — it never mutates an arbitrary existing position and never
defaults to an equity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping

from ..xa01.contracts import InstrumentRecord
from ..xa01.enums import ExternalIdentifierType, InstrumentKind
from ..xa01.registry import InstrumentRegistry
from ..xa01.resolver import resolve_alias
from .canonical import (
    PositionInput,
    PortfolioError,
    PortfolioErrorCode,
    QuantityUnit,
    _as_decimal,
)


class NormalizationStatus(StrEnum):
    NORMALIZED = "NORMALIZED"
    UNRESOLVED_INSTRUMENT = "UNRESOLVED_INSTRUMENT"
    NON_EXECUTABLE = "NON_EXECUTABLE"
    INVALID_ROW = "INVALID_ROW"


@dataclass(frozen=True, slots=True)
class ProviderPositionRow:
    """One provider/broker position row (PROVIDER_INPUT, never canonical state)."""

    provider_id: str
    provider_symbol: str
    quantity: Decimal
    currency: str = "USD"
    average_cost: Decimal | None = None
    realized_pnl: Decimal | None = None
    source_time_ns: int = 0
    observed_at_ns: int = 0
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider_id or not str(self.provider_id).strip():
            raise PortfolioError(PortfolioErrorCode.INVALID_PORTFOLIO_KEY, "provider_id required", {})
        if not self.provider_symbol or not str(self.provider_symbol).strip():
            raise PortfolioError(PortfolioErrorCode.INVALID_INSTRUMENT, "provider_symbol required", {})
        object.__setattr__(self, "quantity", _as_decimal(self.quantity, field_name="quantity"))
        if self.average_cost is not None:
            object.__setattr__(self, "average_cost", _as_decimal(self.average_cost, field_name="average_cost"))
        if self.realized_pnl is not None:
            object.__setattr__(self, "realized_pnl", _as_decimal(self.realized_pnl, field_name="realized_pnl"))


@dataclass(frozen=True, slots=True)
class NormalizedPosition:
    status: NormalizationStatus
    provider_id: str
    provider_symbol: str
    canonical_id: str = ""
    position_input: PositionInput | None = None
    reason: str = ""

    @property
    def normalized(self) -> bool:
        return self.status == NormalizationStatus.NORMALIZED


def _position_input_from_record(
    record: InstrumentRecord,
    row: ProviderPositionRow,
) -> PositionInput:
    identity = record.descriptor.identity
    kind = identity.instrument_kind
    if kind == InstrumentKind.TRADABLE_SECURITY:
        quantity_unit = QuantityUnit.SHARES
        multiplier = Decimal("1")
        price_basis = None
    elif kind == InstrumentKind.OPTION_CONTRACT:
        quantity_unit = QuantityUnit.CONTRACTS
        # G4: multiplier is canonical economics, never silently defaulted.
        raw_multiplier = record.descriptor.denomination.contract_multiplier
        if not raw_multiplier or not str(raw_multiplier).strip():
            raise PortfolioError(
                PortfolioErrorCode.INVALID_INSTRUMENT,
                "option contract has no canonical multiplier",
                {"canonical_id": identity.canonical_id},
            )
        multiplier = _as_decimal(raw_multiplier, field_name="contract_multiplier")
        price_basis = None
    elif kind == InstrumentKind.FUTURE_CONTRACT:
        quantity_unit = QuantityUnit.CONTRACTS
        # G4: a future without a canonical multiplier fails closed — never
        # silently equity-style multiplier=1.
        raw_multiplier = record.descriptor.denomination.contract_multiplier
        if not raw_multiplier or not str(raw_multiplier).strip():
            raise PortfolioError(
                PortfolioErrorCode.INVALID_INSTRUMENT,
                "future contract has no canonical multiplier",
                {"canonical_id": identity.canonical_id},
            )
        multiplier = _as_decimal(raw_multiplier, field_name="contract_multiplier")
        price_basis = None
    elif kind == InstrumentKind.CRYPTO_PAIR:
        quantity_unit = QuantityUnit.BASE_UNITS
        multiplier = Decimal("1")
        price_basis = None
    else:
        # Reference identities (bond/sovereign/commodity/family/continuous)
        # never normalize into a position today.
        raise PortfolioError(
            PortfolioErrorCode.NON_EXECUTABLE_INSTRUMENT,
            "provider row resolved to a non-positionable identity",
            {"instrument_kind": kind.value, "canonical_id": identity.canonical_id},
        )
    return PositionInput(
        instrument_id=identity.canonical_id,
        asset_class=identity.asset_class.value,
        instrument_kind=kind.value,
        quantity=row.quantity,
        quantity_unit=quantity_unit,
        native_currency=str(record.descriptor.denomination.currency or row.currency),
        multiplier=multiplier,
        average_cost=row.average_cost,
        cost_basis=(
            row.average_cost * abs(row.quantity)
            if row.average_cost is not None
            else None
        ),
        realized_pnl_native=row.realized_pnl if row.realized_pnl is not None else Decimal("0"),
        price_basis=price_basis,
        source_time_ns=row.source_time_ns,
        observed_at_ns=row.observed_at_ns,
    )


def normalize_provider_position(
    row: ProviderPositionRow,
    *,
    registry: InstrumentRegistry,
) -> NormalizedPosition:
    """Resolve one provider row to a canonical position input, failing closed.

    Unknown or ambiguous aliases produce ``UNRESOLVED_INSTRUMENT`` with no
    position input; non-executable identities produce ``NON_EXECUTABLE``; the
    caller must never guess, default to equity, or mutate an existing position
    from any non-NORMALIZED result.
    """
    from .admission import admission_result

    resolution = resolve_alias(
        provider_id=row.provider_id,
        alias_value=row.provider_symbol,
        identifier_type=ExternalIdentifierType.PROVIDER_SYMBOL,
        registry=registry,
    )
    if resolution.status.value != "RESOLVED" or not resolution.canonical_id:
        return NormalizedPosition(
            NormalizationStatus.UNRESOLVED_INSTRUMENT,
            row.provider_id,
            row.provider_symbol,
            reason=f"ALIAS_{resolution.status.value}",
        )
    record = registry.get(resolution.canonical_id)
    admission = admission_result(
        instrument_kind=record.descriptor.identity.instrument_kind.value,
        asset_class=record.descriptor.identity.asset_class.value,
        tradability=record.descriptor.tradability.value,
    )
    if not admission.admitted:
        return NormalizedPosition(
            NormalizationStatus.NON_EXECUTABLE,
            row.provider_id,
            row.provider_symbol,
            canonical_id=resolution.canonical_id,
            reason=admission.reason,
        )
    try:
        position_input = _position_input_from_record(record, row)
    except PortfolioError as exc:
        return NormalizedPosition(
            NormalizationStatus.NON_EXECUTABLE,
            row.provider_id,
            row.provider_symbol,
            canonical_id=resolution.canonical_id,
            reason=str(exc.code.value),
        )
    return NormalizedPosition(
        NormalizationStatus.NORMALIZED,
        row.provider_id,
        row.provider_symbol,
        canonical_id=resolution.canonical_id,
        position_input=position_input,
    )


def normalize_provider_snapshot(
    rows: list[ProviderPositionRow],
    *,
    registry: InstrumentRegistry,
) -> tuple[list[NormalizedPosition], list[NormalizedPosition]]:
    """Normalize a full provider snapshot; return (normalized, unresolved).

    Rows that cannot be resolved are returned in the second list so the caller
    can record an explicit issue (``UNRESOLVED_INSTRUMENT``) without mutating
    canonical portfolio truth for those instruments.
    """
    normalized: list[NormalizedPosition] = []
    unresolved: list[NormalizedPosition] = []
    for row in rows:
        result = normalize_provider_position(row, registry=registry)
        if result.normalized:
            normalized.append(result)
        else:
            unresolved.append(result)
    return normalized, unresolved


__all__ = [
    "NormalizationStatus",
    "NormalizedPosition",
    "ProviderPositionRow",
    "normalize_provider_position",
    "normalize_provider_snapshot",
]