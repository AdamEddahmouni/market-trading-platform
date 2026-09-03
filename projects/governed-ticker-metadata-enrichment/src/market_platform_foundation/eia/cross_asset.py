"""EnergyMarketContext — macro + CFTC + EIA with independent source clocks."""

from __future__ import annotations

from typing import Any

from ..cftc.contracts import CotPositionScope, CotReportFamily, InstitutionalPositioningState
from ..cftc.derived import build_positioning_state
from ..cftc.store import CotStore
from ..fred.contracts import MacroRegimeState
from ..fred.pit import macro_state_as_of
from ..fred.contracts import MacroObservation
from ..weather.contracts import WeatherDemandState
from ..weather.derived import build_weather_demand_state
from ..weather.store import WeatherStore
from .contracts import EnergyFundamentalsState, EnergyMarketContext
from .derived import build_energy_fundamentals_state
from .store import EiaStore


def _latest_physical_available(state: EnergyFundamentalsState) -> str:
    candidates: list[str] = []
    for block in (
        state.petroleum.commercial_crude,
        state.petroleum.cushing,
        state.petroleum.production,
        state.natural_gas.lower48_storage,
    ):
        if block and block.available_time:
            candidates.append(block.available_time)
    return max(candidates) if candidates else ""


def build_energy_market_context(
    *,
    macro_observations: list[MacroObservation],
    cot_store: CotStore,
    eia_store: EiaStore,
    decision_time: str,
    contract_family_id: str = "CL",
    pit_available: bool = True,
    weather_store: WeatherStore | None = None,
) -> EnergyMarketContext:
    macro_state: MacroRegimeState = macro_state_as_of(
        macro_observations,
        decision_time=decision_time,
        pit_available=pit_available,
    )
    latest_cot, cot_flags = cot_store.latest_visible_or_flags(
        contract_family_id=contract_family_id,
        decision_time=decision_time,
        position_scope=CotPositionScope.FUTURES_ONLY,
    )
    positioning_state: InstitutionalPositioningState | None = None
    positioning_available = ""
    if latest_cot is not None:
        report_family = (
            CotReportFamily.DISAGGREGATED
            if contract_family_id in {"CL", "NG", "GC", "SI"}
            else CotReportFamily.TFF
        )
        positioning_state = build_positioning_state(
            observations=[latest_cot],
            contract_family_id=contract_family_id,
            report_family=report_family,
            position_scope=CotPositionScope.FUTURES_ONLY,
            decision_time=decision_time,
        )
        positioning_available = latest_cot.publication_time

    physical_state = build_energy_fundamentals_state(
        eia_store.observations,
        decision_time=decision_time,
    )
    physical_available = _latest_physical_available(physical_state)

    weather_state: WeatherDemandState | None = None
    weather_available = ""
    if weather_store is not None:
        weather_state = build_weather_demand_state(
            weather_store,
            decision_time=decision_time,
        )
        weather_available = weather_state.latest_forecast_available_time

    contradictions: list[str] = []
    commercial = physical_state.petroleum.commercial_crude
    production = physical_state.petroleum.production
    if (
        commercial
        and production
        and commercial.value is not None
        and production.value is not None
        and positioning_state
        and positioning_state.leveraged_or_managed_net is not None
    ):
        if commercial.value < 400000 and production.value > 12000 and positioning_state.leveraged_or_managed_net < 0:
            contradictions.append("FALLING_COMMERCIAL_STOCKS_RISING_PRODUCTION_WITH_MANAGED_SHORTS")

    quality = list(macro_state.quality_flags) + list(cot_flags) + list(physical_state.quality_flags)
    if weather_state is not None:
        quality.extend(weather_state.quality_flags)
    return EnergyMarketContext(
        macro_state=macro_state,
        institutional_positioning_state=positioning_state,
        physical_fundamentals_state=physical_state,
        decision_time=decision_time,
        macro_available_time=_latest_macro_available(macro_state),
        positioning_available_time=positioning_available,
        physical_available_time=physical_available,
        staleness={
            "macro": _latest_macro_available(macro_state),
            "positioning": positioning_available,
            "physical": physical_available,
            "weather": weather_available or None,
        },
        quality_flags=tuple(dict.fromkeys(quality)),
        contradictions=tuple(contradictions),
        provenance_ref="eia.energy_market_context",
        weather_demand_state=weather_state,
        weather_available_time=weather_available,
    )


def _latest_macro_available(state: MacroRegimeState) -> str:
    latest = ""
    for block in (
        state.rates,
        state.yield_curve,
        state.inflation,
        state.labor,
        state.growth,
        state.liquidity,
        state.credit,
        state.financial_conditions,
        state.usd,
    ):
        for value in block.values():
            if value and value.available_time > latest:
                latest = value.available_time
    return latest


__all__ = ["build_energy_market_context"]
