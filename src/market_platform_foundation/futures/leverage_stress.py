"""Futures leverage / liquidation stress engine (F8) — rule-based composite v1."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from ..contracts.futures import FuturesContract
from ..contracts.futures_quality import quality_blocks_leverage_stress
from ..providers.contracts import ProviderResult
from .notional import ES_CONTRACT_SPEC, exposure_summary
from .positioning import CrowdingRegime

LEVERAGE_STRESS_VERSION = "futures_leverage_stress_v1"
STRESS_HIGH_THRESHOLD = 0.70
STRESS_MODERATE_THRESHOLD = 0.45
LIQUIDATION_RISK_THRESHOLD = 0.65


class StressRegime(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class LeverageStressSnapshot:
    instrument_family: str
    stress_score: float | None = None
    stress_regime: StressRegime = StressRegime.UNAVAILABLE
    long_liquidation_risk: bool = False
    short_liquidation_risk: bool = False
    effective_leverage: float | None = None
    margin_percentile: float | None = None
    margin_change_pct: float | None = None
    crowding_regime: str | None = None
    fragility_score: float | None = None
    disclaimer: str = (
        "Futures liquidation stress is distinct from equity short squeeze mechanics. "
        "Stress composite is contextual, not a directional forecast."
    )
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = "margin.fixture.futures_margin"


def compute_margin_percentile(
    current_margin: Decimal,
    history: list[Decimal],
) -> float | None:
    if not history:
        return None
    values = sorted(history)
    if current_margin <= values[0]:
        return 0.0
    if current_margin >= values[-1]:
        return 1.0
    rank = sum(1 for value in values if value <= current_margin)
    return round(rank / len(values), 6)


def stress_regime_from_score(score: float | None) -> StressRegime:
    if score is None:
        return StressRegime.UNAVAILABLE
    if score >= STRESS_HIGH_THRESHOLD:
        return StressRegime.HIGH
    if score >= STRESS_MODERATE_THRESHOLD:
        return StressRegime.MODERATE
    return StressRegime.LOW


def leverage_stress_to_dict(snapshot: LeverageStressSnapshot) -> dict[str, Any]:
    return {
        "instrument_family": snapshot.instrument_family,
        "stress_score": snapshot.stress_score,
        "stress_regime": snapshot.stress_regime.value,
        "long_liquidation_risk": snapshot.long_liquidation_risk,
        "short_liquidation_risk": snapshot.short_liquidation_risk,
        "effective_leverage": snapshot.effective_leverage,
        "margin_percentile": snapshot.margin_percentile,
        "margin_change_pct": snapshot.margin_change_pct,
        "crowding_regime": snapshot.crowding_regime,
        "fragility_score": snapshot.fragility_score,
        "disclaimer": snapshot.disclaimer,
        "quality_flags": list(snapshot.quality_flags),
        "provenance_ref": snapshot.provenance_ref,
        "leverage_stress_version": LEVERAGE_STRESS_VERSION,
    }


def _latest_pit_margin_row(
    rows: list[dict[str, Any]],
    decision_time: int | str,
) -> dict[str, Any] | None:
    from .macro_events import _decision_time_iso, _parse_time

    decision_dt = _parse_time(_decision_time_iso(decision_time))
    eligible: list[dict[str, Any]] = []
    for row in rows:
        available_time = str(row.get("available_time") or row.get("observation_time") or "")
        available_dt = _parse_time(available_time)
        if available_dt is None:
            continue
        if decision_dt is not None and available_dt > decision_dt:
            continue
        eligible.append(row)
    if not eligible:
        return None
    eligible.sort(
        key=lambda row: str(row.get("available_time") or row.get("observation_time") or "")
    )
    return eligible[-1]


def compute_stress_score(
    *,
    margin_percentile: float | None,
    margin_change_pct: float | None,
    crowding_regime: str | None,
    fragility_score: float | None,
    effective_leverage: float | None,
) -> float | None:
    components: list[float] = []
    if margin_percentile is not None:
        components.append(margin_percentile * 0.35)
    if margin_change_pct is not None and margin_change_pct > 0:
        components.append(min(margin_change_pct / 20.0, 1.0) * 0.20)
    if crowding_regime == CrowdingRegime.CROWDED_LONG.value:
        components.append(0.20)
    elif crowding_regime == CrowdingRegime.CROWDED_SHORT.value:
        components.append(0.20)
    if fragility_score is not None:
        components.append(min(max(fragility_score, 0.0), 1.0) * 0.15)
    if effective_leverage is not None:
        components.append(min(effective_leverage / 20.0, 1.0) * 0.10)
    if not components:
        return None
    return round(min(sum(components), 1.0), 6)


def build_leverage_stress_snapshot(
    *,
    instrument_family: str,
    margin_row: dict[str, Any],
    margin_history: list[dict[str, Any]],
    lead_price: Decimal | None,
    crowding_regime: str | None,
    fragility_score: float | None,
    quality_flags: tuple[str, ...] = (),
) -> LeverageStressSnapshot:
    maintenance_values: list[Decimal] = []
    for row in margin_history:
        raw = row.get("maintenance_margin")
        if raw is not None:
            maintenance_values.append(Decimal(str(raw)))

    current_maintenance = Decimal(str(margin_row.get("maintenance_margin", "0")))
    margin_percentile = compute_margin_percentile(current_maintenance, maintenance_values)
    margin_change_raw = margin_row.get("margin_change_pct")
    margin_change_pct = float(margin_change_raw) if margin_change_raw is not None else None

    effective_leverage: float | None = None
    if lead_price is not None and current_maintenance > 0:
        contract = FuturesContract(
            instrument_family=instrument_family,
            contract_id=str(margin_row.get("contract_id", f"{instrument_family}")),
            underlying_id=instrument_family,
            asset_class="future",
            spec=ES_CONTRACT_SPEC,
            maintenance_margin=current_maintenance,
            price=lead_price,
        )
        summary = exposure_summary(contract, 1)
        raw_leverage = summary.get("effective_leverage")
        if raw_leverage is not None:
            effective_leverage = float(raw_leverage)

    stress_score = compute_stress_score(
        margin_percentile=margin_percentile,
        margin_change_pct=margin_change_pct,
        crowding_regime=crowding_regime,
        fragility_score=fragility_score,
        effective_leverage=effective_leverage,
    )
    regime = stress_regime_from_score(stress_score)

    long_risk = (
        regime in {StressRegime.HIGH, StressRegime.MODERATE}
        and crowding_regime == CrowdingRegime.CROWDED_LONG.value
        and stress_score is not None
        and stress_score >= LIQUIDATION_RISK_THRESHOLD
    )
    short_risk = (
        regime in {StressRegime.HIGH, StressRegime.MODERATE}
        and crowding_regime == CrowdingRegime.CROWDED_SHORT.value
        and stress_score is not None
        and stress_score >= LIQUIDATION_RISK_THRESHOLD
    )

    return LeverageStressSnapshot(
        instrument_family=instrument_family,
        stress_score=stress_score,
        stress_regime=regime,
        long_liquidation_risk=long_risk,
        short_liquidation_risk=short_risk,
        effective_leverage=effective_leverage,
        margin_percentile=margin_percentile,
        margin_change_pct=margin_change_pct,
        crowding_regime=crowding_regime,
        fragility_score=fragility_score,
        quality_flags=quality_flags,
        provenance_ref=str(margin_row.get("provenance_ref", "margin.fixture.futures_margin")),
    )


def leverage_stress_payload(
    margin_result: ProviderResult,
    *,
    instrument_family: str,
    decision_time: int | str,
    crowding_regime: str | None = None,
    lead_price: Decimal | float | None = None,
    fragility_score: float | None = None,
) -> dict[str, Any]:
    """Build workspace leverage stress payload with fail-closed semantics."""
    if margin_result.status != "available" or not margin_result.events:
        return {
            "available": False,
            "reason": margin_result.reason_code or "MARGIN_UNAVAILABLE",
            "futures_leverage_stress_available": False,
            "leverage_stress_version": LEVERAGE_STRESS_VERSION,
        }

    rows = [row for row in margin_result.events if isinstance(row, dict)]
    latest = _latest_pit_margin_row(rows, decision_time)
    if latest is None:
        return {
            "available": False,
            "reason": "MARGIN_NOT_PIT_ELIGIBLE",
            "futures_leverage_stress_available": False,
            "leverage_stress_version": LEVERAGE_STRESS_VERSION,
        }

    quality_flags = list(latest.get("quality_flags", []) or [])
    if quality_blocks_leverage_stress(tuple(quality_flags)):
        return {
            "available": False,
            "reason": "LEVERAGE_STRESS_BLOCKED",
            "futures_leverage_stress_available": False,
            "quality_flags": quality_flags,
            "leverage_stress_version": LEVERAGE_STRESS_VERSION,
        }

    price_decimal = Decimal(str(lead_price)) if lead_price is not None else None
    snapshot = build_leverage_stress_snapshot(
        instrument_family=instrument_family,
        margin_row=latest,
        margin_history=rows,
        lead_price=price_decimal,
        crowding_regime=crowding_regime,
        fragility_score=fragility_score,
        quality_flags=tuple(quality_flags),
    )

    payload = leverage_stress_to_dict(snapshot)
    available = snapshot.stress_regime != StressRegime.UNAVAILABLE
    payload["available"] = available
    return {
        "available": available,
        "leverage_stress_snapshot": payload,
        "futures_leverage_stress_available": available,
        "stress_regime": snapshot.stress_regime.value,
        "long_liquidation_risk": snapshot.long_liquidation_risk,
        "short_liquidation_risk": snapshot.short_liquidation_risk,
        "quality_flags": quality_flags,
        "leverage_stress_version": LEVERAGE_STRESS_VERSION,
    }


__all__ = [
    "LEVERAGE_STRESS_VERSION",
    "LeverageStressSnapshot",
    "StressRegime",
    "build_leverage_stress_snapshot",
    "compute_margin_percentile",
    "compute_stress_score",
    "leverage_stress_payload",
    "leverage_stress_to_dict",
    "stress_regime_from_score",
]
