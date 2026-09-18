"""Paper simulator research path (HISTORICAL_DEVELOPMENT; not Item 9 calibration)."""

from __future__ import annotations

from typing import Any

from ...risk_simulation.evaluation import risk_simulation_root_hash, run_risk_simulation_evaluation

SIMULATOR_RESEARCH_RESULT_KIND = "SIMULATOR_RESEARCH_RESULT"
ITEM9_CALIBRATION_RESULT_KIND = "ITEM9_CALIBRATION_RESULT"


def run_historical_development_simulator_research(
    events: list[dict[str, Any]],
    *,
    simulator_version: str,
    cost_slippage_bps: float,
) -> dict[str, Any]:
    risk_result = run_risk_simulation_evaluation(events, enable_squeeze_replay=True)
    fills = list(risk_result.get("fills") or [])
    gross_pnl = sum(float(fill.get("realized_pnl", 0) or 0) for fill in fills)
    estimated_costs = abs(gross_pnl) * (cost_slippage_bps / 10_000.0)
    net_pnl = gross_pnl - estimated_costs
    return {
        "result_kind": SIMULATOR_RESEARCH_RESULT_KIND,
        "not_result_kind": ITEM9_CALIBRATION_RESULT_KIND,
        "item9_calibration": False,
        "simulator_version": simulator_version,
        "cost_slippage_bps": cost_slippage_bps,
        "risk_simulation_root_hash": risk_simulation_root_hash(risk_result),
        "fill_count": len(fills),
        "order_count": len(risk_result.get("orders") or []),
        "intent_count": len(risk_result.get("intents") or []),
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "estimated_costs": estimated_costs,
        "turnover": len(fills),
        "max_drawdown": risk_result.get("portfolio", {}).get("max_drawdown"),
        "exposure": risk_result.get("portfolio", {}).get("gross_exposure"),
        "coverage": risk_result.get("portfolio", {}).get("coverage"),
        "raw_risk_result_keys": sorted(risk_result.keys()),
    }


__all__ = [
    "ITEM9_CALIBRATION_RESULT_KIND",
    "SIMULATOR_RESEARCH_RESULT_KIND",
    "run_historical_development_simulator_research",
]
