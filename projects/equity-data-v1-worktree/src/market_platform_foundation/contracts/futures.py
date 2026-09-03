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


@dataclass(frozen=True, slots=True)
class FuturesTrendBaselineSnapshot:
    """Vol-scaled trend features — research baseline, not directional forecast."""

    instrument_family: str
    trend_1m: float | None = None
    trend_3m: float | None = None
    trend_6m: float | None = None
    trend_12m: float | None = None
    vol_estimate: float | None = None
    lookback_bars_used: tuple[tuple[str, int], ...] = field(default_factory=tuple)
    observation_time: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class FuturesCarryBaseline:
    """Carry level with historical percentile — not assumed predictive."""

    annualized_carry: float | None = None
    carry_percentile: float | None = None
    carry_change: float | None = None
    carry_zscore: float | None = None
    formula_tag: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FuturesCurveMomentum:
    """Term-structure slope momentum — curve context, not directional forecast."""

    curve_slope: float | None = None
    slope_change: float | None = None
    calendar_spread_momentum: str = ""
    regime: str = ""
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


def basis_observation_to_dict(observation: BasisObservation) -> dict[str, Any]:
    return {
        "instrument_family": observation.instrument_family,
        "contract_id": observation.contract_id,
        "basis_value": str(observation.basis_value),
        "basis_definition": observation.basis_definition.value,
        "spot_reference_id": observation.spot_reference_id,
        "event_time": observation.event_time,
        "available_time": observation.available_time,
        "quality_flags": list(observation.quality_flags),
    }


def positioning_snapshot_to_dict(snapshot: FuturesPositioningSnapshot) -> dict[str, Any]:
    return {
        "instrument_family": snapshot.instrument_family,
        "report_type": snapshot.report_type,
        "participant_category": snapshot.participant_category,
        "long_positions": snapshot.long_positions,
        "short_positions": snapshot.short_positions,
        "spreading": snapshot.spreading,
        "net": snapshot.net,
        "net_change": snapshot.net_change,
        "net_percentile": snapshot.net_percentile,
        "net_zscore": snapshot.net_zscore,
        "observation_time": snapshot.observation_time,
        "publication_time": snapshot.publication_time,
        "data_age_days": snapshot.data_age_days,
        "quality_flags": list(snapshot.quality_flags),
        "provenance_ref": snapshot.provenance_ref,
    }


def trend_baseline_to_dict(snapshot: FuturesTrendBaselineSnapshot) -> dict[str, Any]:
    return {
        "instrument_family": snapshot.instrument_family,
        "trend_1m": round(snapshot.trend_1m, 6) if snapshot.trend_1m is not None else None,
        "trend_3m": round(snapshot.trend_3m, 6) if snapshot.trend_3m is not None else None,
        "trend_6m": round(snapshot.trend_6m, 6) if snapshot.trend_6m is not None else None,
        "trend_12m": round(snapshot.trend_12m, 6) if snapshot.trend_12m is not None else None,
        "vol_estimate": round(snapshot.vol_estimate, 8) if snapshot.vol_estimate is not None else None,
        "lookback_bars_used": {key: value for key, value in snapshot.lookback_bars_used},
        "observation_time": snapshot.observation_time,
        "quality_flags": list(snapshot.quality_flags),
        "provenance_ref": snapshot.provenance_ref,
    }


def trend_baseline_from_dict(payload: dict[str, Any]) -> FuturesTrendBaselineSnapshot:
    quality = payload.get("quality_flags", [])
    quality_flags = tuple(str(flag) for flag in quality) if isinstance(quality, list) else ()
    lookback_raw = payload.get("lookback_bars_used", {})
    lookback_bars_used: tuple[tuple[str, int], ...] = ()
    if isinstance(lookback_raw, dict):
        lookback_bars_used = tuple((str(k), int(v)) for k, v in lookback_raw.items())
    return FuturesTrendBaselineSnapshot(
        instrument_family=str(payload.get("instrument_family", "")),
        trend_1m=float(payload["trend_1m"]) if payload.get("trend_1m") is not None else None,
        trend_3m=float(payload["trend_3m"]) if payload.get("trend_3m") is not None else None,
        trend_6m=float(payload["trend_6m"]) if payload.get("trend_6m") is not None else None,
        trend_12m=float(payload["trend_12m"]) if payload.get("trend_12m") is not None else None,
        vol_estimate=float(payload["vol_estimate"]) if payload.get("vol_estimate") is not None else None,
        lookback_bars_used=lookback_bars_used,
        observation_time=str(payload.get("observation_time", "")),
        quality_flags=quality_flags,
        provenance_ref=str(payload.get("provenance_ref", "")),
    )


def carry_baseline_to_dict(baseline: FuturesCarryBaseline) -> dict[str, Any]:
    return {
        "annualized_carry": round(baseline.annualized_carry, 8) if baseline.annualized_carry is not None else None,
        "carry_percentile": baseline.carry_percentile,
        "carry_change": round(baseline.carry_change, 8) if baseline.carry_change is not None else None,
        "carry_zscore": round(baseline.carry_zscore, 6) if baseline.carry_zscore is not None else None,
        "formula_tag": baseline.formula_tag,
        "quality_flags": list(baseline.quality_flags),
    }


def curve_momentum_to_dict(momentum: FuturesCurveMomentum) -> dict[str, Any]:
    return {
        "curve_slope": round(momentum.curve_slope, 8) if momentum.curve_slope is not None else None,
        "slope_change": round(momentum.slope_change, 8) if momentum.slope_change is not None else None,
        "calendar_spread_momentum": momentum.calendar_spread_momentum,
        "regime": momentum.regime,
        "quality_flags": list(momentum.quality_flags),
    }


def positioning_snapshot_from_dict(payload: dict[str, Any]) -> FuturesPositioningSnapshot:
    quality = payload.get("quality_flags", [])
    quality_flags = tuple(str(flag) for flag in quality) if isinstance(quality, list) else ()
    return FuturesPositioningSnapshot(
        instrument_family=str(payload.get("instrument_family", "")),
        report_type=str(payload.get("report_type", "")),
        participant_category=str(payload.get("participant_category", "")),
        long_positions=int(payload["long_positions"]) if payload.get("long_positions") is not None else None,
        short_positions=int(payload["short_positions"]) if payload.get("short_positions") is not None else None,
        spreading=int(payload["spreading"]) if payload.get("spreading") is not None else None,
        net=int(payload["net"]) if payload.get("net") is not None else None,
        net_change=int(payload["net_change"]) if payload.get("net_change") is not None else None,
        net_percentile=float(payload["net_percentile"]) if payload.get("net_percentile") is not None else None,
        net_zscore=float(payload["net_zscore"]) if payload.get("net_zscore") is not None else None,
        observation_time=str(payload.get("observation_time", "")),
        publication_time=str(payload.get("publication_time", "")),
        data_age_days=int(payload["data_age_days"]) if payload.get("data_age_days") is not None else None,
        quality_flags=quality_flags,
        provenance_ref=str(payload.get("provenance_ref", "")),
    )


def futures_contract_from_dict(payload: dict[str, Any]) -> FuturesContract:
    """Deserialize FuturesContract — fail-closed on missing required fields."""
    required = ("instrument_family", "contract_id", "underlying_id", "asset_class")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise ValueError(f"FUTURES_CONTRACT_MISSING_FIELDS:{','.join(missing)}")
    spec_raw = payload.get("spec")
    spec: FuturesContractSpec | None = None
    if isinstance(spec_raw, dict):
        spec = FuturesContractSpec(
            multiplier=Decimal(str(spec_raw.get("multiplier", "1"))),
            tick_size=Decimal(str(spec_raw.get("tick_size", "0.01"))),
            tick_value=Decimal(str(spec_raw.get("tick_value", "0"))),
            point_value=Decimal(str(spec_raw.get("point_value", "1"))),
            spec_version=str(spec_raw.get("spec_version", "1")),
            spec_effective_date=str(spec_raw.get("spec_effective_date", "")),
        )
    roll_raw = payload.get("roll_state")
    roll_state: RollState | None = None
    if roll_raw:
        try:
            roll_state = RollState(str(roll_raw))
        except ValueError:
            roll_state = None
    settlement_raw = payload.get("settlement_type", SettlementType.UNKNOWN.value)
    try:
        settlement_type = SettlementType(str(settlement_raw))
    except ValueError:
        settlement_type = SettlementType.UNKNOWN
    family_raw = payload.get("family", FuturesFamily.OTHER.value)
    try:
        family = FuturesFamily(str(family_raw))
    except ValueError:
        family = FuturesFamily.OTHER
    quality = payload.get("quality_flags", [])
    quality_flags = tuple(str(flag) for flag in quality) if isinstance(quality, list) else ()

    def _dec(key: str) -> Decimal | None:
        val = payload.get(key)
        return Decimal(str(val)) if val is not None else None

    return FuturesContract(
        instrument_family=str(payload["instrument_family"]),
        contract_id=str(payload["contract_id"]),
        underlying_id=str(payload["underlying_id"]),
        asset_class=str(payload["asset_class"]),
        subclass=str(payload.get("subclass", "")),
        family=family,
        exchange=str(payload.get("exchange", "")),
        currency=str(payload.get("currency", "USD")),
        expiration=str(payload.get("expiration", "")),
        first_notice_date=str(payload.get("first_notice_date")) if payload.get("first_notice_date") else None,
        last_trade_date=str(payload.get("last_trade_date")) if payload.get("last_trade_date") else None,
        delivery_start=str(payload.get("delivery_start")) if payload.get("delivery_start") else None,
        delivery_end=str(payload.get("delivery_end")) if payload.get("delivery_end") else None,
        settlement_type=settlement_type,
        settlement_methodology=str(payload.get("settlement_methodology", "")),
        physical_delivery_terms=str(payload.get("physical_delivery_terms", "")),
        spec=spec,
        price=_dec("price"),
        settlement_price=_dec("settlement_price"),
        last_trade_price=_dec("last_trade_price"),
        close=_dec("close"),
        volume=int(payload["volume"]) if payload.get("volume") is not None else None,
        open_interest=int(payload["open_interest"]) if payload.get("open_interest") is not None else None,
        initial_margin=_dec("initial_margin"),
        maintenance_margin=_dec("maintenance_margin"),
        lead_contract=bool(payload.get("lead_contract", False)),
        roll_state=roll_state,
        provider=str(payload.get("provider", "")),
        event_time=str(payload.get("event_time", "")),
        available_time=str(payload.get("available_time", "")),
        ingested_time=str(payload.get("ingested_time", "")),
        quality_flags=quality_flags,
        provenance_ref=str(payload.get("provenance_ref", "")),
    )


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

