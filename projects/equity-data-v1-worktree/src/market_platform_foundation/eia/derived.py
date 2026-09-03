"""Deterministic derived energy features — not predictive."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import (
    EnergyFeatureLayer,
    EnergyFundamentalObservation,
    EnergyFundamentalsState,
    EnergyIndicatorValue,
    EnergyMetricClass,
    NaturalGasFundamentalsBlock,
    PetroleumFundamentalsBlock,
)
from .pit import query_visible
from .quality import EiaQualityFlag


@dataclass(frozen=True, slots=True)
class DerivedEnergyFeatures:
    weekly_balance_change: float | None
    change_vs_4w_average: float | None
    feature_layer: EnergyFeatureLayer = EnergyFeatureLayer.DETERMINISTIC_DERIVED
    predictive: bool = False
    disclaimer: str = (
        "weekly balance change is not physical injection volume; "
        "storage changes may include reclassifications"
    )


def compute_balance_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None:
        return None
    return current - prior


def derive_balance_change(
    observations: list[EnergyFundamentalObservation],
    *,
    canonical_indicator_id: str,
    decision_time: str,
) -> DerivedEnergyFeatures:
    visible = query_visible(
        observations,
        decision_time=decision_time,
        canonical_indicator_id=canonical_indicator_id,
    )
    if len(visible) < 2:
        return DerivedEnergyFeatures(weekly_balance_change=None, change_vs_4w_average=None)
    current = visible[-1].normalized_value
    prior = visible[-2].normalized_value
    weekly = compute_balance_change(current, prior)
    trailing = visible[-5:]
    changes = []
    for idx in range(1, len(trailing)):
        delta = compute_balance_change(
            trailing[idx].normalized_value,
            trailing[idx - 1].normalized_value,
        )
        if delta is not None:
            changes.append(delta)
    avg4 = sum(changes) / len(changes) if changes else None
    change_vs_4w = compute_balance_change(weekly, avg4) if weekly is not None and avg4 is not None else None
    return DerivedEnergyFeatures(
        weekly_balance_change=weekly,
        change_vs_4w_average=change_vs_4w,
    )


def _indicator_value(obs: EnergyFundamentalObservation | None) -> EnergyIndicatorValue | None:
    if obs is None:
        return None
    return EnergyIndicatorValue(
        canonical_indicator_id=obs.canonical_indicator_id,
        value=obs.normalized_value,
        raw_value=obs.raw_value,
        unit=obs.unit,
        metric_class=obs.metric_class,
        period_end=obs.period_end,
        available_time=obs.available_time,
        quality_flags=obs.quality_flags,
        provenance_ref=obs.provenance_ref,
    )


def build_energy_fundamentals_state(
    store_observations: list[EnergyFundamentalObservation],
    *,
    decision_time: str,
) -> EnergyFundamentalsState:
    visible = query_visible(store_observations, decision_time=decision_time)
    by_id = {obs.canonical_indicator_id: obs for obs in visible}
    flags: list[str] = []

    petroleum = PetroleumFundamentalsBlock(
        commercial_crude=_indicator_value(by_id.get("COMMERCIAL_CRUDE_STOCKS")),
        cushing=_indicator_value(by_id.get("CUSHING_CRUDE_STOCKS")),
        spr=_indicator_value(by_id.get("SPR_CRUDE_STOCKS")),
        gasoline=_indicator_value(by_id.get("TOTAL_MOTOR_GASOLINE_STOCKS")),
        distillate=_indicator_value(by_id.get("DISTILLATE_FUEL_STOCKS")),
        propane=_indicator_value(by_id.get("PROPANE_PROPYLENE_STOCKS")),
        production=_indicator_value(by_id.get("CRUDE_OIL_PRODUCTION")),
        refinery_inputs=_indicator_value(by_id.get("REFINERY_CRUDE_INPUTS")),
        refinery_utilization=_indicator_value(by_id.get("REFINERY_UTILIZATION")),
        crude_imports=_indicator_value(by_id.get("CRUDE_OIL_IMPORTS")),
        crude_exports=_indicator_value(by_id.get("CRUDE_OIL_EXPORTS")),
        petroleum_exports=_indicator_value(by_id.get("TOTAL_PETROLEUM_EXPORTS")),
        product_supplied=_indicator_value(by_id.get("TOTAL_PRODUCT_SUPPLIED")),
        gasoline_product_supplied=_indicator_value(by_id.get("GASOLINE_PRODUCT_SUPPLIED")),
        distillate_product_supplied=_indicator_value(by_id.get("DISTILLATE_PRODUCT_SUPPLIED")),
        crude_days_of_supply=_indicator_value(by_id.get("CRUDE_DAYS_OF_SUPPLY")),
        regional={
            key: value
            for key, value in {
                "PADD_2": _indicator_value(by_id.get("PADD2_COMMERCIAL_CRUDE_STOCKS")),
            }.items()
            if value is not None
        },
    )

    lower48 = by_id.get("LOWER48_WORKING_GAS_STORAGE")
    storage_change = derive_balance_change(
        store_observations,
        canonical_indicator_id="LOWER48_WORKING_GAS_STORAGE",
        decision_time=decision_time,
    )
    ng = NaturalGasFundamentalsBlock(
        lower48_storage=_indicator_value(lower48),
        regional_storage={
            "EAST": _indicator_value(by_id.get("EAST_WORKING_GAS_STORAGE")),
            "MIDWEST": _indicator_value(by_id.get("MIDWEST_WORKING_GAS_STORAGE")),
            "MOUNTAIN": _indicator_value(by_id.get("MOUNTAIN_WORKING_GAS_STORAGE")),
            "PACIFIC": _indicator_value(by_id.get("PACIFIC_WORKING_GAS_STORAGE")),
            "SOUTH_CENTRAL": _indicator_value(by_id.get("SOUTH_CENTRAL_WORKING_GAS_STORAGE")),
            "SOUTH_CENTRAL_SALT": _indicator_value(by_id.get("SOUTH_CENTRAL_SALT_WORKING_GAS_STORAGE")),
            "SOUTH_CENTRAL_NONSALT": _indicator_value(by_id.get("SOUTH_CENTRAL_NONSALT_WORKING_GAS_STORAGE")),
        },
        storage_change=(
            EnergyIndicatorValue(
                canonical_indicator_id="LOWER48_STORAGE_BALANCE_CHANGE",
                value=storage_change.weekly_balance_change,
                raw_value=str(storage_change.weekly_balance_change)
                if storage_change.weekly_balance_change is not None
                else None,
                unit="Billion Cubic Feet",
                metric_class=EnergyMetricClass.BALANCE_CHANGE,
                period_end=lower48.period_end if lower48 else "",
                available_time=lower48.available_time if lower48 else "",
                quality_flags=lower48.quality_flags if lower48 else (EiaQualityFlag.SERIES_UNAVAILABLE.value,),
                provenance_ref="eia.derived.balance_change",
            )
            if lower48
            else None
        ),
    )

    for obs in visible:
        flags.extend(obs.quality_flags)
    return EnergyFundamentalsState(
        petroleum=petroleum,
        natural_gas=ng,
        decision_time=decision_time,
        quality_flags=tuple(dict.fromkeys(flags)),
        provenance_ref="eia.energy_fundamentals_state",
        predictive=False,
    )


__all__ = [
    "DerivedEnergyFeatures",
    "build_energy_fundamentals_state",
    "compute_balance_change",
    "derive_balance_change",
]
