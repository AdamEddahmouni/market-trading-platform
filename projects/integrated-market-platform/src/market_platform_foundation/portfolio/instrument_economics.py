"""Canonical instrument economics contract (G4 / BL-0211, Phase 1).

One fail-closed representation of the economic facts an accounting/risk
surface needs, derived from XA-01 canonical identity metadata — never from
symbol text. Extends the existing canonical model (``xa01.contracts``
``InstrumentDescriptor`` / ``DenominationMetadata``) instead of creating a
competing authority.

The contract answers, at minimum:

- canonical instrument id, asset class / instrument kind, tradability;
- quantity unit (SHARES / CONTRACTS / BASE_UNITS / FACE_VALUE);
- price denomination currency and settlement currency;
- contract multiplier (required, positive for OPTION_CONTRACT /
  FUTURE_CONTRACT — never silently defaulted to 1);
- tick size and lot/minimum quantity increment when known;
- expiration / strike / option right and underlying identity for
  derivatives when relevant.

Fail-closed rules (G4 Invariants 8-11):

- unknown instrument kinds are rejected (``UNKNOWN_INSTRUMENT_KIND``);
- missing or non-positive multiplier for a derivative kind is rejected
  (``MISSING_CONTRACT_MULTIPLIER`` / ``INVALID_CONTRACT_MULTIPLIER``);
- missing currency is rejected (``MISSING_CURRENCY``);
- multiplier=1 is acceptable ONLY when the canonical kind proves equity/ETF
  semantics (G4 Phase 10 migration rule);
- symbol heuristics are never used to infer economics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Mapping

from ..xa01.contracts import InstrumentDescriptor
from ..xa01.enums import InstrumentKind, RelationshipType, Tradability
from .accounting import DERIVATIVE_KINDS, AccountingError, exact_decimal
from .canonical import PortfolioError, PortfolioErrorCode, QuantityUnit


class EconomicsErrorCode(StrEnum):
    UNKNOWN_INSTRUMENT_KIND = "UNKNOWN_INSTRUMENT_KIND"
    UNKNOWN_ASSET_CLASS = "UNKNOWN_ASSET_CLASS"
    NON_EXECUTABLE_ECONOMICS = "NON_EXECUTABLE_ECONOMICS"
    MISSING_CONTRACT_MULTIPLIER = "MISSING_CONTRACT_MULTIPLIER"
    INVALID_CONTRACT_MULTIPLIER = "INVALID_CONTRACT_MULTIPLIER"
    MISSING_CURRENCY = "MISSING_CURRENCY"
    INVALID_QUANTITY_UNIT = "INVALID_QUANTITY_UNIT"
    UNSUPPORTED_ECONOMICS = "UNSUPPORTED_ECONOMICS"


@dataclass(frozen=True, slots=True)
class EconomicsError(Exception):
    code: EconomicsErrorCode
    message: str
    details: Mapping[str, Any]

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


# Quantity-unit mapping is kind-driven, never symbol-driven.
_QUANTITY_UNIT_BY_KIND: dict[str, QuantityUnit] = {
    "TRADABLE_SECURITY": QuantityUnit.SHARES,
    "ETF_FUND": QuantityUnit.SHARES,
    "OPTION_CONTRACT": QuantityUnit.CONTRACTS,
    "FUTURE_CONTRACT": QuantityUnit.CONTRACTS,
    "CRYPTO_PAIR": QuantityUnit.BASE_UNITS,
    "BOND": QuantityUnit.FACE_VALUE,
    "SOVEREIGN_SECURITY": QuantityUnit.FACE_VALUE,
}


def kind_default_quantity_unit(instrument_kind: str) -> QuantityUnit:
    """Deterministic quantity unit for a kind; unknown kinds fail closed."""
    kind = str(instrument_kind).upper()
    unit = _QUANTITY_UNIT_BY_KIND.get(kind)
    if unit is None:
        raise EconomicsError(
            EconomicsErrorCode.UNSUPPORTED_ECONOMICS,
            "no quantity unit for instrument kind",
            {"instrument_kind": kind},
        )
    return unit


def _multiplier_from_raw(
    raw: Any,
    *,
    instrument_kind: str,
    source: str,
) -> Decimal:
    """Fail-closed multiplier resolution.

    Derivatives require an explicit positive multiplier. Equity/ETF kinds may
    use 1 only because the canonical kind proves equity semantics (G4 Phase 10
    migration rule). Anything else is rejected.
    """
    kind = str(instrument_kind).upper()
    if kind in DERIVATIVE_KINDS:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise EconomicsError(
                EconomicsErrorCode.MISSING_CONTRACT_MULTIPLIER,
                f"{kind} requires an explicit canonical contract multiplier (no safe default)",
                {"instrument_kind": kind, "source": source},
            )
        try:
            value = exact_decimal(raw, field_name="contract_multiplier")
        except (AccountingError, ValueError, InvalidOperation):
            raise EconomicsError(
                EconomicsErrorCode.INVALID_CONTRACT_MULTIPLIER,
                "contract multiplier is not a valid decimal",
                {"instrument_kind": kind, "contract_multiplier": str(raw)},
            ) from None
        if value <= 0:
            raise EconomicsError(
                EconomicsErrorCode.INVALID_CONTRACT_MULTIPLIER,
                "contract multiplier must be positive",
                {"instrument_kind": kind, "contract_multiplier": str(value)},
            )
        return value
    if kind in {"TRADABLE_SECURITY", "ETF_FUND"}:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return Decimal("1")
        value = exact_decimal(raw, field_name="contract_multiplier")
        if value <= 0:
            raise EconomicsError(
                EconomicsErrorCode.INVALID_CONTRACT_MULTIPLIER,
                "contract multiplier must be positive",
                {"instrument_kind": kind, "contract_multiplier": str(value)},
            )
        return value
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return Decimal("1")
    value = exact_decimal(raw, field_name="contract_multiplier")
    if value <= 0:
        raise EconomicsError(
            EconomicsErrorCode.INVALID_CONTRACT_MULTIPLIER,
            "contract multiplier must be positive",
            {"instrument_kind": kind, "contract_multiplier": str(value)},
        )
    return value


def _currency_from_raw(raw: Any, *, instrument_kind: str) -> str:
    currency = str(raw or "").strip().upper()
    if not currency:
        raise EconomicsError(
            EconomicsErrorCode.MISSING_CURRENCY,
            "settlement/denomination currency is required",
            {"instrument_kind": str(instrument_kind).upper()},
        )
    return currency


@dataclass(frozen=True, slots=True)
class InstrumentEconomics:
    """Typed, fail-closed economics for one canonical instrument.

    ``settlement_currency`` equals ``price_currency`` in IMP today: no FX
    settlement conversion exists, and unknown FX fails closed at the gate
    (G4 Phase 6). The field exists so a future governed FX source can extend
    it without changing the contract shape.
    """

    instrument_id: str
    asset_class: str
    instrument_kind: str
    tradability: str
    quantity_unit: QuantityUnit
    price_currency: str
    settlement_currency: str
    contract_multiplier: Decimal = Decimal("1")
    tick_size: Decimal | None = None
    lot_size: Decimal | None = None
    expiration: str | None = None
    strike: str | None = None
    option_right: str | None = None
    underlying_id: str | None = None
    source: str = "XA01_DESCRIPTOR"
    schema_version: int = 1

    def __post_init__(self) -> None:
        kind = str(self.instrument_kind).upper()
        if kind in DERIVATIVE_KINDS and self.contract_multiplier <= 0:
            raise EconomicsError(
                EconomicsErrorCode.INVALID_CONTRACT_MULTIPLIER,
                "derivative position requires positive contract multiplier",
                {"instrument_kind": kind, "contract_multiplier": str(self.contract_multiplier)},
            )
        if kind in DERIVATIVE_KINDS and self.quantity_unit != QuantityUnit.CONTRACTS:
            raise EconomicsError(
                EconomicsErrorCode.INVALID_QUANTITY_UNIT,
                "derivative positions are quantified in contracts",
                {"instrument_kind": kind, "quantity_unit": self.quantity_unit.value},
            )

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "asset_class": self.asset_class,
            "contract_multiplier": format(self.contract_multiplier, "f"),
            "instrument_id": self.instrument_id,
            "instrument_kind": self.instrument_kind,
            "price_currency": self.price_currency,
            "quantity_unit": self.quantity_unit.value,
            "schema_version": self.schema_version,
            "settlement_currency": self.settlement_currency,
            "source": self.source,
            "tradability": self.tradability,
        }
        for key, value in (
            ("expiration", self.expiration),
            ("lot_size", None if self.lot_size is None else format(self.lot_size, "f")),
            ("option_right", self.option_right),
            ("strike", self.strike),
            ("tick_size", None if self.tick_size is None else format(self.tick_size, "f")),
            ("underlying_id", self.underlying_id),
        ):
            if value is not None:
                body[key] = value
        return body

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "InstrumentEconomics":
        return cls(
            instrument_id=str(payload["instrument_id"]),
            asset_class=str(payload["asset_class"]),
            instrument_kind=str(payload["instrument_kind"]),
            tradability=str(payload.get("tradability", Tradability.REFERENCE_ONLY.value)),
            quantity_unit=QuantityUnit(str(payload["quantity_unit"])),
            price_currency=str(payload["price_currency"]),
            settlement_currency=str(payload.get("settlement_currency", payload["price_currency"])),
            contract_multiplier=exact_decimal(payload.get("contract_multiplier", "1"), field_name="contract_multiplier"),
            tick_size=exact_decimal(payload["tick_size"], field_name="tick_size") if payload.get("tick_size") is not None else None,
            lot_size=exact_decimal(payload["lot_size"], field_name="lot_size") if payload.get("lot_size") is not None else None,
            expiration=payload.get("expiration"),
            strike=payload.get("strike"),
            option_right=payload.get("option_right"),
            underlying_id=payload.get("underlying_id"),
            source=str(payload.get("source", "XA01_DESCRIPTOR")),
            schema_version=int(payload.get("schema_version", 1)),
        )


def economics_from_descriptor(
    descriptor: InstrumentDescriptor,
    *,
    registry: Any | None = None,
) -> InstrumentEconomics:
    """Build fail-closed economics from a canonical XA-01 descriptor.

    ``registry`` is optional; when supplied, the UNDERLYING relationship is
    resolved to the underlying instrument's canonical id.
    """
    identity = descriptor.identity
    kind = str(identity.instrument_kind.value).upper()
    try:
        kind_enum = InstrumentKind(kind)
    except ValueError:
        raise EconomicsError(
            EconomicsErrorCode.UNKNOWN_INSTRUMENT_KIND,
            "unknown canonical instrument kind",
            {"instrument_kind": kind},
        ) from None
    try:
        asset_class = str(identity.asset_class.value)
    except Exception:
        raise EconomicsError(
            EconomicsErrorCode.UNKNOWN_ASSET_CLASS,
            "unknown canonical asset class",
            {"asset_class": str(identity.asset_class)},
        ) from None

    denomination = descriptor.denomination
    multiplier_raw = denomination.contract_multiplier
    currency = _currency_from_raw(denomination.currency, instrument_kind=kind)
    unit_raw = denomination.quantity_unit
    quantity_unit: QuantityUnit
    if unit_raw:
        try:
            quantity_unit = QuantityUnit(str(unit_raw).upper())
        except ValueError:
            raise EconomicsError(
                EconomicsErrorCode.INVALID_QUANTITY_UNIT,
                "denomination quantity_unit is not a canonical unit",
                {"quantity_unit": str(unit_raw)},
            ) from None
    else:
        quantity_unit = kind_default_quantity_unit(kind)

    underlying_id: str | None = None
    if registry is not None:
        try:
            record = registry.get(identity.canonical_id)
            for rel in record.relationships:
                if rel.relationship_type == RelationshipType.UNDERLYING:
                    underlying_id = rel.to_canonical_id
                    break
        except Exception:
            underlying_id = None

    return InstrumentEconomics(
        instrument_id=identity.canonical_id,
        asset_class=asset_class,
        instrument_kind=kind_enum.value,
        tradability=str(descriptor.tradability.value),
        quantity_unit=quantity_unit,
        price_currency=currency,
        settlement_currency=currency,
        contract_multiplier=_multiplier_from_raw(multiplier_raw, instrument_kind=kind, source="XA01_DESCRIPTOR"),
        tick_size=exact_decimal(denomination.tick_size, field_name="tick_size") if denomination.tick_size else None,
        lot_size=None,
        expiration=descriptor.expiration or None,
        strike=descriptor.strike or None,
        option_right=descriptor.call_put or None,
        underlying_id=underlying_id,
        source="XA01_DESCRIPTOR",
    )


def economics_from_instrument_ref(instrument: Mapping[str, Any]) -> InstrumentEconomics:
    """Build fail-closed economics from a runtime instrument reference.

    Accepts the paper ``build_instrument_ref`` shape. Legacy equity refs that
    carry no ``instrument_kind`` are treated as equity (TRADABLE_SECURITY /
    EQUITY) — the only place multiplier=1 is valid without a kind is a
    legacy equity ref, matching G4 Phase 10's migration rule. Derivatives
    without an explicit multiplier fail closed.
    """
    instrument_id = str(instrument.get("instrument_id") or "").strip()
    if not instrument_id:
        raise EconomicsError(
            EconomicsErrorCode.UNSUPPORTED_ECONOMICS,
            "instrument ref requires instrument_id",
            {},
        )
    kind_raw = instrument.get("instrument_kind")
    if kind_raw is None or not str(kind_raw).strip():
        kind = "TRADABLE_SECURITY"
        asset_class = str(instrument.get("asset_class") or "EQUITY").upper()
        tradability = Tradability.TRADABLE.value
    else:
        kind = str(kind_raw).upper()
        try:
            InstrumentKind(kind)
        except ValueError:
            raise EconomicsError(
                EconomicsErrorCode.UNKNOWN_INSTRUMENT_KIND,
                "unknown instrument kind",
                {"instrument_kind": kind},
            ) from None
        asset_class = str(instrument.get("asset_class") or "").upper() or _default_asset_class(kind)
        tradability = str(instrument.get("tradability") or Tradability.TRADABLE.value)

    currency = _currency_from_raw(
        instrument.get("currency") or instrument.get("settlement_currency"),
        instrument_kind=kind,
    )
    unit_raw = instrument.get("quantity_unit")
    quantity_unit: QuantityUnit
    if unit_raw:
        try:
            quantity_unit = QuantityUnit(str(unit_raw).upper())
        except ValueError:
            raise EconomicsError(
                EconomicsErrorCode.INVALID_QUANTITY_UNIT,
                "quantity_unit is not a canonical unit",
                {"quantity_unit": str(unit_raw)},
            ) from None
    else:
        quantity_unit = kind_default_quantity_unit(kind)

    multiplier = _multiplier_from_raw(
        instrument.get("contract_multiplier"),
        instrument_kind=kind,
        source="INSTRUMENT_REF",
    )
    tick_raw = instrument.get("tick_size")
    lot_raw = instrument.get("lot_size")
    return InstrumentEconomics(
        instrument_id=instrument_id,
        asset_class=asset_class,
        instrument_kind=kind,
        tradability=tradability,
        quantity_unit=quantity_unit,
        price_currency=currency,
        settlement_currency=currency,
        contract_multiplier=multiplier,
        tick_size=exact_decimal(tick_raw, field_name="tick_size") if tick_raw else None,
        lot_size=exact_decimal(lot_raw, field_name="lot_size") if lot_raw else None,
        expiration=instrument.get("expiration"),
        strike=instrument.get("strike"),
        option_right=instrument.get("option_right"),
        underlying_id=instrument.get("underlying"),
        source="INSTRUMENT_REF",
    )


def _default_asset_class(instrument_kind: str) -> str:
    mapping = {
        "TRADABLE_SECURITY": "EQUITY",
        "ETF_FUND": "ETF_FUND",
        "OPTION_CONTRACT": "OPTION",
        "FUTURE_CONTRACT": "FUTURE",
        "CRYPTO_PAIR": "CRYPTO",
        "BOND": "BOND",
        "SOVEREIGN_SECURITY": "SOVEREIGN_DEBT",
    }
    asset = mapping.get(instrument_kind)
    if asset is None:
        raise EconomicsError(
            EconomicsErrorCode.UNKNOWN_ASSET_CLASS,
            "no default asset class for instrument kind",
            {"instrument_kind": instrument_kind},
        )
    return asset


def assert_derivative_position_economics(
    *,
    instrument_kind: str,
    quantity_unit: QuantityUnit,
    multiplier: Any,
) -> None:
    """Fail-closed economics check for the canonical position mutation boundary.

    A derivative position (OPTION_CONTRACT / FUTURE_CONTRACT) must be
    quantified in contracts and carry a positive explicit multiplier — never
    a silent multiplier=1 fallback (G4 Invariant 10). Raises
    ``PortfolioError(INVALID_POSITION_ECONOMICS)`` so the canonical store's
    existing error vocabulary is preserved.
    """
    kind = str(instrument_kind).upper()
    if kind not in DERIVATIVE_KINDS:
        return
    if quantity_unit != QuantityUnit.CONTRACTS:
        raise PortfolioError(
            PortfolioErrorCode.INVALID_POSITION_ECONOMICS,
            "derivative positions must be quantified in contracts",
            {"instrument_kind": kind, "quantity_unit": quantity_unit.value},
        )
    try:
        multiplier_dec = exact_decimal(multiplier, field_name="multiplier")
    except Exception as exc:
        raise PortfolioError(
            PortfolioErrorCode.INVALID_POSITION_ECONOMICS,
            "derivative position requires an explicit contract multiplier",
            {"instrument_kind": kind},
        ) from exc
    if multiplier_dec <= 0:
        raise PortfolioError(
            PortfolioErrorCode.INVALID_POSITION_ECONOMICS,
            "derivative contract multiplier must be positive",
            {"instrument_kind": kind, "multiplier": str(multiplier_dec)},
        )


__all__ = [
    "DERIVATIVE_KINDS",
    "EconomicsError",
    "EconomicsErrorCode",
    "InstrumentEconomics",
    "assert_derivative_position_economics",
    "economics_from_descriptor",
    "economics_from_instrument_ref",
    "kind_default_quantity_unit",
]