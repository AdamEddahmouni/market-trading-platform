"""Canonical normalized futures contract model (F1 foundation).

Distinguishes tradeable contract instances (e.g. ESU26) from instrument families (ES).
Never treat a family symbol as a timeless security.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal


class FuturesFamily(StrEnum):
    """Asset-family taxonomy for plugin interpretation branches."""

    EQUITY_INDEX = "EQUITY_INDEX"
    TREASURY = "TREASURY"
    SHORT_RATE = "SHORT_RATE"
    FX = "FX"
    ENERGY = "ENERGY"
    AGRICULTURE = "AGRICULTURE"
    METALS = "METALS"
    CRYPTO_FUTURES = "CRYPTO_FUTURES"
    OTHER = "OTHER"


class SettlementType(StrEnum):
    PHYSICAL = "physical"
    CASH = "cash"
    UNKNOWN = "unknown"


class RollState(StrEnum):
    """Roll lifecycle — lead contract may differ from nearest expiry."""

    PRE_ROLL = "PRE_ROLL"
    ROLLING = "ROLLING"
    POST_ROLL = "POST_ROLL"
    EXPIRING = "EXPIRING"


class BasisDefinition(StrEnum):
    """Explicit basis sign convention — never mix series built under different semantics."""

    FUTURES_MINUS_SPOT = "FUTURES_MINUS_SPOT"
    SPOT_MINUS_FUTURES = "SPOT_MINUS_FUTURES"
    FUTURES_MINUS_FAIR_VALUE = "FUTURES_MINUS_FAIR_VALUE"


ContinuousSeriesMethod = Literal[
    "unadjusted_continuous",
    "additive_back_adjusted",
    "ratio_adjusted",
    "constant_maturity",
]


@dataclass(frozen=True, slots=True)
class FuturesContractSpec:
    """Versioned contract specification metadata — first-class data, not hard-coded logic."""

    multiplier: Decimal
    tick_size: Decimal
    tick_value: Decimal
    point_value: Decimal
    spec_version: str = "1"
    spec_effective_date: str = ""


@dataclass(frozen=True, slots=True)
class FuturesContract:
    """Normalized futures contract — platform ingestion target for F1+."""

    instrument_family: str
    contract_id: str
    underlying_id: str

    asset_class: str
    subclass: str = ""
    family: FuturesFamily = FuturesFamily.OTHER

    exchange: str = ""
    currency: str = "USD"

    expiration: str = ""
    first_notice_date: str | None = None
    last_trade_date: str | None = None
    delivery_start: str | None = None
    delivery_end: str | None = None

    settlement_type: SettlementType = SettlementType.UNKNOWN
    settlement_methodology: str = ""
    physical_delivery_terms: str = ""

    spec: FuturesContractSpec | None = None

    price: Decimal | None = None
    settlement_price: Decimal | None = None
    last_trade_price: Decimal | None = None
    close: Decimal | None = None

    volume: int | None = None
    open_interest: int | None = None

    initial_margin: Decimal | None = None
    maintenance_margin: Decimal | None = None

    lead_contract: bool = False
    roll_state: RollState | None = None

    provider: str = ""
    event_time: str = ""
    available_time: str = ""
    ingested_time: str = ""

    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class FuturesCurveSnapshot:
    """Term structure snapshot — curve level/slope/carry derived separately."""

    instrument_family: str
    observation_time: str
    available_time: str

    contract_ids: tuple[str, ...]
    expirations: tuple[str, ...]
    prices: tuple[Decimal, ...]
    volumes: tuple[int, ...] = ()
    open_interests: tuple[int, ...] = ()
    liquidity_scores: tuple[float, ...] = ()

    lead_contract_id: str = ""
    roll_state: RollState | None = None

    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class FuturesPositioningSnapshot:
    """COT / futures positioning with publication-delay semantics."""

    instrument_family: str
    report_type: str
    participant_category: str

    long_positions: int | None = None
    short_positions: int | None = None
    spreading: int | None = None
    net: int | None = None

    net_change: int | None = None
    net_percentile: float | None = None
    net_zscore: float | None = None

    observation_time: str = ""
    publication_time: str = ""
    data_age_days: int | None = None

    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class BasisObservation:
    """Basis with explicit definition — never assume universal sign."""

    instrument_family: str
    contract_id: str
    basis_value: Decimal
    basis_definition: BasisDefinition
    spot_reference_id: str = ""
    event_time: str = ""
    available_time: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


def futures_contract_to_dict(contract: FuturesContract) -> dict[str, Any]:
    """Serialize for API envelopes and replay fixtures."""
    spec: dict[str, Any] | None = None
    if contract.spec is not None:
        spec = {
            "multiplier": str(contract.spec.multiplier),
            "tick_size": str(contract.spec.tick_size),
            "tick_value": str(contract.spec.tick_value),
            "point_value": str(contract.spec.point_value),
            "spec_version": contract.spec.spec_version,
            "spec_effective_date": contract.spec.spec_effective_date,
        }
    return {
        "instrument_family": contract.instrument_family,
        "contract_id": contract.contract_id,
        "underlying_id": contract.underlying_id,
        "asset_class": contract.asset_class,
        "subclass": contract.subclass,
        "family": contract.family.value,
        "exchange": contract.exchange,
        "currency": contract.currency,
        "expiration": contract.expiration,
        "first_notice_date": contract.first_notice_date,
        "last_trade_date": contract.last_trade_date,
        "delivery_start": contract.delivery_start,
        "delivery_end": contract.delivery_end,
        "settlement_type": contract.settlement_type.value,
        "settlement_methodology": contract.settlement_methodology,
        "physical_delivery_terms": contract.physical_delivery_terms,
        "spec": spec,
        "price": str(contract.price) if contract.price is not None else None,
        "settlement_price": (
            str(contract.settlement_price) if contract.settlement_price is not None else None
        ),
        "last_trade_price": (
            str(contract.last_trade_price) if contract.last_trade_price is not None else None
        ),
        "close": str(contract.close) if contract.close is not None else None,
        "volume": contract.volume,
        "open_interest": contract.open_interest,
        "initial_margin": (
            str(contract.initial_margin) if contract.initial_margin is not None else None
        ),
        "maintenance_margin": (
            str(contract.maintenance_margin) if contract.maintenance_margin is not None else None
        ),
        "lead_contract": contract.lead_contract,
        "roll_state": contract.roll_state.value if contract.roll_state else None,
        "provider": contract.provider,
        "event_time": contract.event_time,
        "available_time": contract.available_time,
        "ingested_time": contract.ingested_time,
        "quality_flags": list(contract.quality_flags),
        "provenance_ref": contract.provenance_ref,
    }


def futures_curve_to_dict(snapshot: FuturesCurveSnapshot) -> dict[str, Any]:
    return {
        "instrument_family": snapshot.instrument_family,
        "observation_time": snapshot.observation_time,
        "available_time": snapshot.available_time,
        "contract_ids": list(snapshot.contract_ids),
        "expirations": list(snapshot.expirations),
        "prices": [str(p) for p in snapshot.prices],
        "volumes": list(snapshot.volumes),
        "open_interests": list(snapshot.open_interests),
        "liquidity_scores": list(snapshot.liquidity_scores),
        "lead_contract_id": snapshot.lead_contract_id,
        "roll_state": snapshot.roll_state.value if snapshot.roll_state else None,
        "quality_flags": list(snapshot.quality_flags),
        "provenance_ref": snapshot.provenance_ref,
    }


def cot_point_in_time_valid(
    observation_time: str,
    publication_time: str,
    decision_time: str,
) -> bool:
    """Return True when COT is visible at decision_time (publication delay enforced).

    COT reflects Tuesday positions but is released Friday — event_time ≠ available_time.
    """
    if not publication_time or not decision_time:
        return False
    return decision_time >= publication_time

