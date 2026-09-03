"""CrossAssetRegimeContext — macro + CFTC positioning with independent clocks."""

from __future__ import annotations

from typing import Any

from ..cftc.contracts import InstitutionalPositioningState
from ..cftc.store import CotStore
from ..cftc.derived import build_positioning_state
from ..cftc.contracts import CotPositionScope, CotReportFamily
from .contracts import CrossAssetRegimeContext, MacroRegimeState
from .pit import macro_state_as_of
from .contracts import MacroObservation


CFTC_SYNTHESIS_MATRIX = {
    "rates_inflation": ["ZT", "ZF", "ZN", "ZB", "UB"],
    "growth_liquidity": ["ES", "NQ", "RTY", "YM"],
    "rates_usd": ["6E", "6J", "6B"],
    "growth_inflation_usd": ["CL", "NG"],
    "real_rates_usd": ["GC", "SI"],
}


def build_cross_asset_regime_context(
    *,
    macro_observations: list[MacroObservation],
    cot_store: CotStore,
    decision_time: str,
    contract_family_id: str = "ES",
    pit_available: bool = True,
) -> CrossAssetRegimeContext:
    macro_state = macro_state_as_of(
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
        positioning_state = build_positioning_state(
            observations=[latest_cot],
            contract_family_id=contract_family_id,
            report_family=CotReportFamily.TFF,
            position_scope=CotPositionScope.FUTURES_ONLY,
            decision_time=decision_time,
        )
        positioning_available = latest_cot.publication_time

    contradictions: list[str] = []
    fin_conditions = macro_state.financial_conditions.get("US_NFCI")
    if (
        positioning_state
        and fin_conditions
        and fin_conditions.value is not None
        and fin_conditions.value < 0
        and positioning_state.leveraged_or_managed_net is not None
        and positioning_state.leveraged_or_managed_net < 0
    ):
        contradictions.append("EASING_FINANCIAL_CONDITIONS_WITH_HEAVY_LEVERAGED_SHORTS")

    quality = list(macro_state.quality_flags) + list(cot_flags)
    return CrossAssetRegimeContext(
        macro_state=macro_state,
        institutional_positioning_state=positioning_state,
        decision_time=decision_time,
        macro_available_time=_latest_macro_available(macro_state),
        positioning_available_time=positioning_available,
        staleness={
            "macro": macro_state.decision_time,
            "positioning": positioning_available,
        },
        quality_flags=tuple(dict.fromkeys(quality)),
        contradictions=tuple(contradictions),
        provenance_ref="fred.cross_asset_regime_context",
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


__all__ = ["CFTC_SYNTHESIS_MATRIX", "build_cross_asset_regime_context"]
